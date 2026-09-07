"""Kritik - nezávislá revize překladu.

Dostane JEN anglický originál a český překlad. NE translatorovo zdůvodnění ani
jeho metadata - oddělený kontext je celý smysl: kritik tak chytá jiné chyby,
než by chytil translator sám na sobě.

Výstup je JSON (krátký, žádná próza) → převedeme na sjednocený tvar Finding.
"""
import config
from src.llm.client import OutputTruncated
from src.llm.parsing import extract_json

SYSTEM_PROMPT = """Jsi přísný redaktor literárního překladu z angličtiny do češtiny.
Dostaneš anglický originál kapitoly a její český překlad. Posuď věrnost
(nic nechybí, nic není přidáno, význam sedí), plynulost češtiny a rejstřík
(tón, oslovení, styl vypravěče).

Vrať POUZE JSON, žádný text kolem:
{"verdict": "pass" | "revise",
 "findings": [{"severity": "critical" | "minor",
               "type": "fidelity" | "fluency" | "register",
               "cz_excerpt": "krátký úryvek z překladu, kterého se nález týká",
               "issue": "co je špatně",
               "suggestion": "jak to opravit"}]}

"critical" = mění význam, chybí kus textu, nebo je to česky nečitelné.
"minor" = stylistická drobnost. Když je překlad v pořádku, vrať verdict "pass"
a prázdné findings. Nevymýšlej nálezy, abys nevypadal užitečně."""


def _to_finding(raw: dict) -> dict:
    severity = raw.get("severity") or "minor"
    if severity not in ("critical", "minor"):
        severity = "minor"
    return {
        "source": "critic",
        "type": raw.get("type") or "fidelity",
        "severity": severity,
        # critical spouští revizní smyčku, minor se jen zapíše do poznámek
        "action": "revise" if severity == "critical" else "note",
        "term_id": None,
        "expected": None,
        "actual": None,
        "cz_excerpt": raw.get("cz_excerpt"),
        "issue": raw.get("issue") or "",
        "suggestion": raw.get("suggestion"),
    }


def review(en_chapter: str, cz_chapter: str, client, *, model=None,
           max_tokens=None) -> list:
    """Vrátí nálezy. Useknutý i rozbitý výstup zkusí jednou znovu, pak vyhodí
    výjimku - pipeline z toho udělá `flagged` kapitolu (nepředpokládat pass)."""
    model = model or config.MODEL_CRITIC
    tokens = max_tokens or config.MAX_TOKENS_CRITIC
    user = (f"ANGLICKÝ ORIGINÁL:\n{en_chapter}\n\n"
            f"ČESKÝ PŘEKLAD:\n{cz_chapter}")

    last_error = None
    for attempt in range(2):
        comp = client.complete(system=SYSTEM_PROMPT, user=user,
                               max_tokens=tokens, model=model)
        if comp.truncated:
            last_error = OutputTruncated(
                "Kritik vrátil useknutý výstup i po zvýšení max_tokens.")
            tokens = tokens * 2      # druhý pokus s větším prostorem
            continue
        try:
            data = extract_json(comp.text)
        except ValueError as e:
            last_error = e
            continue
        return [_to_finding(f) for f in (data.get("findings") or [])]
    raise last_error
