## IMPORTANT

- `_backup_db_once`, ř. 1452–1457; testovací plán ř. 2730–2734: Po úspěšném `os.replace` následuje nechráněný `print()` ještě před `backup_state["done"] = True`. `BrokenPipeError` proto způsobí `FatalRunError`, commit neproběhne a deklarovaný test s vždy selhávajícím `main.print` musí selhat. Nastavit `done` ihned po `os.replace`, použít `_say()` a testovat skutečnou cestu přes `_backup_db_once`.

- `_write_polish_report`, ř. 1681–1719; `_cmd_polish.finally`, ř. 1959–1975: „Best-effort“ diagnostika stále může přebít výsledek běhu. Selhání úspěchového `print()` zavede `_write_polish_report` do `except`; následný varovný `print()` může znovu vyhodit a uniknout z `finally`. Totéž platí pro varování po selhání `finish_run`, které navíc zabrání vytvoření reportu. Použít nevyhazující `_say()` pro všechny výpisy v cleanup/report cestách a přidat testy kombinující selhávající stdout se selháním `json.dump` a `finish_run`.

## NITS

- Prose-vs-code sweep našel několik stale tvrzení:
  - ř. 1484–1485 a 2831 stále popisují detekci commitu přes marker; kód používá změnu `translated_text`;
  - ř. 2692–2696 stále předpokládají přímý `print("…vylepšeno.")`;
  - ř. 2830 tvrdí redakci `FatalRunError` v in-loop handleru, ale probíhá u zdroje;
  - ř. 2832 tvrdí `print()` → `failed` a append v každém handleru; obojí odporuje `_say()` a společnému bottom appendu;
  - ř. 1660, 2833 a 2852 vynechávají náhodný suffix skutečného názvu reportu.

## VERDICT

CHANGES_NEEDED