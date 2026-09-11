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
    výjimku - `pipeline._run_critic` ji zachytí a podle VOLAJÍCÍHO kontextu
    z toho udělá RŮZNÝ výsledek (kolo 15 NIT - upřesňuje starší tvrzení,
    co počítalo jen s `run`): u `run` (`_cmd_run`) kapitola skončí
    `flagged` (nepředpokládat pass); u `polish` (`_polish_one_chapter`,
    volá se tu STEJNÁ `pipeline._run_critic`) `critic_failed=True` vede
    k `outcome="rejected"` BEZ jakékoli změny statusu kapitoly v DB -
    kapitola zůstává přesně tak, jak byla PŘED stylizací."""
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
        # Kolo 7 BLOCKING: `extract_json` slibuje "-> dict", ale za běhu
        # vrátí cokoli platné JSON - top-level pole/string/číslo by na
        # `data.get(...)` spadlo na AttributeError MIMO tenhle retry cyklus
        # (žádný z předchozích `except` bloků ho nechytá).
        if not isinstance(data, dict):
            last_error = ValueError(
                f"Kritik vrátil {type(data).__name__} na nejvyšší úrovni, ne objekt.")
            continue
        raw_findings = data.get("findings")
        # Kolo 4 nález: `data.get("findings")` může být cokoli platné JSON
        # (string, číslo, ...), ne jen seznam/None. `for f in "text"` by
        # iterovalo PO ZNACÍCH a `_to_finding` by na jednom znaku spadlo na
        # AttributeError místo srozumitelné chyby - vynutit typ explicitně.
        if raw_findings is not None and not isinstance(raw_findings, list):
            last_error = ValueError(
                f"Kritik vrátil 'findings' jako {type(raw_findings).__name__}, ne seznam.")
            continue
        # Kolo 7 BLOCKING: TICHÉ přeskočení nedict položek (`isinstance`
        # filtr) by nechalo `{"verdict": "pass", "findings": [1]}` projít
        # jako čistý výsledek (findings=[1] → po filtru prázdné, verdikt
        # "pass" sedí) - ale [1] je zjevně poškozená odpověď, ne "žádný
        # nález". Jakákoli nedict položka = celá odpověď je nedůvěryhodná.
        if raw_findings and any(not isinstance(f, dict) for f in raw_findings):
            last_error = ValueError(
                "Kritik vrátil 'findings' s položkou, co není objekt.")
            continue
        # Kolo 9 IMPORTANT: existující `_to_finding` (v `critic.py`, mimo
        # tenhle plán) tiše DOMÝŠLÍ chybějící/neplatné `severity`/`type` na
        # bezpečné "minor"/"fidelity" - `{"severity": 0}` by tak prošlo jako
        # neškodný "minor" nález (0 je falsy → `0 or "minor"` = "minor"),
        # i když jde o zjevně poškozenou položku, ne o "žádná závažnost
        # neuvedena". Stejná filozofie jako o pár řádků výš (nedict položka
        # = celá odpověď nedůvěryhodná) - položka se špatným enum polem
        # celou odpověď zneplatní, místo aby se tiše "opravila" na bezpečnou
        # hodnotu, kterou `_to_finding` samo nabízí jako fallback (ten
        # zůstává, ale díky týhle kontrole ho `review()` už reálně
        # nevyužije).
        if raw_findings and any(
                f.get("severity") not in ("critical", "minor")
                or f.get("type") not in ("fidelity", "fluency", "register")
                for f in raw_findings):
            last_error = ValueError(
                "Kritik vrátil 'findings' s položkou s neplatným "
                "'severity'/'type'.")
            continue
        # Kolo 5 IMPORTANT: `verdict` mimo "pass"/"revise" (chybí, jiný typ,
        # nesmyslná hodnota) se dřív tiše bralo jako "ne revise", takže
        # prázdné/poškozené `findings` + neplatný verdikt vyšly jako klidné
        # "pass". Modul sám tvrdí "rozbitý výstup vede k retry a výjimce" -
        # tohle je přesně ten rozbitý případ, který tvrzení nesplňovalo.
        if data.get("verdict") not in ("pass", "revise"):
            last_error = ValueError(
                f"Kritik vrátil neplatný verdikt: {data.get('verdict')!r}.")
            continue
        findings = [_to_finding(f) for f in (raw_findings or [])]
        # Rozpor verdikt vs. findings (kolo 3 plan-consensus nález): model
        # řekl "revise", ale nedal nález, co by to samo vynutilo -
        # `has_revise_triggers`/`_polish_rejected` by o tom nevěděly a
        # nekonzistentní odpověď by tiše prošla jako čistá. Radši synteticky
        # vynutit revizi, než nechat nesoulad projít.
        if data.get("verdict") == "revise" and not any(
                f["action"] == "revise" for f in findings):
            findings.append({
                "source": "critic", "type": "fidelity", "severity": "critical",
                "action": "revise", "term_id": None, "expected": None,
                "actual": None, "cz_excerpt": None,
                "issue": "Kritik označil verdikt jako 'revise', ale nevrátil "
                        "žádný nález odpovídající závažnosti - rozpor v "
                        "odpovědi modelu.",
                "suggestion": None})
        return findings
    raise last_error
