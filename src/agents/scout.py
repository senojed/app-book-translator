"""Scout - pre-scan celé knihy před překladem.

Projede knihu a vrátí strukturovaná fakta (postavy, místa, termíny, vztahy,
styl) jako podklad pro překladatelský návod. Člověk je pak potvrdí v review UI.

Useknutý nebo neúplný výstup je TVRDÁ CHYBA, ne varování: částečný návod tiše
vynechá postavy a znehodnotí celý běh knihy.

Agent je bezstavová funkce (vstup, klient) → dict. Nezná DB ani soubory.
"""
import config
from src.guide import relationship_key
from src.llm.client import OutputTruncated
from src.llm.parsing import extract_json

_REQUIRED_KEYS = ("characters", "places", "terms", "relationships",
                  "style_notes", "must_decide")

SYSTEM_PROMPT = """Jsi literární scout. Dostaneš text knihy v angličtině a
připravíš podklad pro překlad do češtiny.

Vrať POUZE JSON (žádný text kolem, žádné ```), přesně v tomto tvaru:
{
  "characters":    [{"name_en": "...", "aliases": ["..."], "suggested": "keep|translate", "note": "..."}],
  "places":        [{"name_en": "...", "suggested_cz": "...", "note": "..."}],
  "terms":         [{"term_en": "...", "suggested_cz": "...", "note": "..."}],
  "relationships": [{"a": "...", "b": "...", "observed": "...", "suggested": "tyka|vyka"}],
  "style_notes":   "osoba vypravěče, čas, tón, rytmus vět, typické rysy",
  "must_decide":   [{"kind": "term|name|relationship|style", "scope_key": "...",
                     "question": "...", "default": "..."}]
}

Pravidla:
- "characters": vlastní jména postav. "keep" = ponechat anglicky, "translate" = přeložit.
- "terms": pojmy specifické pro tento svět (organizace, magie, artefakty).
- "relationships": dvojice, které spolu mluví; "suggested" = jestli si mají v
  češtině tykat nebo vykat, podle tónu jejich řeči.
- "must_decide": jen věci, kde bez rozhodnutí člověka hrozí nekonzistentní překlad.
- Nic nevynechávej kvůli délce. Když je toho moc, zkracuj poznámky, ne seznamy."""


def scan_book(book_text: str, client, *, model=None, max_tokens=None) -> dict:
    """Jedno volání na celou knihu. Useknutý výstup = OutputTruncated (fatal)."""
    model = model or config.MODEL_SCOUT
    max_tokens = max_tokens or config.MAX_TOKENS_SCOUT
    user = "Text knihy:\n\n" + book_text
    comp = client.complete(system=SYSTEM_PROMPT, user=user,
                           max_tokens=max_tokens, model=model)
    if comp.truncated:
        raise OutputTruncated(
            "Scout výstup useknutý na max_tokens. Částečný návod znehodnotí celý "
            "běh - zvyš MAX_TOKENS_SCOUT nebo použij `scan --chunked`.")
    data = extract_json(comp.text)
    missing = [k for k in _REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(f"Scout výstup nemá povinné klíče: {', '.join(missing)}")
    return data


def chunk_chapters(chapters, word_limit: int) -> list:
    """Greedy packing kapitol do chunků pod limitem slov. Deterministické."""
    chunks, current, current_words = [], [], 0
    for ch in chapters:
        raw = ch["raw_text"] if isinstance(ch, dict) else ch.raw_text
        n = len(raw.split())
        if current and current_words + n > word_limit:
            chunks.append("\n\n".join(current))
            current, current_words = [], 0
        current.append(raw)
        current_words += n
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def scan_chunks(chunks: list, client, **kw) -> dict:
    """Fallback pro knihu, která se nevejde do jednoho volání."""
    partials = [scan_book(c, client, **kw) for c in chunks]
    return merge_scout_facts(partials)


def _key(text: str) -> str:
    return (text or "").strip().casefold()


def _merge_entities(partials, section: str, name_key: str, kind: str,
                    suggest_key: str, must_decide: list) -> list:
    """Slije jednu sekci napříč chunky. Konflikt návrhu → must_decide."""
    merged: dict = {}
    order: list = []
    for p in partials:
        for item in (p.get(section) or []):
            k = _key(item.get(name_key, ""))
            if not k:
                continue
            if k not in merged:
                merged[k] = {name_key: item.get(name_key, ""),
                             "aliases": list(item.get("aliases") or []),
                             suggest_key: item.get(suggest_key) or "",
                             "note": item.get("note") or ""}
                order.append(k)
                continue
            cur = merged[k]
            for a in (item.get("aliases") or []):
                if a not in cur["aliases"]:
                    cur["aliases"].append(a)
            note = item.get("note") or ""
            if note and note not in cur["note"]:
                cur["note"] = "; ".join(x for x in [cur["note"], note] if x)
            new_s = item.get(suggest_key) or ""
            if new_s and cur[suggest_key] and new_s != cur[suggest_key]:
                must_decide.append({
                    "kind": kind, "scope_key": cur[name_key],
                    "question": f"Chunky se neshodly ({cur[suggest_key]} vs {new_s}). "
                                f"Co s '{cur[name_key]}'?",
                    "default": cur[suggest_key]})
            elif new_s and not cur[suggest_key]:
                cur[suggest_key] = new_s
    return [merged[k] for k in order]


def merge_scout_facts(partials: list) -> dict:
    """Slití dílčích výstupů z `--chunked` běhu. Bez dalšího LLM volání."""
    must_decide: list = []
    characters = _merge_entities(partials, "characters", "name_en", "name",
                                 "suggested", must_decide)
    places = _merge_entities(partials, "places", "name_en", "place",
                             "suggested_cz", must_decide)
    terms = _merge_entities(partials, "terms", "term_en", "term",
                            "suggested_cz", must_decide)

    rels: dict = {}
    rel_order: list = []
    for p in partials:
        for r in (p.get("relationships") or []):
            k = relationship_key(r.get("a", ""), r.get("b", ""))
            if k not in rels:
                rels[k] = {"a": r.get("a", ""), "b": r.get("b", ""),
                           "observed": r.get("observed") or "",
                           "suggested": r.get("suggested")}
                rel_order.append(k)
                continue
            cur = rels[k]
            obs = r.get("observed") or ""
            if obs and obs not in cur["observed"]:
                cur["observed"] = "; ".join(x for x in [cur["observed"], obs] if x)
            new_s = r.get("suggested")
            if new_s and cur["suggested"] and new_s != cur["suggested"]:
                cur["suggested"] = None
                must_decide.append({
                    "kind": "relationship", "scope_key": k,
                    "question": f"Tykají si {cur['a']} a {cur['b']}, nebo vykají? "
                                "Chunky se neshodly.",
                    "default": "vyka"})
            elif new_s and not cur["suggested"]:
                cur["suggested"] = new_s

    style_notes = "\n".join(
        s for s in ((p.get("style_notes") or "").strip() for p in partials) if s)

    seen_md = set()
    all_md = []
    for md in [m for p in partials for m in (p.get("must_decide") or [])] + must_decide:
        k = (md.get("kind"), md.get("scope_key"))
        if k in seen_md:
            continue
        seen_md.add(k)
        all_md.append(md)

    return {"characters": characters, "places": places, "terms": terms,
            "relationships": [rels[k] for k in rel_order],
            "style_notes": style_notes, "must_decide": all_md}
