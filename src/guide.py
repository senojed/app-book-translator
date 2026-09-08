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


def _reference_index(reference):
    if not reference:
        return {}
    return {f["id"]: f for f in reference.get("findings") or []}


def _is_fresh(reference, draft, cfg) -> bool:
    """Jeden příznak, ne tři: čerstvé je jen to, kde sedí otisk draftu, korpusu
    i prahů. Nedostupný korpus se chová jako nečerstvý - radši nepředvyplnit
    než předvyplnit z neznámého podkladu."""
    if not reference or cfg is None:
        return False
    from src import reference_mine
    fp = reference.get("fingerprint") or {}
    if fp.get("draft") != reference_mine.draft_fingerprint(draft):
        return False
    if fp.get("thresholds") != reference_mine.thresholds_fingerprint(cfg):
        return False
    current_corpus = reference_mine.corpus_fingerprint(reference.get("source_root") or "")
    return current_corpus is not None and fp.get("corpus") == current_corpus


def _reference_block(finding, fresh, shown_cz):
    """Nečerstvá reference nepřispívá NIČÍM než příznakem - ani klasifikací,
    ani návrhem: formulář zobrazí jen poznámku, že existuje nález z jiného
    běhu. U čerstvé se číselný důkaz vynechá, liší-li se zobrazená hodnota od
    té, ke které se důkaz váže - ale jen u tříd, které hodnotu předvyplňují;
    `evidence_only` má cz prázdné záměrně a jeho důkaz je jediný obsah, který
    má."""
    if not fresh:
        return {"fresh": False}
    block = {"fresh": True, "classification": finding["classification"],
             "primary_attested": finding["primary_attested"],
             "matched_forms": finding["matched_forms"],
             "matched_cz": finding["matched_cz"]}
    prefilling = finding["classification"] in ("confirmed", "weak")
    # `shown_cz != matched_cz` SAMO O SOBĚ, bez `shown_cz and` navíc - prázdné
    # `shown_cz` (platný stav u postavy s render="keep", viz Task 9) je falsy,
    # takže by `shown_cz and ...` podmínku "liší se" nikdy nevyhodnotilo a
    # číselný důkaz by zůstal, ačkoli prázdné pole zjevně neodpovídá
    # `matched_cz`. NEPŘIDÁVEJ zpátky `shown_cz and` - to byl ten bug.
    if prefilling and shown_cz != finding["matched_cz"]:
        return block
    block.update({"hits": finding["hits"], "books": finding["books"],
                  "per_form": finding["per_form"],
                  "cooccurrence": finding["cooccurrence"]})
    return block


