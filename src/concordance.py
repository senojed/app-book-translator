"""Deterministická kontrola konzistence termínů - BEZ LLM.

Nahrazuje "terminology" a "cross-reference" agenty z pokusu 1. Vyčerpávající
hledání řetězců je přesně to, v čem je kód dobrý a LLM špatný.

Co umí:
- `check_chapter` - nálezy v jedné kapitole: leak (nepřeložený termín),
  inconsistency (jiný tvar než kanonický), omission (termín v EN, v CZ nic).
- `build_mentions` - pozorovací záznam výskytů pro tabulku `term_mentions`.
- `check_drift` - rozjezd tvarů napříč kapitolami.

České skloňování v1 neřeší lemmatizací, ale porovnáním na kmeni (slovo bez
posledních 1-3 znaků). Falešné nálezy jsou očekávané - končí jako otázka pro
člověka, ne jako tvrdý fail.

Modul je čistá logika: glosář dostává jako list dictů, DB nezná.
"""
import re
from dataclasses import dataclass

_PUNCT = ".,;:!?\"')"


def stem(word: str) -> str:
    """Hrubý kmen pro porovnání českých tvarů. Bez lemmatizace, v1."""
    w = word.rstrip(_PUNCT).lower()
    if len(w) > 5:
        return w[:-3]
    if len(w) > 3:
        return w[:-2]
    return w


def form_key(form: str) -> str:
    """Normalizace víceslovného tvaru: 'Bílá radě' i 'Bílá rada' → 'bí ra'."""
    return " ".join(stem(w) for w in (form or "").split())


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text or "", re.UNICODE)


def find_form_occurrences(text: str, form: str) -> list[str]:
    """Najde v textu výskyty daného tvaru (na kmeni, po slovech).
    Vrací skutečné úseky textu, ne hledaný tvar - zachytí i skloňování."""
    f_stems = [stem(w) for w in (form or "").split() if w.strip()]
    if not f_stems:
        return []
    toks = _tokens(text)
    t_stems = [stem(w) for w in toks]
    n = len(f_stems)
    out = []
    for i in range(len(toks) - n + 1):
        if t_stems[i:i + n] == f_stems:
            out.append(" ".join(toks[i:i + n]))
    return out


def contains_form(text: str, form: str) -> bool:
    return bool(find_form_occurrences(text, form))


def _contains_surface(text: str, surface: str) -> bool:
    """Přesná shoda povrchu (word-boundary, case-insensitive) - pro EN v CZ textu."""
    if not surface:
        return False
    return re.search(r"\b" + re.escape(surface) + r"\b", text or "",
                     re.IGNORECASE | re.UNICODE) is not None


@dataclass
class Mention:
    term_id: str
    cz_form: str | None
    scene_idx: int | None
    source: str          # rendered | detected | omission


def _finding(*, source, type, severity, action, term_id=None, expected=None,
             actual=None, cz_excerpt=None, issue="", suggestion=None) -> dict:
    """Sjednocený tvar nálezu (viz spec §Finding). Kritik vrací totéž."""
    return {"source": source, "type": type, "severity": severity, "action": action,
            "term_id": term_id, "expected": expected, "actual": actual,
            "cz_excerpt": cz_excerpt, "issue": issue, "suggestion": suggestion}


def _surfaces(term: dict) -> list[str]:
    return [term.get("canonical_en", "")] + list(term.get("aliases") or [])


def examined_terms(en_text: str, glossary: list[dict],
                   rendered_terms: list[dict]) -> list[dict]:
    """Zkoumáme jen termíny, které jsou v EN textu nebo je translator ohlásil.
    Ne celý glosář - ten může mít stovky řádků."""
    wanted_ids = {rt.get("term_id") for rt in (rendered_terms or [])}
    out = []
    for t in glossary or []:
        if t.get("term_id") in wanted_ids:
            out.append(t)
            continue
        if any(_contains_surface(en_text, s) for s in _surfaces(t) if s):
            out.append(t)
    return out


def _allowed_keys(term: dict) -> set:
    forms = [term.get("cz", "")] + list(term.get("accepted_alt") or [])
    # Alias je platný český tvar JEN pokud se jméno vůbec nepřekládá (cz ==
    # canonical_en doslova, typicky render="keep") - v próze je zkrácené
    # jméno po prvním uvedení běžné ("Donald Morgan" → dál jen "Morgan").
    # U přeloženého jména/termínu by anglický alias tiše obešel kontrolu -
    # proto se přidává jen v týhle podmínce, ne vždy.
    canonical = (term.get("canonical_en") or "").strip().lower()
    cz = (term.get("cz") or "").strip().lower()
    if cz and cz == canonical:
        forms += list(term.get("aliases") or [])
    return {form_key(f) for f in forms if f}


