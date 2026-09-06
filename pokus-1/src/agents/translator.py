"""
Translator agent - přeloží úsek textu do češtiny podle glosáře a style guide.
Nedělá vlastní kontrolu kvality - to je úloha kritika (oddělený kontext).

Výstup ZÁMĚRNĚ není JSON obalující celý překlad: dlouhý literární text plný
uvozovek a nových řádků JSON snadno rozbije a useknutí na max_tokens by zničilo
celou kapitolu. Místo toho model vrací překlad jako čistý text a malá metadata
(nové termíny, otevřené otázky) v JSON bloku za oddělovačem - metadata jsou
krátká, takže se neusekávají.
"""
import json
import re
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from src import llm_client
from src.glossary import glossary_as_prompt_block, style_guide_as_prompt_block

TRANSLATION_MARKER = "===PREKLAD==="
METADATA_MARKER = "===METADATA==="

SYSTEM_PROMPT = f"""Jsi profesionální literární překladatel z angličtiny do češtiny.
Překládáš román žánru urban fantasy. Tvým úkolem je vytvořit plynulý, přirozený
český text, který zachovává tón, humor a hlas vypravěče originálu - NE doslovný
strojový převod.

Pravidla:
- Dodržuj glosář jmen a termínů, pokud je uveden - jsou závazná.
- Dodržuj pravidla stylu (style guide), pokud jsou uvedena.
- Pokud narazíš na jméno, místo nebo termín, který NENÍ v glosáři a je nejednoznačný
  (mohl by se přeložit více způsoby, nebo je kulturně specifický), nezastavuj se -
  přelož podle svého nejlepšího úsudku, ale zaznamenej to jako otevřenou otázku.
- Zachovej odstavcovou strukturu originálu.

Odpověz PŘESNĚ v tomto formátu, nic před ani za:

{TRANSLATION_MARKER}
<celý přeložený český text>
{METADATA_MARKER}
{{"new_terms": [{{"term_en": "...", "cz": "...", "note": "...", "type": "name|place|term"}}], "open_questions": ["otázka 1"]}}

new_terms uváděj jen pro termíny, které nejsou v dodaném glosáři.
open_questions uváděj jen pro skutečně nejednoznačné případy, ne rutinně.
Za {METADATA_MARKER} musí být platný JSON na jednom řádku nebo bloku, nic jiného."""


def translate_chunk(text_en: str, glossary: dict, style_guide: dict) -> dict:
    user_content = f"""GLOSÁŘ (závazné):
{glossary_as_prompt_block(glossary)}

STYLE GUIDE (závazné):
{style_guide_as_prompt_block(style_guide)}

TEXT K PŘEKLADU:
{text_en}"""

    raw = llm_client.call(
        model=config.MODEL_TRANSLATOR,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        max_tokens=config.MAX_TOKENS_TRANSLATOR,
    )
    return _parse(raw)


def _parse(raw: str) -> dict:
    """Rozdělí odpověď na překlad (čistý text) a metadata (JSON).
    Když model formát úplně nedodrží, degraduje rozumně - překlad je důležitější
    než metadata, takže radši vrátí překlad bez termínů než aby spadl."""
    text = raw.strip()
    if TRANSLATION_MARKER in text:
        text = text.split(TRANSLATION_MARKER, 1)[1]

    if METADATA_MARKER in text:
        translation, meta_raw = text.split(METADATA_MARKER, 1)
    else:
        translation, meta_raw = text, ""

    translation = translation.strip()
    new_terms, open_questions = [], []

    meta_raw = meta_raw.strip()
    if meta_raw:
        m = re.search(r"\{.*\}", meta_raw, re.DOTALL)
        if m:
            try:
                meta = json.loads(m.group(0))
                new_terms = meta.get("new_terms") or []
                open_questions = meta.get("open_questions") or []
            except json.JSONDecodeError:
                pass  # metadata ztracena, překlad zůstává

    if not translation:
        raise ValueError(f"Translator nevrátil žádný překlad. Surová odpověď:\n{raw[:2000]}")

    return {"translation": translation, "new_terms": new_terms, "open_questions": open_questions}
