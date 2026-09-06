"""
Glosář (jména, místa, ustálené termíny) a style guide jako perzistentní JSON.
Toto je sdílený stav mezi terminologickým agentem a translatorem - NE součást
kontextu jednoho promptu, ale explicitní soubor na disku, který se čte/zapisuje
při každé kapitole. Tím se konzistence udržuje i přes stovky kapitol.
"""
import json
import os


def _load(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_glossary(path: str) -> dict:
    # struktura: { "term_en": {"cz": "...", "note": "...", "type": "name|place|term"} }
    return _load(path, {})


def save_glossary(path: str, glossary: dict):
    _save(path, glossary)


def add_or_update_term(path: str, term_en: str, cz: str, note: str = "", term_type: str = "term"):
    glossary = load_glossary(path)
    glossary[term_en] = {"cz": cz, "note": note, "type": term_type}
    save_glossary(path, glossary)


def load_style_guide(path: str) -> dict:
    # struktura: volná - registr postav, tón vyprávění, rozhodnutí z kalibrace
    return _load(path, {"rules": [], "character_register": {}})


def save_style_guide(path: str, style_guide: dict):
    _save(path, style_guide)


def add_style_rule(path: str, rule: str):
    sg = load_style_guide(path)
    if rule not in sg["rules"]:
        sg["rules"].append(rule)
    save_style_guide(path, sg)


def glossary_as_prompt_block(glossary: dict) -> str:
    """Formátování glosáře pro vložení do promptu agentům."""
    if not glossary:
        return "(glosář je zatím prázdný)"
    lines = []
    for term_en, info in sorted(glossary.items()):
        lines.append(f"- {term_en} → {info['cz']}" + (f" ({info['note']})" if info.get("note") else ""))
    return "\n".join(lines)


def style_guide_as_prompt_block(style_guide: dict) -> str:
    rules = style_guide.get("rules", [])
    if not rules:
        return "(zatím žádná pravidla stylu)"
    return "\n".join(f"- {r}" for r in rules)
