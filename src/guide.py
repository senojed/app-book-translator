"""Překladatelský návod = lidská rozhodnutí (guide.json) a draft od scouta
(guide.draft.json). Oboje jsou soubory, ne DB - edituje je člověk přes review UI
a za běhu `run` se nemění.

Důležité: prompt blok návodu NIKDY neobsahuje dvojice termín→český překlad.
Jediný zdroj pravdy pro překlad termínu je glosář, jinak by návod přebíjel
schválená rozhodnutí.
"""
import json
import os

_GUIDE_SHAPE = {"characters": [], "places": [], "terms": [],
                "relationships": [], "style": "", "rules": []}
_DRAFT_SHAPE = {"characters": [], "places": [], "terms": [],
                "relationships": [], "style_notes": "", "must_decide": []}


def normalize(name: str) -> str:
    return (name or "").strip().lower()


def relationship_key(a: str, b: str) -> str:
    """Klíč dvojice nezávislý na pořadí. v1: podle jména, ne přes aliasy -
    'Harry|Murphy' a 'Dresden|Murphy' se nespárují."""
    return "|".join(sorted([normalize(a), normalize(b)]))


def _load(path: str, shape: dict) -> dict:
    if not path or not os.path.exists(path):
        return json.loads(json.dumps(shape))
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return json.loads(json.dumps(shape))
    # Starší / neúplný tvar doplníme, aby downstream nikdy nepadal na KeyError.
    for k, v in shape.items():
        data.setdefault(k, json.loads(json.dumps(v)))
    return data


def _save(path: str, data: dict) -> None:
    """Atomický zápis - napůl zapsaný JSON by shodil další běh."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_guide(path: str) -> dict:
    return _load(path, _GUIDE_SHAPE)


def save_guide(path: str, guide: dict) -> None:
    _save(path, guide)


def load_draft(path: str) -> dict:
    return _load(path, _DRAFT_SHAPE)


def save_draft(path: str, draft: dict) -> None:
    _save(path, draft)


def add_rule(path: str, rule: str) -> None:
    g = load_guide(path)
    if rule not in g["rules"]:
        g["rules"].append(rule)
    save_guide(path, g)


def merge_draft_and_guide(draft: dict, guide: dict) -> dict:
    """Podklad pro review UI: draft scouta předvyplní, lidská rozhodnutí vyhrávají.
    Výstup už používá FINÁLNÍ názvy polí (cz, render, address, style)."""
    draft = draft or {}
    guide = guide or {}

    def by_name(items, key):
        return {normalize(i.get(key, "")): i for i in (items or [])}

    g_chars = by_name(guide.get("characters"), "name_en")
    out_chars = []
    seen = set()
    for d in (draft.get("characters") or []):
        name = d.get("name_en", "")
        g = g_chars.get(normalize(name), {})
        seen.add(normalize(name))
        out_chars.append({
            "name_en": name,
            "aliases": g.get("aliases") or d.get("aliases") or [],
            "render": g.get("render") or d.get("suggested") or "keep",
            "cz": g.get("cz") or "",
            "note": d.get("note") or "",
        })
    for key, g in g_chars.items():   # rozhodnuté postavy, které draft nezná
        if key not in seen:
            out_chars.append({"name_en": g.get("name_en", ""),
                              "aliases": g.get("aliases") or [],
                              "render": g.get("render") or "keep",
                              "cz": g.get("cz") or "", "note": ""})

    def merge_simple(draft_items, guide_items, name_key):
        g_map = by_name(guide_items, name_key)
        out, done = [], set()
        for d in (draft_items or []):
            name = d.get(name_key, "")
            g = g_map.get(normalize(name), {})
            done.add(normalize(name))
            out.append({name_key: name,
                        "cz": g.get("cz") or d.get("suggested_cz") or "",
                        "note": d.get("note") or ""})
        for key, g in g_map.items():
            if key not in done:
                out.append({name_key: g.get(name_key, ""), "cz": g.get("cz") or "",
                            "note": ""})
        return out

    g_rel = {relationship_key(r.get("a", ""), r.get("b", "")): r
             for r in (guide.get("relationships") or [])}
    out_rel, done_rel = [], set()
    for d in (draft.get("relationships") or []):
        k = relationship_key(d.get("a", ""), d.get("b", ""))
        g = g_rel.get(k, {})
        done_rel.add(k)
        out_rel.append({"a": d.get("a", ""), "b": d.get("b", ""),
                        "address": g.get("address") or d.get("suggested") or ""})
    for k, g in g_rel.items():
        if k not in done_rel:
            out_rel.append({"a": g.get("a", ""), "b": g.get("b", ""),
                            "address": g.get("address") or ""})

    return {
        "characters": out_chars,
        "places": merge_simple(draft.get("places"), guide.get("places"), "name_en"),
        "terms": merge_simple(draft.get("terms"), guide.get("terms"), "term_en"),
        "relationships": out_rel,
        "style": guide.get("style") or draft.get("style_notes", "") or "",
        "rules": guide.get("rules") or [],
        "must_decide": draft.get("must_decide") or [],
    }


def guide_as_prompt_block(guide: dict) -> str:
    """Styl, vztahy a keep/translate rozhodnutí do promptu. ŽÁDNÉ cz páry."""
    guide = guide or {}
    parts = []

    style = (guide.get("style") or "").strip()
    parts.append("STYL:\n" + (style if style else "(zatím nic)"))

    rels = []
    for r in (guide.get("relationships") or []):
        addr = r.get("address") or ""
        if not addr:
            continue
        how = "tykají si" if addr == "tyka" else "vykají si"
        rels.append(f"{r.get('a','')} ↔ {r.get('b','')}: {how}")
    parts.append("VZTAHY (oslovení):\n" + ("\n".join(rels) if rels else "(zatím nic)"))

    keep, translate = [], []
    for c in (guide.get("characters") or []):
        (translate if c.get("render") == "translate" else keep).append(c.get("name_en", ""))
    lines = []
    if keep:
        lines.append("ponechat v originále: " + ", ".join(x for x in keep if x))
    if translate:
        lines.append("přeložit (překlad viz glosář): " + ", ".join(x for x in translate if x))
    parts.append("JMÉNA:\n" + ("\n".join(lines) if lines else "(zatím nic)"))

    rules = [r for r in (guide.get("rules") or []) if r]
    parts.append("PRAVIDLA:\n" + ("\n".join(f"- {r}" for r in rules) if rules else "(zatím nic)"))

    return "\n\n".join(parts)