def _term_mentions(term: dict, cz_text: str, rendered_terms: list[dict]) -> list[Mention]:
    tid = term.get("term_id")
    mentions: list[Mention] = []
    seen_keys = set()

    # 1) co ohlásil translator - ale jen pokud to v CZ textu opravdu je
    for rt in (rendered_terms or []):
        if rt.get("term_id") != tid:
            continue
        form = (rt.get("cz_as_used") or "").strip()
        if not form or form not in cz_text:
            continue
        mentions.append(Mention(tid, form, rt.get("scene_idx"), "rendered"))
        seen_keys.add(form_key(form))

    # 2) co kód navíc najde v CZ textu (kanonický tvar / schválené alternativy)
    for form in [term.get("cz", "")] + list(term.get("accepted_alt") or []):
        if not form:
            continue
        for found in find_form_occurrences(cz_text, form):
            k = form_key(found)
            if k in seen_keys:
                continue
            seen_keys.add(k)
            mentions.append(Mention(tid, found, None, "detected"))

    if not mentions:
        mentions.append(Mention(tid, None, None, "omission"))
    return mentions


def build_mentions(en_text: str, cz_text: str, glossary: list[dict],
                   rendered_terms: list[dict]) -> list[Mention]:
    """Best-effort pozorovací záznam pro `term_mentions`. Signál, ne důkaz."""
    out: list[Mention] = []
    for term in examined_terms(en_text, glossary, rendered_terms):
        out.extend(_term_mentions(term, cz_text, rendered_terms))
    return out


def check_chapter(en_text: str, cz_text: str, glossary: list[dict],
                  rendered_terms: list[dict]) -> list[dict]:
    """Nálezy pro jednu kapitolu. Pipeline je routuje podle `action`."""
    findings: list[dict] = []
    for term in examined_terms(en_text, glossary, rendered_terms):
        tid = term.get("term_id")
        cz = term.get("cz", "")
        status = term.get("status", "candidate")
        canonical = term.get("canonical_en", "")

        # leak: termín se má překládat, ale EN podoba zůstala v českém textu
        if cz.strip().lower() != canonical.strip().lower():
            leaked = [s for s in _surfaces(term) if s and _contains_surface(cz_text, s)]
            if leaked:
                findings.append(_finding(
                    source="concordance", type="leak", severity="critical",
                    action="revise", term_id=tid, expected=cz, actual=leaked[0],
                    issue=f"Nepřeložený termín '{leaked[0]}' zůstal v českém textu.",
                    suggestion=f"Použij '{cz}'."))

        mentions = _term_mentions(term, cz_text, rendered_terms)
        allowed = _allowed_keys(term)
        reported = set()
        for m in mentions:
            if m.cz_form is None:
                findings.append(_finding(
                    source="concordance", type="omission", severity="minor",
                    action="note", term_id=tid, expected=cz, actual=None,
                    issue=f"Termín '{canonical}' je v originále, v překladu nenalezen "
                          "(parafráze nebo vynechávka).",
                    suggestion=None))
                continue
            k = form_key(m.cz_form)
            if k in allowed or k in reported:
                continue
            reported.add(k)
            approved = status in ("seeded", "approved")
            findings.append(_finding(
                source="concordance", type="inconsistency",
                severity="critical" if approved else "minor",
                action="revise" if approved else "question",
                term_id=tid, expected=cz, actual=m.cz_form,
                issue=f"Termín '{canonical}' přeložen jako '{m.cz_form}', "
                      f"kanonicky je '{cz}'.",
                suggestion=f"Sjednoť na '{cz}'." if approved else None))
    return findings


def check_drift(mentions: list[dict]) -> list[dict]:
    """Napříč kapitolami: dva zjevně různé kmeny u jednoho termínu = drift."""
    by_term: dict = {}
    for m in mentions or []:
        form = m.get("cz_form")
        if not form:
            continue
        by_term.setdefault(m.get("term_id"), []).append(m)

    out = []
    for tid, rows in by_term.items():
        groups: dict = {}
        for r in rows:
            groups.setdefault(form_key(r["cz_form"]), []).append(r)
        if len(groups) < 2:
            continue
        formy = [g[0]["cz_form"] for g in groups.values()]
        kapitoly = sorted({r.get("chapter_idx") for r in rows
                           if r.get("chapter_idx") is not None})
        out.append({"term_id": tid, "formy": formy, "kapitoly": kapitoly})
    return out
