"""Lexikograf - navrhne zavedený český tvar termínu z české edice série.

Jeho návrh sám o sobě nemá váhu; teprve `reference_mine` ho ověří proti korpusu.
Agent proto nezná korpus, databázi ani soubory - dostane seznam, vrátí mapu.
"""
import config
from src.llm.client import OutputTruncated
from src.llm.parsing import extract_json

SYSTEM_PROMPT = """Jsi znalec české edice knižní série. Dostaneš seznam
anglických termínů a jmen a u každého vrátíš **zavedený český tvar**, jak se
používá v oficiálním překladu téhle série.

Vrať POUZE JSON, žádný text kolem:
{"proposals": [{"id": "<id z dotazu, doslova>", "cz": "<český tvar nebo null>"}]}

Pravidla:
- **Když termín neznáš, vrať `null`. Nehádej a nevymýšlej.** Tvůj návrh se bude
  ověřovat proti skutečnému textu překladů; vymyšlený tvar tam nebude a jen
  přidá práci člověku.
- `id` opiš přesně, jak přišlo v dotazu. Podle něj se odpověď páruje.
- Vrať položku pro **každé** `id` z dotazu, i kdyby byla `null`.
- `cz` je jen samotný tvar, žádná věta ani vysvětlení."""


def _format_items(items) -> str:
    lines = []
    for it in items:
        note = f"  (poznámka: {it['note']})" if it.get("note") else ""
        lines.append(f"- id={it['id']} | {it.get('kind', 'term')}: "
                     f"{it['term_en']}{note}")
    return "\n".join(lines)


def propose(items, client, *, model=None, max_tokens=None):
    """Vrací {id: cz | None}. Neúplná nebo rozbitá odpověď = ValueError."""
    if not items:
        return {}
    model = model or config.MODEL_LEXICOGRAPHER
    tokens = max_tokens or config.MAX_TOKENS_LEXICOGRAPHER
    user = ("Vrať zavedené české tvary pro tyto položky:\n\n"
            + _format_items(items))

    comp = None
    for attempt in range(2):
        comp = client.complete(system=SYSTEM_PROMPT, user=user,
                               max_tokens=tokens, model=model)
        if not comp.truncated:
            break
        tokens *= 2          # jeden pokus s dvojnásobným prostorem
    if comp.truncated:
        raise OutputTruncated(
            "Lexikograf vrátil useknutý výstup i po zvýšení max_tokens.")

    data = extract_json(comp.text)
    # extract_json má typový anotační slib "-> dict", ale za běhu vrací
    # cokoli, co je platný JSON - stačí, aby model vrátil pole nebo scalar
    # (nebo pole se špatnými řádky) a `.get`/`.get("id")` spadne na
    # AttributeError místo srozumitelného ValueError.
    if not isinstance(data, dict):
        raise ValueError(f"Odpověď lexikografa není JSON objekt: {type(data).__name__}")
    proposals = data.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("Odpověď lexikografa nemá pole 'proposals' jako seznam.")
    wanted = {it["id"] for it in items}
    out, seen = {}, set()
    for row in proposals:
        if not isinstance(row, dict):
            raise ValueError(f"Položka v 'proposals' není objekt: {row!r}")
        rid = row.get("id")
        if rid in seen:
            raise ValueError(f"Duplicitní id v odpovědi lexikografa: {rid!r}")
        seen.add(rid)
        if rid not in wanted:
            print(f"lexikograf: ignoruji cizí id {rid!r}")
            continue
        cz = row.get("cz")
        if cz is not None and not isinstance(cz, str):
            raise ValueError(f"cz u {rid!r} není řetězec ani null: {cz!r}")
        out[rid] = cz.strip() if isinstance(cz, str) and cz.strip() else None
    missing = wanted - set(out)
    if missing:
        # Chybějící položka není totéž co explicitní null - model na ni
        # zapomněl, výsledek je neúplný a běh selže atomicky.
        raise ValueError(
            f"Lexikografovi chybí {len(missing)} položek ve výstupu, výsledek "
            "je neúplný: " + ", ".join(sorted(missing)[:5]))
    return out
