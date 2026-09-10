# Round 36 — Claude critique

Desáté review kola-27 dodatku. Codex 2 IMPORTANT + prose-vs-code sweep.
Oba IMPORTANT = dokončení kolo-35 `_say` změny (další `print` v
cleanup/report cestě).

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `_backup_db_once` `print` po `os.replace` PŘED
  `done = True`:** `BrokenPipeError` → `FatalRunError` → úspěšná promoce
  se "nestala", commit se nezkusí. → `backup_state["done"] = True` HNED
  po `os.replace`, pak `_say`.
- **IMPORTANT - `_write_polish_report` + `finally` warning `print`
  můžou vyhodit a uniknout z `finally`:** úspěchový `print`, jeho
  `except`-warning, `finish_run`-failure warning → všechny `_say`.
- **Dokončení:** VŠECHNY zbylé raw `print` v `main.py` runtime kódu
  (preflight, výběr kapitol, "všechno selhalo") → `_say`. Jediný raw
  `print` co zůstává je uvnitř `_say` samotného.

### NITS (prose-vs-code sweep) - fixed
- `_polish_one_chapter` docstring + error tabulka: commit-detekce přes
  marker → `translated_text`.
- test bullet `print("...vylepšeno.")` → obecný "výpis nemůže změnit
  outcome".
- error tabulka: redakce `FatalRunError` "v in-loop handleru" → "u
  zdroje".
- filename `run-<rid>-<čas>.json` → `run-<rid>-<čas>-<8 hex>.json`.

## Claude VERDICT

`CHANGES_NEEDED` - 2 IMPORTANT (dokončení `_say`), zbytek prose sweep.
Aplikováno. Teď je JEDINÝ raw `print` v `_say`; žádná diagnostika
nemůže shodit ani přebít výsledek běhu. Čeká se na kolo 37.

## Summary for log

Kolo 36: 2 IMPORTANT + prose sweep. Oba IMPORTANT = zbylé `print` v
cleanup/report cestě → `_say`. `_backup_db_once` navíc `done = True`
HNED po `os.replace`. VŠECHNY raw `print` v main.py runtime → `_say`.
Stale próza (marker vs translated_text, print vylepšeno, redakce
in-loop vs u zdroje, filename hex) sjednocena. Čeká se na kolo 37.
