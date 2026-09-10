# Round 35 — Claude critique

Deváté review kola-27 dodatku. Codex 3 IMPORTANT + 1 NIT - fallout z
kola 34 (redakce + record model).

## On Codex's points

### Agreed + fixed
- **IMPORTANT - commit-detekce přes `_already_styled` špatná pro
  `--force`:** marker je z DŘÍVĚJŠÍHO běhu → přerušení před novým commitem
  by se vykázalo jako `polished`. → detekce přes `state.get_chapter(...)
  ["translated_text"] != c["translated_text"]` (úspěšný commit text VŽDY
  změní - commit se dělá jen když `styled != cz`).
- **IMPORTANT - `print("...vylepšeno.")` po commitu může hodit:** generic
  `except` → `failed` (u jediné kapitoly `fatal`), navzdory zapsané
  stylizaci. Kolo 34 zabránilo dvojímu záznamu, ne nepravdivému. →
  helper `_say(msg)` = `try: print(msg) except Exception: pass` pro
  VŠECHNY per-kapitolové diagnostické výpisy. Výsledek běhu se řídí
  stavem DB, ne tím jestli hláška dorazila.
- **IMPORTANT - redigovaný `str(fe)` v in-loop handleru, ale top-level
  `run_error`/`print(e)` uložily/vytiskly STEJNOU výjimku nezměněnou:**
  → `FatalRunError` z commitu je REDIGOVANÁ U ZDROJE
  (`_polish_one_chapter` `raise FatalRunError(f"... ({_redact_detail(...)})")`),
  pak `str(fe)` bezpečné všude. `_snapshot_db`/cost-guard `FatalRunError`
  Codexův obsah nikdy nenese (běží před/mimo stylizaci). Config komentář
  upřesněn.

### NITS - fixed
- test próza "stderr Codexu potlačen" → aktuální `_REDACTED` string.

## Claude VERDICT

`CHANGES_NEEDED` - 3 IMPORTANT, všechny fallout z kola 34. Aplikováno.
Redakce je teď u zdroje (jeden helper, jeden bod pravdy), diagnostické
výpisy nemůžou změnit výsledek. Čeká se na kolo 36.

## Summary for log

Kolo 35: 3 IMPORTANT + 1 NIT - fallout z kola 34. (1) commit-detekce
`--force`: přes `translated_text`, ne marker. (2) `_say()` best-effort
pro všechny diagnostické výpisy - výpis nemůže změnit outcome. (3)
`FatalRunError` z commitu redigovaná U ZDROJE → `str(fe)` bezpečné i v
top-level `run_error`/výpisu. NIT: test próza. Čeká se na kolo 36.
