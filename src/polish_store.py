"""JSON perzistence pro `polish` review workflow - drží schéma, validaci a
atomický zápis `data/polish.draft.json` a `data/polish.history.json`.
Izolováno od `main.py`/`polish_server.py` - obojí přes tenhle modul, nikdy
přímo `open()`/`json.load` na tyhle dva soubory (spec kolo 1, 3, 13)."""
import datetime as _dt
import json
import os
import threading
import uuid


class PolishStoreError(Exception):
    """Draft/history soubor je neplatný - poškozený JSON, chybějící pole,
    nebo poškozuje invariant (duplicitní idx apod.). Volající se NEsmí
    pokoušet pokračovat s částečně přečteným obsahem (spec kolo 3)."""


DRAFT_SCHEMA_VERSION = 1
HISTORY_SCHEMA_VERSION = 1
_VALID_HISTORY_SOURCES = ("polish-review", "polish-batch", "revert")

_DRAFT_CHAPTER_FIELDS = {
    "idx": int, "title": str, "cz_before": str, "styled": str,
    "revision_rounds": int, "reason_types": list, "findings": list,
    "rendered_terms": list, "draft_id": str,
}
_HISTORY_ENTRY_FIELDS = {
    "idx": int, "applied_at": str, "cz_before": str, "cz_after": str,
    "styled_by_codex": str, "title": str, "findings": list,
    "rendered_terms": list, "source": str, "draft_id": str,
}


def utc_now_z() -> str:
    """UTC čas s literálním `Z` sufixem (spec kolo 5/8 - `applied_at`/
    `generated_at` musí být VŽDY tenhle přesný tvar, ne jen "něco s
    offsetem", jinak "poslední záznam"/CAS řazení může vybrat špatnou
    hodnotu kolem přechodu letní/zimní čas)."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _is_utc_z(value) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        _dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def parse_z(value: str) -> "_dt.datetime":
    """Naparsuje `utc_now_z()`'s tvar zpět na `datetime` - "poslední"/řazení
    MUSÍ vždy porovnávat tohle, nikdy syrový řetězec (spec kolo 5/8):
    `datetime.isoformat()` VYNECHÁVÁ mikrosekundy, když jsou přesně 0, takže
    dva timestampy s a bez zlomkové části se lexikograficky NEřadí stejně,
    jako by se řadily chronologicky."""
    return _dt.datetime.fromisoformat(value[:-1] + "+00:00")


def _atomic_write_json(path: str, payload: dict) -> None:
    """tmp+`os.replace`, UNIKÁTNÍ tmp jméno na KAŽDÉ volání (spec kolo 16 -
    sdílená pevná tmp cesta by dvě souběžná volání mohla nechat navzájem
    poškodit interleaved zápisy). Selže-li COKOLI (zápis, `os.replace`),
    tmp soubor se ÚKLIDÍ (kolo 2 plán-ping-pongu IMPORTANT - dřív by po
    opakovaných diskových chybách zůstávaly viset citlivé drafty/historie
    v `data/` navždy). `flush()`+`os.fsync()` PŘED `os.replace` (kolo 6
    plán-ping-pongu NIT) - bez tohle `os.replace` chrání jen souběžné
    ČTENÁŘE před rozbitým souborem, ne výpadek napájení mezi zápisem a
    flushem OS bufferu na disk."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = os.path.join(
        directory, f".{os.path.basename(path)}."
                  f"{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _validate_record(record: dict, fields: dict, *, what: str) -> None:
    if not isinstance(record, dict):
        raise PolishStoreError(f"{what}: záznam není objekt.")
    for name, type_ in fields.items():
        if name not in record:
            raise PolishStoreError(f"{what}: chybí pole {name!r}.")
        value = record[name]
        # `isinstance(True, int)` je v Pythonu `True` (kolo 2
        # plán-ping-pongu IMPORTANT) - `bool` je PODTŘÍDA `int`, takže
        # `idx: true`/`revision_rounds: true` by jinak tiše prošlo jako
        # platné číslo (a `true` == `1`, `false` == `0` v aritmetice -
        # `idx=true` by potichu mířilo na kapitolu 1).
        if type_ is int and isinstance(value, bool):
            raise PolishStoreError(f"{what}: pole {name!r} nesmí být bool.")
        if not isinstance(value, type_):
            raise PolishStoreError(f"{what}: pole {name!r} má špatný typ.")
    if "idx" in fields and record["idx"] <= 0:
        raise PolishStoreError(f"{what}: idx musí být kladné celé číslo.")
    if "revision_rounds" in fields and record["revision_rounds"] < 0:
        raise PolishStoreError(f"{what}: revision_rounds nesmí být záporné.")


