"""Orchestrace těžby: korpus + lexikograf → nálezy.

Jediné místo, které drátuje hledání a agenta dohromady. Nezná databázi ani
glosář - výsledek jen vrací; zápis dělá volající.
"""
import math
import unicodedata
from typing import TypedDict

from src import reference
from src.agents import lexicographer


class SurfaceItem(TypedDict):
    """Jedna položka draftu ke zpracování - vyrábí ji main.py z guide.draft.json."""
    id: str              # "{section}/{normalize_key(surface)}"
    section: str          # "characters" | "places" | "terms"
    surface: str
    aliases: list[str]
    note: str


class Finding(TypedDict):
    """Jeden nález těžby - tvoří obsah `reference.json["findings"]`."""
    id: str
    section: str
    surface: str
    cz: str | None
    classification: str   # confirmed|weak|evidence_only|proposed|not_attested|unresolved
    primary_attested: bool
    navrh: str | None
    hits: int
    books: list[int]
    per_form: dict
    cooccurrence: list[int]
    matched_forms: list[str]
    matched_cz: str | None
    source: str            # kept|proposed|none


def _finding(item, ev0, cz_ev, proposal, cooccurrence, classification, cz):
    source = ("kept" if classification in ("confirmed", "weak", "evidence_only")
              else "proposed" if classification in ("proposed", "not_attested")
              else "none")
    # Stejný důvod jako v classify(): ev0.per_form má klíče normalizované na
    # NFC (viz count_en_surface), lookup musí projít stejnou normalizací.
    nfc_surface = unicodedata.normalize("NFC", (item["surface"] or "").strip())
    return {
        "id": item["id"],
        "section": item["section"],
        "surface": item["surface"],
        "cz": cz,
        "classification": classification,
        "primary_attested": bool(ev0.per_form.get(nfc_surface, {}).get("hits")),
        "navrh": proposal,
        "hits": ev0.hits,
        "books": ev0.books,
        "per_form": ev0.per_form,
        "cooccurrence": sorted(cooccurrence),
        "matched_forms": ev0.matched_forms,
        "matched_cz": (item["surface"] if classification in ("confirmed", "weak")
                       else (proposal if cz_ev and cz_ev.hits else None)),
        "source": source,
    }


def classify(ev0, surface, proposal, cz_ev, cooccurrence, e_books, cfg) -> str:
    """Precedence tříd. Kroky 1 a 2 se týkají JEN způsobilých povrchů - bez
    toho by `stole` (79 výskytů, malé písmeno) spadlo do `weak`, `weak`
    předvyplňuje, a byla by zpět chyba, kvůli které tenhle aparát existuje.

    Prahy se počítají VÝHRADNĚ z primárního tvaru (`ev0.per_form[surface]`),
    ne z `ev0.hits`/`ev0.books` - ty jsou sjednocení přes aliasy. Bez tohohle
    rozlišení by hodně doložený alias mohl "protáhnout" primární tvar na
    `confirmed`, přestože ten samotný doložený vůbec není.

    `surface` se normalizuje na NFC stejně jako uvnitř `count_en_surface` -
    ta ukládá klíče `per_form` už normalizované. Bez odpovídající normalizace
    tady by NFD zápis (jiný, ale kanonicky stejný Unicode tvar) v `per_form`
    nenašel nic a položka by vyšla `weak`/`unresolved`, přestože důkaz
    existuje pod (jinak zapsaným) stejným klíčem."""
    surface = unicodedata.normalize("NFC", (surface or "").strip())
    primary = ev0.per_form.get(surface, {})
    primary_hits = primary.get("hits", 0)
    primary_books = primary.get("books", [])
    if ev0.confirm_eligible:
        if (primary_hits >= cfg.REFERENCE_MIN_HITS
                and len(primary_books) >= cfg.REFERENCE_MIN_BOOKS):
            return "confirmed"
        return "weak"
    if proposal:
        needed = max(1, math.ceil(cfg.REFERENCE_COOCCUR_RATIO * len(e_books)))
        if e_books and len(cooccurrence) >= needed:
            return "proposed"
        return "not_attested"
    if ev0.hits:
        return "evidence_only"
    return "unresolved"


def resolve(corpus, items, client_factory, cfg):
    """Vrací list[Finding]. Selhání kdekoli propaguje výjimku - běh je atomický."""
    stage0, pending = {}, []
    for item in items:
        ev = reference.count_en_surface(corpus, item["surface"], item.get("aliases") or [])
        stage0[item["id"]] = ev
        # Do stupně 1 jde jen to, co stupeň 0 nedoložil jako přímý důkaz
        # ponechání. Nezpůsobilý povrch (obecné slovo, jen alias) tam jde taky.
        if not ev.confirm_eligible:
            pending.append(item)

    proposals = {}
    size = max(1, cfg.REFERENCE_BATCH_SIZE)
    for start in range(0, len(pending), size):
        batch = pending[start:start + size]
        payload = [{"id": i["id"], "term_en": i["surface"],
                    "kind": i["section"], "note": i.get("note", "")} for i in batch]
        proposals.update(lexicographer.propose(
            payload, client_factory("lexicographer"),
            model=cfg.MODEL_LEXICOGRAPHER,
            max_tokens=cfg.MAX_TOKENS_LEXICOGRAPHER))

    findings = []
    for item in items:
        ev0 = stage0[item["id"]]
        proposal = proposals.get(item["id"])
        cz_ev = reference.count_cz_form(corpus, proposal) if proposal else None
        e_books = reference.books_with_en(corpus, item["surface"]) if proposal else set()
        cooccurrence = (e_books & set(cz_ev.books)) if cz_ev else set()
        classification = classify(ev0, item["surface"], proposal, cz_ev,
                                  cooccurrence, e_books, cfg)
        # Předvyplňuje se JEN doložené ponechání; návrhy nikdy.
        cz = item["surface"] if classification in ("confirmed", "weak") else None
        findings.append(_finding(item, ev0, cz_ev, proposal, cooccurrence,
                                 classification, cz))
    return findings
