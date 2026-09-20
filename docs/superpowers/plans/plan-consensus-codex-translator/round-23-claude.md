# Round 23 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (scénová smyčka bez checkpointu ztrácí staré otázky):**
  Souhlasím a ověřil jsem přesně proti reálnému `src/pipeline.py`
  (řádky 66-99) - `_checkpoint_flagged()` (kolo 22) a revizní smyčka
  (kolo 13/18/20/21) chrání jen "kontrola" blok a `while` smyčku, obě
  běžící AŽ PO scénové smyčce (`for scene_idx, scene in enumerate
  (scenes): ...`). Selhání PŘÍMO tam (`CodexTranslatorFatalError`/
  `InvalidTranslationOutput`/timeout z `translate_scene()`, i lazy
  `factory()` preflight - ověřil jsem přes Task 5's `except` větve v
  `_cmd_run`, main.py: žádná z nich volá `commit_chapter_result()` ani
  jinak otázky obnovuje, jen `state.update_chapter()` s `status`/
  `notes`) propaguje úplně BEZ checkpointu. `begin_chapter()` (transakce
  A) přitom `existing_questions` UŽ smazal na začátku funkce - takže
  `--retry-flagged` kapitola, co ZNOVU selže v týhle fázi (typicky
  pořád rozbitý Codex CLI/auth), ztratí staré otevřené otázky NAVŽDY,
  i když se nepřeložilo vůbec nic nového.

  **Oprava:** Obalil jsem scénovou smyčku samotnou `try/except
  Exception`, co při JAKÉKOLI výjimce obnoví `existing_questions` přes
  existující veřejné `state.upsert_open_question()` (žádná nová DB
  logika - už existuje, `src/state.py:497-500`) PŘED re-raise. Nemění
  status/text - main.py dál rozhoduje stejně jako dřív. Zvažoval jsem
  širší obalení (celá funkce od `begin_chapter()` po konec) proti
  úzkému (jen scénová smyčka) - zvolil jsem úzké, protože zbytek funkce
  (kontrola blok/revizní smyčka) už má VLASTNÍ, přesnější checkpoint
  (`_checkpoint_flagged()`, co navíc zachovává `cz` a mentions, ne jen
  otázky) - širší obal by byl jen redundantní bezpečnostní síť bez
  přidané hodnoty, za cenu složitějšího find/replace bloku kolidujícího
  s kolo-22's editem stejné oblasti. Přidán regresní test
  `test_scene_loop_fatal_error_restores_existing_open_question`
  (existující otevřená otázka, `translate_scene()` vyhodí
  `FatalRunError` na PRVNÍ scéně, ověřeno že otázka přežije).

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 23: jeden IMPORTANT bod, přesný a ověřený proti reálnému kódu -
scénová smyčka (před "kontrola" blokem) byla JEDINÁ fáze `process_
chapter()` úplně bez checkpointu, takže `--retry-flagged` kapitola,
co znovu selže hned na začátku, ztratí staré otevřené otázky navěky.
Opraveno úzkým `try/except` jen kolem scénové smyčky, co obnoví staré
otázky přes existující `state.upsert_open_question()` - bez zásahu do
state.py, bez duplicity s kolo-22's `_checkpoint_flagged()`. Páté kolo
v řadě, co našlo mezeru ve stejné "checkpoint/otázky" oblasti (9, 13,
18, 20, 21, 22, teď 23) - ale mezery se systematicky zužují, tohle byla
POSLEDNÍ nechráněná fáze funkce.
