"""Orchestrace těžby: korpus + lexikograf → nálezy.

Jediné místo, které drátuje hledání a agenta dohromady. Nezná databázi ani
glosář - výsledek jen vrací; zápis dělá volající.
"""
import hashlib
import json
import math
import os
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


SCHEMA_VERSION = 1
_SECTIONS = {"characters", "places", "terms"}
_CLASSES = {"confirmed", "weak", "evidence_only", "proposed", "not_attested",
            "unresolved"}
_SOURCES = {"kept", "proposed", "none"}
_REQUIRED = ("id", "section", "surface", "cz", "classification",
             "primary_attested", "navrh", "hits", "books", "per_form",
             "cooccurrence", "matched_forms", "matched_cz", "source")


def _sha1(obj) -> str:
    return hashlib.sha1(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def draft_fingerprint(draft: dict) -> str:
    """Klíče, aliasy a poznámky. Poznámky proto, že se posílají lexikografovi
    a mění jeho návrh - draft se stejnými klíči, ale jinými poznámkami, může
    dát jiný výsledek."""
    rows = []
    for section, key in (("characters", "name_en"), ("places", "name_en"),
                         ("terms", "term_en")):
        for item in draft.get(section) or []:
            rows.append([section, item.get(key) or "",
                         sorted(item.get("aliases") or []), item.get("note") or ""])
    return _sha1(sorted(rows))


def thresholds_fingerprint(cfg) -> str:
    """Jen hodnoty, které ovlivňují důkaz - ne cesty, model ani velikost dávky."""
    return _sha1([cfg.REFERENCE_MIN_HITS, cfg.REFERENCE_MIN_BOOKS,
                  cfg.REFERENCE_MIN_CORPUS_BOOKS, cfg.REFERENCE_COOCCUR_RATIO])


def corpus_fingerprint(root: str):
    """None = kořen není dostupný nebo se nedá přečíst; volající to musí brát
    jako 'nevím'.

    POZOR: stat()uje aktuální filesystém. Pro otisk toho, co bylo SKUTEČNĚ
    vytěženo, použij `manifest_fingerprint(corpus.manifest)` - `corpus`
    nese manifest zachycený PŘI NAČTENÍ, ne v okamžiku volání."""
    if not root or not os.path.isdir(root):
        return None
    try:
        # os.listdir/os.stat uvnitř build_manifest můžou selhat i po úspěšném
        # isdir() - soubor mezitím zmizel, oprávnění, síťový disk. Volá se
        # mimo jiné z guide._is_fresh() uvnitř GET /api/guide - nezachycená
        # výjimka by tam znamenala HTTP 500 místo "nevím, ber jako nečerstvé".
        return _sha1(reference.build_manifest(root))
    except OSError:
        return None


def manifest_fingerprint(manifest: dict) -> str:
    """Otisk konkrétního manifestu, ne aktuálního stavu disku. `_cmd_reference`
    ho volá na `corpus.manifest` (zachycený při `load_corpus`/`load_cache`) -
    kdyby místo toho volal `corpus_fingerprint(root)` až PO těžbě (co může
    trvat minuty kvůli volání modelu), zapsal by otisk aktuálního disku, ne
    toho, ze kterého nálezy skutečně vzešly. Změní-li se EPUB během běhu,
    `review` by pak nálezy z dřívějšího textu tiše označil za čerstvé."""
    return _sha1(manifest)


def write_reference(findings, path, run_id, fingerprint, source_root) -> None:
    """Nahrazuje soubor celý. Žádné slévání s předchozím - selhání je atomické,
    takže se sem dostane jen kompletní výsledek."""
    import tempfile
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Unikátní dočasný soubor ve stejné složce (kvůli os.replace na stejném
    # svazku), ne pevné jméno `path + ".tmp"" - souběžný `reference` běh by
    # se jinak přepisoval navzájem.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"schema_version": SCHEMA_VERSION, "run_id": run_id,
                       "source_root": source_root, "fingerprint": fingerprint,
                       "findings": findings}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


# Očekávaný typ každého pole - validace kontroluje TVAR, ne jen přítomnost.
# Bez toho by poškozený `reference.json` (např. `hits` jako string) prošel
# do `review` a rozbil formulář na frontendu s méně srozumitelnou chybou.
_FIELD_TYPES = {
    "id": str, "section": str, "surface": str, "classification": str,
    "primary_attested": bool, "hits": int, "books": list, "per_form": dict,
    "cooccurrence": list, "matched_forms": list, "source": str,
    "cz": (str, type(None)), "navrh": (str, type(None)),
    "matched_cz": (str, type(None)),
}


def _is_strict_int(v) -> bool:
    """`isinstance(True, int)` je v Pythonu `True` - bez vyloučení `bool` by
    `hits: true` prošlo jako platný počet výskytů."""
    return isinstance(v, int) and not isinstance(v, bool)


def _finding_is_well_formed(f) -> bool:
    if not isinstance(f, dict) or any(k not in f for k in _REQUIRED):
        return False
    for key, types in _FIELD_TYPES.items():
        # "hits" je jediné pole, kde by isinstance(x, int) tiše přijalo bool
        # (isinstance(True, int) je True v Pythonu) - ostatní typy tu díru nemají.
        if key == "hits":
            if not _is_strict_int(f[key]):
                return False
            continue
        if not isinstance(f[key], types):
            return False
    if any(not _is_strict_int(b) for b in f["books"]):
        return False
    if any(not _is_strict_int(b) for b in f["cooccurrence"]):
        return False
    if any(not isinstance(m, str) for m in f["matched_forms"]):
        return False
    if not isinstance(f["per_form"], dict):
        return False
    for form, row in f["per_form"].items():
        if not isinstance(form, str) or not isinstance(row, dict):
            return False
        if not _is_strict_int(row.get("hits")) or not isinstance(row.get("books"), list):
            return False
        if any(not _is_strict_int(b) for b in row["books"]):
            return False
        # case_exact chybí u starších záznamů jen přes migraci schématu (žádná
        # tu není), takže se vyžaduje a musí to být SKUTEČNÝ bool.
        if not isinstance(row.get("case_exact"), bool):
            return False
    if f["section"] not in _SECTIONS or f["classification"] not in _CLASSES \
            or f["source"] not in _SOURCES:
        return False
    # Sémantická konzistence napříč poli, ne jen typ: `resolve()` nikdy
    # nevyrobí `cz` mimo confirmed/weak ani `navrh` mimo proposed/not_attested
    # (viz classify() - cz se plní jen v té větvi, navrh jen tehdy, když je
    # model vrátil). Bez týhle kontroly by poškozený/ručně upravený soubor
    # s `classification="proposed", cz="Vymyšleno"` prošel jako platný a
    # `_merge_section` by ho vzal jako doložené - přesně to, co má invariant
    # "odhad se netváří jako důkaz" zabránit.
    if (f["cz"] is not None) != (f["classification"] in ("confirmed", "weak")):
        return False
    if (f["navrh"] is not None) != (f["classification"] in ("proposed", "not_attested")):
        return False
    return True


_FINGERPRINT_KEYS = {"draft": str, "corpus": (str, type(None)), "thresholds": str}


def _fingerprint_is_well_formed(fp) -> bool:
    if not isinstance(fp, dict) or set(fp) != set(_FINGERPRINT_KEYS):
        return False
    return all(isinstance(fp[k], t) for k, t in _FINGERPRINT_KEYS.items())


def load_reference(path: str):
    """None u chybějícího, nečitelného i schématu neodpovídajícího souboru.
    Poškozený soubor nesmí shodit `review`."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        return None
    except ValueError:
        print(f"reference: {path} není platný JSON, ignoruji")
        return None
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        print(f"reference: {path} má neznámou verzi schématu, ignoruji")
        return None
    if not _is_strict_int(data.get("run_id")) or not isinstance(data.get("source_root"), str) \
            or not _fingerprint_is_well_formed(data.get("fingerprint")):
        print(f"reference: {path} má poškozená metadata, ignoruji")
        return None
    findings = data.get("findings")
    if not isinstance(findings, list):
        print(f"reference: {path} nemá seznam nálezů, ignoruji")
        return None
    seen = set()
    for f in findings:
        if not _finding_is_well_formed(f):
            print(f"reference: {path} má nález se špatným tvarem nebo typem pole, ignoruji")
            return None
        if f["id"] in seen:
            print(f"reference: {path} má duplicitní id {f['id']!r}, ignoruji")
            return None
        seen.add(f["id"])
    return data
