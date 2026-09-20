# Round 15 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed (přeformulováno)

- **IMPORTANT (cenová tabulka pro `CODEX_MODEL` může zestárnout):**
  Ověřil jsem Codexovu KONKRÉTNÍ premisu ("změní-li uživatel CODEX_MODEL
  za běhu") - `config.CODEX_MODEL` je PLAIN hardcoded konstanta
  (`config.py:96`), NENÍ env-overridable jako `PROJECT_DIR`, a Task 1's
  `PRICE_IN_PER_MTOK[CODEX_MODEL] = 0.0` je na SOUSEDNÍM řádku ve
  STEJNÉM souboru - referencuje proměnnou, ne hardcoded string, takže
  editace `CODEX_MODEL` v `config.py` VŽDY drží cenu synchronizovanou.
  Codexova KONKRÉTNÍ scénka (runtime změna modelu) tedy NENÍ reálně
  dosažitelná v současném návrhu.

  ALE za tímhle tvrzením je OBECNĚJŠÍ, platný problém, co jsem ověřil
  nezávisle - `PipelineLLMClient._guard()`'s "nemá sazby" `FatalRunError`
  (`src/llm/client.py:135-140`, `_price()`) je OBECNÝ typ. I když Task 1
  garantuje sazby VŽDY (za normálních okolností), `PipelineLLMClient`
  samo nemá ŽÁDNÝ mechanismus, co by tenhle konkrétní `FatalRunError`
  přebalil na `CodexTranslatorFatalError`, kdyby k desynchronizaci PŘECE
  jen došlo (budoucí refaktor, konfigurace editovaná mimo `config.py`,
  cokoli) - poslední netypovaná cesta z celé rodiny fixů (kolo 10-13
  postupně otypovaly `CodexLLMClient.complete()`, `InvalidTranslationOutput`,
  `factory()`'s líný preflight - tohle bylo jediné zbývající místo).

  **Oprava:** `PipelineLLMClient.complete()`'s `_guard()` volání se
  obalí `try/except FatalRunError` - pro `self._inner.provider ==
  "codex"` přebalí na `CodexTranslatorFatalError`. Přidán test s
  chybějícím cenovým záznamem (simuluje stav přímo, bez nutnosti
  "CODEX_MODEL se změnil" scénáře).

- **IMPORTANT (`sqlite3` CLI není dostupné v tomhle prostředí):**
  OVĚŘIL jsem přímo (`which sqlite3` → "command not found", `/usr/bin/
  bash: sqlite3: command not found`) - Codex má PRAVDU, `sqlite3` CLI
  skutečně chybí a projekt ho nemá jako závislost. Můj vlastní kolo-14
  fix (`.backup` dot-command) by tedy nešel provést podle plánu - reálná
  regrese, co jsem zavedl a neověřil.

  **Oprava:** Nahrazeno Python stdlib `sqlite3` modulem (vždy dostupný,
  žádná nová závislost) - `Connection.backup()` pro konzistentní kopii,
  parametrizovaný `SELECT` (bind parametr `?` místo SQL string literálu -
  vyhne se quoting rozdílům mezi bash/PowerShell) pro diagnostický
  dotaz. Cesty se předávají přes env proměnné (`SMOKE_SRC_DB`/`SMOKE_DB`),
  ne stringovou interpolací do Pythonu - obchází backslash/forward-slash
  a quoting nekonzistence mezi bash a PowerShell.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 15: dva IMPORTANT body. První - Codexova KONKRÉTNÍ premisa
("CODEX_MODEL se mění za běhu") byla nesprávná (config.py's proměnná-
referencující kód drží cenu vždy synchronizovanou), ALE za ní byl
OBECNĚJŠÍ platný problém - PipelineLLMClient._guard()'s FatalRunError
zůstávalo jediné netypované místo z celé rodiny kolo-10-13 fixů;
opraveno přebalením na CodexTranslatorFatalError pro Codex-backed
inner klienty. Druhý bod OVĚŘEN přímo (sqlite3 CLI skutečně chybí v
tomhle prostředí) - vlastní kolo-14 fix byl neproveditelný regrese;
opraveno přechodem na Python stdlib sqlite3 modul.
