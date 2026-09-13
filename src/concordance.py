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


def _root_len(word: str) -> int:
    """Kolik znaků od začátku slova bereme jako neměnný kořen - stejná
    délková heuristika jako `stem()`, ale vrací DÉLKU (ne useknutý
    řetězec), aby šla aplikovat i na DRUHÉ slovo (viz `_root_matches`)."""
    n = len(word)
    if n > 5:
        return n - 3
    if n > 3:
        return n - 2
    return n


def _root_matches(candidate: str, canonical: str) -> bool:
    """Case-insensitive shoda na kořeni ODVOZENÉM Z `canonical`u, ne
    nezávisle z obou stran (pilot nálezy 2026-09-13 - Edinburgh/Red
    Court). Nezávislé odseknutí STEJNÉHO POČTU znaků z KAŽDÉ strany
    (dřívější `stem()` použitý na obou stranách) selhává, když se
    skloňovaná přípona liší délkou od nuly ('Edinburgh'->'Edinburghu':
    +1 znak; 'dvůr'->'dvora': +1 znak a navíc samohlásková alternace) -
    obě strany tak vyjdou jako jinak dlouhý "kmen" a přímé porovnání
    selže. Kořenová délka se proto bere VŽDY z kanonického tvaru a
    aplikuje se stejně na kandidáta."""
    canonical = canonical.rstrip(_PUNCT).lower()
    candidate = candidate.rstrip(_PUNCT).lower()
    n = _root_len(canonical)
    return candidate[:n] == canonical[:n]


def find_form_occurrences(text: str, form: str) -> list[str]:
    """Najde v textu výskyty daného tvaru (na kořeni odvozeném z `form`,
    po slovech). Vrací skutečné úseky textu, ne hledaný tvar - zachytí i
    skloňování (viz `_root_matches`)."""
    f_words = [w for w in (form or "").split() if w.strip()]
    if not f_words:
        return []
    toks = _tokens(text)
    n = len(f_words)
    out = []
    for i in range(len(toks) - n + 1):
        if all(_root_matches(toks[i + j], f_words[j]) for j in range(n)):
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


_SENTENCE_END_CHARS = ".!?"
_CLOSING_QUOTE_CHARS = "\"'”’"


def _is_sentence_initial(text: str, pos: int) -> bool:
    """True, pokud pozice `pos` v `text` navazuje na začátek věty (úplný
    začátek textu, nebo hned po tečce/vykřičníku/otazníku, případně přes
    zavírací uvozovku). Použito k potlačení nejednoznačné shody
    alias/jména, co je zároveň běžné anglické slovo psané s velkým
    písmenem JEN proto, že začíná větu (pilot nález 2026-09-13 - alias
    'Will' vs. modální 'Will you...')."""
    prefix = text[:pos].rstrip()
    if not prefix:
        return True
    ch = prefix[-1]
    if ch in _SENTENCE_END_CHARS:
        return True
    if ch in _CLOSING_QUOTE_CHARS and len(prefix) > 1 and prefix[-2] in _SENTENCE_END_CHARS:
        return True
    return False


def _confident_surface_match(text: str, surface: str) -> bool:
    """Přítomnost `surface` v `text` pro účely `examined_terms` (rozhoduje,
    jestli se termín vůbec bude zkoumat). U povrchu s velkým prvním
    písmenem (jméno/alias) vyžaduje SHODNÝ case (ne case-insensitive) A
    mimo začátek věty - jinak by běžné anglické slovo kolidující s
    aliasem (např. 'will'/'Will', pilot nález 2026-09-13 - Billy Borden)
    způsobilo falešné zkoumání termínu v kapitole, kde postava vůbec
    není. Neřeší 100 % - vzácný výskyt jména POUZE na začátku věty se tak
    nezachytí, ale to je přijatelné proti ceně falešných nálezů (a
    canonical_en/jiný povrch termín obvykle zachytí odjinud). Ostatní
    povrchy (malé první písmeno) zůstávají case-insensitive jako dřív -
    `_contains_surface` beze změny, používá ho i leak-kontrola výš, kde
    tahle nejednoznačnost není potvrzený problém."""
    if not surface:
        return False
    if not surface[0].isupper():
        return _contains_surface(text, surface)
    for m in re.finditer(r"\b" + re.escape(surface) + r"\b", text or "", re.UNICODE):
        if not _is_sentence_initial(text, m.start()):
            return True
    return False


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
        if any(_confident_surface_match(en_text, s) for s in _surfaces(t) if s):
            out.append(t)
    return out


def _forms_match(candidate: str, canonical: str) -> bool:
    """Porovná dva víceslovné tvary slovo po slovu, kořen VŽDY odvozen z
    `canonical` (viz `_root_matches`) - pro případy, kdy se nalezený tvar
    porovnává se ZNÁMÝM/referenčním tvarem (ne mezi dvěma nezávisle
    pozorovanými tvary navzájem, tam zůstává symetrický `form_key`)."""
    c_words = candidate.split()
    k_words = canonical.split()
    if not c_words or len(c_words) != len(k_words):
        return False
    return all(_root_matches(cw, kw) for cw, kw in zip(c_words, k_words))


def _allowed_forms(term: dict) -> list[str]:
    """Tvary, co se NEHLÁSÍ jako inconsistency, i když nejsou přesně
    kanonický `cz` (viz docstring k aliasům níž). Vrací syrové řetězce,
    ne klíče (pilot nález 2026-09-13 - Edinburgh/Red Court): shoda s
    nalezeným tvarem se dělá přes `_forms_match`, ne přes rovnost dvou
    NEZÁVISLE odvozených `form_key` - to selhávalo přesně stejně jako
    `find_form_occurrences` dřív (skloňovaná přípona jiné délky rozbila
    shodu dvou nezávisle useknutých kmenů)."""
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
    return [f for f in forms if f]


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

    # 2) co kód navíc najde v CZ textu (kanonický tvar / schválené alternativy
    #    / u NEPŘELOŽENÉHO jména - cz == canonical_en - i aliasy, protože
    #    postava může být v próze oslovována zkráceně/přezdívkou, aniž by
    #    se plný kanonický tvar v kapitole vůbec objevil (pilot nález
    #    2026-09-13 - Bjorn Bjorngunnarson/'Thorsen': dřív hlášeno jako
    #    omission, i když alias v textu reálně je). Stejná podmínka jako
    #    `_allowed_forms` - alias je platný ČESKÝ tvar jen u jména, co se
    #    vůbec nepřekládá.
    canonical_lc = (term.get("canonical_en") or "").strip().lower()
    cz_lc = (term.get("cz") or "").strip().lower()
    forms_to_find = [term.get("cz", "")] + list(term.get("accepted_alt") or [])
    if cz_lc and cz_lc == canonical_lc:
        forms_to_find += list(term.get("aliases") or [])
    for form in forms_to_find:
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
        allowed = _allowed_forms(term)
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
            if any(_forms_match(m.cz_form, a) for a in allowed):
                continue
            k = form_key(m.cz_form)
            if k in reported:
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
