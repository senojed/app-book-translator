# Round 6 — Claude critique

Codex: CHANGES_NEEDED (1 IMPORTANT). Fallout kolo-5.

## Claude's own findings
Žádné nové vlastní.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `counts` nezapočítává neočekávané výjimky:** kolo-5 přesunul `counts[...] += 1` do `else` vnitřního `try` → po `except Exception` (`failed` záznam) se `counts["failed"]` nezvýší. Dávka, kde VŠECHNY kapitoly spadnou na `ValueError` (např. z konkordance), by vrátila 0 / `runs.status="ok"` navzdory reportu plnému `failed` (spec 2678-2680, 2868). **Fix:** `counts` slovník zrušen; souhrn i podmínka "všechno selhalo" se PO smyčce počítají z `report` (`tally = {k: sum(...) for k in _REPORT_OUTCOMES}`) - jediný zdroj pravdy, DRY s `_write_polish_report`. +test `test_cmd_polish_all_generic_exceptions_is_fatal` (mock `check_chapter` → `ValueError`, 3× → return 1, fatal, `batch_completed=True`, `summary["failed"]==3`). Stávající all-failed test používá `StylistError` (helper ho převádí na normální návrat), tuhle regresi by nechytil.

### Disagreed
Žádné.

## Claude VERDICT

`CHANGES_NEEDED` - 1 Codex IMPORTANT platné, aplikováno. Vlastních 0.

## Summary for log

Kolo 6: Codex 1 IMPORTANT (fallout kolo-5). `counts` v `else` větvi nezapočítal `failed` z neočekávané výjimky → all-failed dávka vracela `ok`. Fix: `counts` pryč, souhrn i all-failed check z `report` po smyčce. +test s generickou výjimkou. Sporné: 0. Append-invariant refactoring je teď snad usazený (kola 4→5→6).