def _merge_section(draft, guide_data, ref_index, fresh, section, key_field,
                   is_character=False):
    from src import textnorm
    # textnorm.normalize_key (NFC + casefold), ne guide.normalize (jen
    # strip+lower) - identita postavy/místa/termínu musí přežít i jinak
    # zapsaný, ale kanonicky stejný Unicode text (guide.json může vzniknout
    # jinou cestou než draft, např. ruční editací v prohlížeči). guide.normalize
    # zůstává vyhrazený vztahům (guide.relationship_key), kde na tenhle rozdíl
    # spec explicitně nenaráží.
    g_map = {textnorm.normalize_key(i.get(key_field, "")): i
             for i in (guide_data.get(section) or [])}
    out, done = [], set()
    for d in (draft.get(section) or []):
        name = d.get(key_field, "")
        key = textnorm.normalize_key(name)
        g = g_map.get(key, {})
        done.add(key)
        fid = f"{section}/{key}"
        finding = ref_index.get(fid)

        scout_suggestion = (d.get("suggested_cz") if not is_character
                            else None) or None
        # Nečerstvá reference nepřispívá NIČÍM - i lexikografův návrh musí
        # zmizet, ne jen číselný důkaz, jinak by formulář nabízel tlačítko
        # "použít návrh" pro nález z jiného draftu/korpusu/prahů.
        lex_suggestion = finding.get("navrh") if (finding and fresh) else None

        # Existence řádku v guide.json JE lidské rozhodnutí, i s prázdným cz -
        # u postavy s render="keep" je prázdné cz platný, uložený stav
        # (validate() vyžaduje neprázdné cz jen při render="translate";
        # u míst/termínů to samo o sobě znamená, že řádek prošel validací
        # s neprázdným cz, takže se tu nic nemění). Bez tohohle by "guide >
        # reference" neplatilo bezpodmínečně - postava, o které už člověk
        # rozhodl "ponechat", by se čerstvým nálezem přepsala zpět na
        # provenance="reference".
        human_cz = (g.get("cz") or "").strip()
        human_decided = bool(g)
        # Předvyplnění je gatované na classification `confirmed`/`weak`
        # NEZÁVISLE na tom, co `load_reference` už validovalo - obrana do
        # hloubky. `load_reference` odmítne `reference.json`, kde `cz`
        # nesedí s `classification`, ale kdyby se sem někdy dostal nález
        # jinou cestou (budoucí volající, který `load_reference` obejde),
        # nesmí se slepě spolehnout na `finding["cz"]`.
        finding_confirmed_or_weak = bool(finding) and finding.get("classification") in ("confirmed", "weak")
        ref_cz = (finding.get("cz") or "") if (fresh and finding_confirmed_or_weak) else ""
        cz = human_cz if human_decided else (ref_cz or "")
        provenance = "human" if human_decided else ("reference" if ref_cz else "none")

        # Přítomnost klíče v guide.json rozhoduje, ne pravdivostní hodnota -
        # `"aliases": []` je platné lidské rozhodnutí "smaž všechny aliasy" a
        # `or d.get(...)` by ho tiše přepsalo zpět draftovou verzí. Stejně tak
        # uložená poznámka (i prázdná) je rozhodnutí, které draft nesmí přebít.
        aliases = g["aliases"] if "aliases" in g else (d.get("aliases") or [])
        note = g["note"] if "note" in g else (d.get("note") or "")

        row = {key_field: name, "cz": cz, "note": note,
               "aliases": aliases,
               "provenance": provenance,
               "scout_suggestion": scout_suggestion,
               "lexicographer_suggestion": lex_suggestion}
        if is_character:
            human_render = g.get("render")
            ref_render = "keep" if ref_cz else None
            row["render"] = human_render or ref_render or ""
            row["scout_suggestion"] = d.get("suggested") or None
        if finding:
            row["reference"] = _reference_block(finding, fresh, cz)
        out.append(row)

    for key, g in g_map.items():
        if key in done:
            continue
        # provenance="human", jakmile řádek v guide.json existuje - stejné
        # pravidlo jako u položek spárovaných s draftem výš (human_decided).
        # `g.get("cz")` samo o sobě by u postavy s render="keep" a prázdným
        # cz (platný, uložený stav) mylně dalo "none".
        row = {key_field: g.get(key_field, ""), "cz": g.get("cz") or "",
               "note": g.get("note") or "", "aliases": g.get("aliases") or [],
               "provenance": "human",
               "scout_suggestion": None, "lexicographer_suggestion": None}
        if is_character:
            row["render"] = g.get("render") or ""
        out.append(row)
    return out


def merge_sources(draft: dict, guide_data: dict, reference=None, *, cfg=None) -> dict:
    """Podklad pro review UI ze tří zdrojů. Přednost: guide > reference > draft.

    Glosářová pole (`cz`, `render`) se předvyplňují JEN z doložené reference -
    scoutův ani lexikografův odhad se do nich nedostane. Oba návrhy se drží
    odděleně, aby je formulář mohl nabídnout tlačítkem.
    """
    draft = draft or {}
    guide_data = guide_data or {}
    ref_index = _reference_index(reference)
    fresh = _is_fresh(reference, draft, cfg)

    characters = _merge_section(draft, guide_data, ref_index, fresh,
                                "characters", "name_en", is_character=True)
    places = _merge_section(draft, guide_data, ref_index, fresh, "places", "name_en")
    terms = _merge_section(draft, guide_data, ref_index, fresh, "terms", "term_en")

    g_rel = {relationship_key(r.get("a", ""), r.get("b", "")): r
             for r in (guide_data.get("relationships") or [])}
    out_rel, done_rel = [], set()
    for d in (draft.get("relationships") or []):
        k = relationship_key(d.get("a", ""), d.get("b", ""))
        g = g_rel.get(k, {})
        done_rel.add(k)
        # Vztahy a styl těžba nepokrývá, takže scoutův návrh zůstává předvyplněný;
        # sekce vztahů to vyvažuje zaškrtnutím "zkontrolováno" před uložením.
        out_rel.append({"a": d.get("a", ""), "b": d.get("b", ""),
                        "address": g.get("address") or d.get("suggested") or ""})
    for k, g in g_rel.items():
        if k not in done_rel:
            out_rel.append({"a": g.get("a", ""), "b": g.get("b", ""),
                            "address": g.get("address") or ""})

    return {"characters": characters, "places": places, "terms": terms,
            "relationships": out_rel,
            "style": guide_data.get("style") or draft.get("style_notes", "") or "",
            "rules": guide_data.get("rules") or [],
            "must_decide": draft.get("must_decide") or []}


def merge_draft_and_guide(draft: dict, guide_data: dict) -> dict:
    """Tenký obal kvůli zpětné kompatibilitě."""
    return merge_sources(draft, guide_data, None)


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
