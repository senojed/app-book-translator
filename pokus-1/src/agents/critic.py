"""
Kritik/redaktor agent - nezávisle hodnotí věrnost a plynulost překladu.
Dostává POUZE originál + CZ text, NIKDY zdůvodnění translatora - to je klíčové
pro to, aby hodnocení nebylo ovlivněné "vysvětlením" překladatele.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from src import llm_client

SYSTEM_PROMPT = """Jsi zkušený redaktor literárního překladu z angličtiny do češtiny.
Dostaneš originál a jeho český překlad. Nezávisle posuzuješ:
1. Věrnost - neztratil se/nezměnil se význam?
2. Plynulost - čte se to jako přirozená čeština, nebo je to kostrbaté/doslovné?
3. Registr - odpovídá tón postav a vypravěče originálu?

Buď přísný. Pokud najdeš problém, cituj konkrétní větu z CZ textu a napiš, proč
je problematická a jaký je závažnostní stupeň.

Vrať POUZE JSON:
{
  "verdict": "pass" | "needs_revision",
  "findings": [
    {"severity": "critical" | "minor", "cz_excerpt": "...", "issue": "...", "suggestion": "..."}
  ]
}
"pass" znamená žádné critical nálezy (minor nálezy jsou u prvního průchodu tolerovatelné)."""


def review(en_text: str, cz_text: str) -> dict:
    user_content = f"""ORIGINÁL (EN):
{en_text}

PŘEKLAD (CZ):
{cz_text}"""

    return llm_client.call_json(
        model=config.MODEL_CRITIC,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        max_tokens=config.MAX_TOKENS_CRITIC,
    )
