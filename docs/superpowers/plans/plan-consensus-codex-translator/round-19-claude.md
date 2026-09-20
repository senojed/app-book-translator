# Round 19 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (Task 6's `polish --only <idx>` bez explicitního
  `BOOK_TRANSLATOR_PROJECT_DIR` prefixu v bash bloku):** Souhlasím,
  ověřil jsem - bash blok nastavuje `BOOK_TRANSLATOR_PROJECT_DIR`
  INLINE PER-PŘÍKAZ (ne `export`, na rozdíl od `SMOKE_SRC_DB`/`SMOKE_DB`),
  takže by nepřenesl do dalšího, samostatně typovaného příkazu.
  Prozaická instrukce "se stejným BOOK_TRANSLATOR_PROJECT_DIR
  nastaveným" (bez UKÁZANÉHO příkazu) je snadné nedomyslet - a `polish`
  na rozdíl od `status` REÁLNĚ ZAPISUJE do DB, takže omyl by dopadl na
  ostrou `data/state.sqlite3`.

  **Oprava:** Explicitní `BOOK_TRANSLATOR_PROJECT_DIR=/tmp/codex-translator-smoke
  \` prefix přidán přímo do bash bloku (stejný vzor jako ostatní
  příkazy). Přidáno i do PowerShell bloku pro symetrii/jasnost (tam by
  to technicky fungovalo i beze změny díky `$env:...` persistenci, ale
  explicitní příkaz je lepší dokumentace než spoléhání na to, že si
  uživatel vzpomene).

### Agreed + fixed (NIT)

- **NIT (`_polish_preflight()`'s hláška "polish je vypnutý" matoucí pro
  `run --translator codex`):** Souhlasím - ověřil jsem přesné znění
  (`main.py:1152`) - sdílená funkce, hláška hardcoded na kontext
  `polish`. Parametrizace `_polish_preflight()`'s signatury by si
  vyžádala update KAŽDÉHO existujícího test mocku (`lambda: (...)`)
  napříč Taskem 4/5 - moc invazivní na NIT. Místo toho krátký
  kontextový prefix PŘI VOLÁNÍ v `_cmd_run`, funkce samotná beze změny.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 19: jeden IMPORTANT (chybějící explicitní env-var prefix pro
`polish --only` v Task 6's bash bloku - reálné riziko zápisu do ostré
DB, opraveno přidáním explicitního příkazu do obou bash/PowerShell
bloků) a jeden NIT (matoucí "polish je vypnutý" hláška pro `run
--translator codex` kontext - opraveno lehkým kontextovým prefixem v
`_cmd_run`, bez zásahu do sdílené `_polish_preflight()` funkce/testů).