def _validate_str_list(value, field_name: str, what: str) -> None:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise PolishStoreError(f"{what}: {field_name!r} musí být seznam stringů.")


def _validate_dict_list(value, field_name: str, what: str) -> None:
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise PolishStoreError(f"{what}: {field_name!r} musí být seznam objektů.")


def _is_exact_schema_version(value, expected: int) -> bool:
    """`type(x) is int` NE `==`/`isinstance` (kolo 3 plán-ping-pongu
    IMPORTANT) - `True == 1` v Pythonu, takže `{"schema_version": true}`
    by jinak tiše prošlo jako platná verze 1."""
    return type(value) is int and value == expected


def _validate_draft_payload(path: str, data) -> None:
    """Sdílená validace pro `load_draft` (po čtení ze souboru) i
    `save_draft` (PŘED zápisem, kolo 1 plán-ping-pongu NIT - caller
    nemá jak vyrobit soubor, co by vlastní `load_draft` odmítl)."""
    if not isinstance(data, dict):
        raise PolishStoreError(f"{path}: kořen musí být objekt.")
    if not _is_exact_schema_version(data.get("schema_version"), DRAFT_SCHEMA_VERSION):
        raise PolishStoreError(f"{path}: neznámý/chybějící schema_version.")
    if not _is_utc_z(data.get("generated_at")):
        raise PolishStoreError(f"{path}: generated_at musí být UTC s koncovým "
                               "'Z' (kolo 5/8, kolo 1 plán-ping-pongu IMPORTANT - "
                               "dřív se validoval jen typ str, ne přesný tvar).")
    if not isinstance(data.get("codex_model"), str) or not data["codex_model"]:
        raise PolishStoreError(f"{path}: codex_model musí být neprázdný string.")
    chapters = data.get("chapters")
    if not isinstance(chapters, list):
        raise PolishStoreError(f"{path}: chapters musí být pole.")
    seen_idx = set()
    for ch in chapters:
        _validate_record(ch, _DRAFT_CHAPTER_FIELDS, what=f"{path}: draft záznam")
        # Neprázdný `draft_id` (kolo 11 plán-ping-pongu IMPORTANT - `_validate_
        # record`'s obecná `str` typová kontrola by prázdný `""` propustila,
        # což by rozbilo garantovanou identitu KONKRÉTNÍHO rozhodnutí, na
        # které se kept-original idempotence (kolo 9/10) spoléhá - VŠECHNY
        # prázdné `draft_id` by si navzájem "kolidovaly"). Přesný
        # `uuid.uuid4().hex` tvar se NEVYŽADUJE - testovací fixture čitelně
        # používají vlastní ID (`"draft-1"` apod.), jen identita/neprázdnost
        # je garance, na které skutečně závisí korektnost.
        if not ch["draft_id"]:
            raise PolishStoreError(f"{path}: draft_id nesmí být prázdný.")
        # Element-level typy (kolo 1 plán-ping-pongu IMPORTANT - dřív jen
        # `isinstance(x, list)`, obsah prvků nekontrolovaný):
        _validate_str_list(ch["reason_types"], "reason_types", f"{path}: draft záznam")
        _validate_dict_list(ch["findings"], "findings", f"{path}: draft záznam")
        _validate_dict_list(ch["rendered_terms"], "rendered_terms", f"{path}: draft záznam")
        if ch["idx"] in seen_idx:
            raise PolishStoreError(f"{path}: duplicitní idx {ch['idx']}.")
        seen_idx.add(ch["idx"])


