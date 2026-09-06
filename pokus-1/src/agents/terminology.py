"""
Terminologický agent - kontroluje použití termínů v přeloženém textu proti
glosáři a hlásí nekonzistence. Běží NEZÁVISLE na translatorovi - dostává jen
hotový CZ text, ne jeho zdůvodnění.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from src import llm_client
from src.glossary import glossary_as_prompt_block

SYSTEM_PROMPT = """Jsi terminologický kontrolor pro knižní překlad. Dostaneš glosář
závazných termínů a český text. Tvým jediným úkolem je zkontrolovat, že se
termíny z glosáře používají KONZISTENTNĚ a přesně tak, jak je glosář předepisuje.

Nehodnoť styl ani plynulost - jen terminologickou konzistenci.

Vrať POUZE JSON:
{
  "inconsistencies": [
    {"term_en": "...", "expected_cz": "...", "found_cz": "...", "context": "krátký úryvek"}
  ]
}
Pokud je vše v pořádku, vrať prázdný seznam."""


def check_terminology(cz_text: str, glossary: dict) -> dict:
    user_content = f"""GLOSÁŘ:
{glossary_as_prompt_block(glossary)}

ČESKÝ TEXT KE KONTROLE:
{cz_text}"""

    return llm_client.call_json(
        model=config.MODEL_TERMINOLOGY,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        max_tokens=config.MAX_TOKENS_TERMINOLOGY,
    )
