"""
Tenká vrstva nad Anthropic API. Jedno místo pro volání modelu.

Co navíc řeší:
- retry na rate-limit / chyby serveru: zajišťuje SDK (config.API_MAX_RETRIES)
- pozná useknutý výstup (stop_reason == "max_tokens"). U překladu je useknutý
  text tichá ztráta kapitoly, proto call() v tom případě vyhodí OutputTruncated.
  Agenti s malým JSON výstupem (call_json) useknutí tolerují a zkusí zparsovat,
  co přišlo.
- počítá spotřebované tokeny za celý běh procesu (get_usage) - pro odhad nákladů
- bezpečné parsování JSON odpovědí agentů (model má vrátit čistý JSON, tady se
  to čistí a parsuje s ošetřením chyb)
"""
import json
import re
from anthropic import Anthropic

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

_client = None

# Průběžný součet tokenů za celý běh procesu (ne perzistentní). Čte se přes get_usage().
_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}


class OutputTruncated(RuntimeError):
    """Model narazil na max_tokens - výstup je neúplný, nedá se použít."""


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "Chybí ANTHROPIC_API_KEY v prostředí. Nastav např.: export ANTHROPIC_API_KEY=sk-ant-..."
            )
        _client = Anthropic(
            api_key=config.ANTHROPIC_API_KEY,
            max_retries=config.API_MAX_RETRIES,
        )
    return _client


def _track_usage(usage) -> None:
    if usage is None:
        return
    _usage["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
    _usage["output_tokens"] += getattr(usage, "output_tokens", 0) or 0
    _usage["calls"] += 1


def get_usage() -> dict:
    """Součet tokenů od startu procesu (pro odhad nákladů v CLI)."""
    return dict(_usage)


def call(model: str, system: str, user_content: str, max_tokens: int, allow_truncated: bool = False) -> str:
    resp = _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    _track_usage(resp.usage)
    text = "".join(block.text for block in resp.content if block.type == "text")
    if resp.stop_reason == "max_tokens" and not allow_truncated:
        raise OutputTruncated(
            f"Model {model} narazil na max_tokens={max_tokens} - výstup je useknutý. "
            "Zvyš příslušný MAX_TOKENS_* v config.py, nebo zmenši vstup "
            "(CHAPTER_SPLIT_WORD_THRESHOLD)."
        )
    if resp.stop_reason == "max_tokens":
        print(f"  POZOR: odpověď modelu {model} byla useknutá na max_tokens={max_tokens}, "
              "parsuji jen část.")
    return text


def call_json(model: str, system: str, user_content: str, max_tokens: int) -> dict:
    """Volá model s instrukcí vrátit čistý JSON a parsuje výsledek.
    Pokud model přesto přidá markdown fence nebo text okolo, zkusí to očistit.
    Useknutý výstup toleruje (zkusí zparsovat, co přišlo) - u strukturovaných
    agentů je částečný výsledek lepší než pád celé kapitoly."""
    raw = call(model, system, user_content, max_tokens, allow_truncated=True)
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*|\s*```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # poslední pokus - najít první { ... poslední }
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Model nevrátil platný JSON. Surová odpověď:\n{raw[:2000]}")
