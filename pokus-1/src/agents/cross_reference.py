"""
Cross-reference agent - periodicky (ne jen na konci) kontroluje celý glosář
a vzorek přeložených kapitol, hledá systematický drift - stejný termín přeložený
různě v různých částech knihy, který terminologický agent nemusel odchytit
v rámci jedné kapitoly (protože porovnává jen tu jednu kapitolu proti glosáři,
ne kapitoly navzájem).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from src import llm_client
from src.glossary import glossary_as_prompt_block

SYSTEM_PROMPT = """Jsi kontrolor konzistence dlouhého knižního překladu. Dostaneš
aktuální glosář a úryvky z více kapitol přeložené knihy. Hledáš PŘÍPADY, kdy se
stejné jméno/místo/termín objevuje přeložené různě na různých místech, i když
by podle glosáře mělo být jednotné - nebo případy, kdy glosář sám obsahuje
rozpor (dva různé záznamy pro fakticky stejnou entitu).

Vrať POUZE JSON:
{
  "drift_found": [
    {"term_en": "...", "variants_found": ["varianta1", "varianta2"], "chapters": [1, 5]}
  ]
}"""


def check_drift(glossary: dict, chapter_excerpts: dict[int, str]) -> dict:
    excerpts_block = "\n\n".join(
        f"--- Kapitola {idx} (úryvek) ---\n{text[:1500]}"
        for idx, text in chapter_excerpts.items()
    )
    user_content = f"""GLOSÁŘ:
{glossary_as_prompt_block(glossary)}

ÚRYVKY Z KAPITOL:
{excerpts_block}"""

    return llm_client.call_json(
        model=config.MODEL_CROSS_REF,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        max_tokens=config.MAX_TOKENS_CROSS_REF,
    )