def load_draft(path: str) -> dict:
    """Chybějící soubor = žádný draft (validní prázdný obal) - existující
    soubor se VŽDY plně validuje, poškozený/cizí obsah nikdy neprojde
    tiše (spec kolo 3)."""
    if not os.path.exists(path):
        # `generated_at`/`codex_model` musí projít VLASTNÍ validací
        # (kolo plán-ping-pongu review nález IMPORTANT) - `""` u obou
        # by `save_draft` rovnou odmítlo (`_is_utc_z("")` je `False`,
        # `codex_model` musí být neprázdný string), takže `post_discard`
        # na serveru startovaném BEZ draft souboru vůbec by po zavolání
        # `save_draft` (jen aby se prázdný seznam kapitol zapsal) dostal
        # matoucí 500 pro kapitolu, co nikdy nebyla ve frontě.
        return {"schema_version": DRAFT_SCHEMA_VERSION, "generated_at": utc_now_z(),
                "codex_model": "none", "chapters": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise PolishStoreError(f"{path}: neplatný JSON ({e}).") from e
    _validate_draft_payload(path, data)
    return data


def save_draft(path: str, data: dict) -> None:
    """Validuje STEJNÝMI pravidly jako `load_draft` PŘED zápisem (kolo 1
    plán-ping-pongu NIT)."""
    _validate_draft_payload(path, data)
    _atomic_write_json(path, data)


def is_draft_pending(path: str) -> bool:
    return bool(load_draft(path)["chapters"])


def _validate_history_payload(path: str, data) -> None:
    """Sdílená validace pro `load_history` i `save_history` - stejný
    princip jako `_validate_draft_payload` (kolo 1 plán-ping-pongu NIT)."""
    if not isinstance(data, dict):
        raise PolishStoreError(f"{path}: kořen musí být objekt.")
    if not _is_exact_schema_version(data.get("schema_version"), HISTORY_SCHEMA_VERSION):
        raise PolishStoreError(f"{path}: neznámý/chybějící schema_version.")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise PolishStoreError(f"{path}: entries musí být pole.")
    for e in entries:
        _validate_record(e, _HISTORY_ENTRY_FIELDS, what=f"{path}: historický záznam")
        # Neprázdný `draft_id` (kolo 15 plán-ping-pongu IMPORTANT, stejný
        # princip jako draftové `draft_id` - kolo 11) - `_stale_info`
        # matchuje `already_committed_has_history` PODLE TOHOTO pole,
        # aby se vyhnula stejné třídě kolize jako kolo 10 (nesouvisející
        # starší záznam se STEJNÝM textem by jinak falešně "vysvětlil"
        # DB stav pro CIZÍ draft).
        if not e["draft_id"]:
            raise PolishStoreError(f"{path}: draft_id nesmí být prázdný.")
        # Element-level typy (kolo 1 plán-ping-pongu IMPORTANT, stejná
        # mezera jako u draftu - viz `_validate_draft_payload`):
        _validate_dict_list(e["findings"], "findings", f"{path}: historický záznam")
        _validate_dict_list(e["rendered_terms"], "rendered_terms", f"{path}: historický záznam")
        if e["source"] not in _VALID_HISTORY_SOURCES:
            raise PolishStoreError(f"{path}: neplatný source {e['source']!r}.")
        if not _is_utc_z(e["applied_at"]):
            raise PolishStoreError(
                f"{path}: applied_at musí být UTC s koncovým 'Z' ({e['applied_at']!r}).")


def load_history(path: str) -> dict:
    if not os.path.exists(path):
        return {"schema_version": HISTORY_SCHEMA_VERSION, "entries": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise PolishStoreError(f"{path}: neplatný JSON ({e}).") from e
    _validate_history_payload(path, data)
    return data


def save_history(path: str, data: dict) -> None:
    """Validuje STEJNÝMI pravidly jako `load_history` PŘED zápisem
    (kolo 1 plán-ping-pongu NIT)."""
    _validate_history_payload(path, data)
    _atomic_write_json(path, data)


def find_latest(entries: list, idx: int) -> "dict | None":
    """Poslední záznam pro `idx` PODLE POZICE v poli, nikdy podle
    `applied_at` (spec kolo 6 - zápisy jsou vždy sekvenční, srovnání času
    může u dvou náhodně identických timestampů vybrat špatný)."""
    for e in reversed(entries):
        if e["idx"] == idx:
            return e
    return None


def find_chain_start(entries: list, idx: int) -> "dict | None":
    """Začátek SOUVISLÉHO řetězce končícího posledním záznamem pro `idx`
    (spec kolo 20) - NENÍ prostě "úplně první záznam pro idx", historie
    může mít mezery od `answer`/`run` epizod mimo `polish` workflow."""
    idx_entries = [e for e in entries if e["idx"] == idx]
    if not idx_entries:
        return None
    start = idx_entries[-1]
    for older in reversed(idx_entries[:-1]):
        if older["cz_after"] != start["cz_before"]:
            break
        start = older
    return start


def resolve_revert_target(entries: list, idx: int, to: str) -> "str | None":
    if to == "original":
        start = find_chain_start(entries, idx)
        return start["cz_before"] if start else None
    latest = find_latest(entries, idx)
    return latest["cz_before"] if latest else None
