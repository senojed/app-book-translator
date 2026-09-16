# Round 2 — Claude critique

## Claude's own findings

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (StylistError politika - OBRACÍM kolo 1 rozhodnutí):**
  Ověřil jsem PŘÍMO v kódu - `state.queue_for_run` (main.py `_cmd_run`'s
  vlastní fronta): `return chapters_by_status(db_path, ("pending",
  "error"))`, s docstringem "error = automatický retry". To je fakt, co
  jsem v kole 1 nezvážil - `flagged`/`needs_human` čekají na ČLOVĚKA
  (`--retry-flagged`), ale `error` se AUTOMATICKY zkusí znovu PŘI
  KAŽDÉM příštím `run`. Můj kolo-1 precedent (`_polish_one_chapter`'s
  stejná třída chyby) NENÍ přenositelný, jak jsem tvrdil - `polish`
  selhání nechá kapitolu v `done` (bezpečné, nic se needěje dál), zatímco
  `run`-translator selhání kvůli rozbitýmu Codex CLI/auth by při KAŽDÉM
  příštím `run` (i budoucím, na JINÝCH kapitolách) potichu znovu
  zkoušelo stejnou rozbitou cestu, dokud si toho uživatel nevšimne -
  přesně to riziko, co jsem v kole 1 podcenil.

  **Oprava:** `CodexLLMClient.complete()` zachytává `stylist.
  StylistError` ze `_exec_codex()` a přebaluje na `FatalRunError`
  (zachovává zprávu) - `_cmd_run`'s `except FatalRunError: raise`
  (main.py:1013-1014) tak zastaví CELÝ běh HNED při první selhávající
  Codex exekuci, ne až po N tichých `error` kapitolách. Task 2 rozšířen.

- **IMPORTANT (`CODEX_TRANSLATE_MAX_CHARS` guard může zahodit hotovou
  scénovou práci):** Souhlasím, ověřil jsem v `pipeline.process_chapter`
  - `revise_chapter()` volání NENÍ obalené žádným try/except uvnitř
  `pipeline.py`, takže výjimka odsud (moje `CODEX_TRANSLATE_MAX_CHARS`
  kontrola, NEBO teď po opravě výš `FatalRunError`) propaguje VEN z
  CELÉ funkce PŘED `state.commit_chapter_result(...)` na konci - i když
  scénový překlad (`cz` proměnná) byl KOMPLETNÍ a validní. Tohle je sice
  architektonicky STARŠÍ vlastnost `pipeline.py`'s revizní smyčky (stejné
  riziko existuje latentně i pro Claude - `revise_chapter` může selhat
  na `FatalRunError`/síťové chybě a taky by zahodilo scénovou práci),
  ALE můj DETERMINISTICKÝ guard (pevný `60_000` znaků) by tohle riziko
  změnil z "vzácná síťová anomálie" na "SPOLEHLIVĚ nastane u každé delší
  kapitoly, jakmile glosář časem naroste" - mnohem pravděpodobnější
  spouštěč stejné staré díry, ne jen stejně pravděpodobný.

  Skutečná architektonická oprava (checkpoint scénového překladu PŘED
  revizní smyčkou, fallback "ulož nerevidovaný překlad jako flagged
  místo zahození") by znamenala zásah do `pipeline.py`'s sdílené
  revizní smyčky (používá ji STEJNĚ Claude i Codex cesta) - mimo rozsah
  týhle spec (design explicitně říká jen `_exec_codex`/`stylist.py`
  zůstávají beze změny, ale úprava SDÍLENÉ revizní smyčky kvůli
  Codex-specifickému limitu je stejná třída scope-creepu).

  **Oprava:** RUŠÍM `CODEX_TRANSLATE_MAX_CHARS` guard z Tasku 1/2 úplně
  (revert kola 1 IMPORTANT fixu). Bez aktivního guardu se oversized
  prompt projeví AŽ přes `CODEX_TRANSLATE_TIMEOUT_SECONDS` timeout
  (méně přesná hláška, ale PO opravě výš i tak `FatalRunError` → celý
  běh se řízeně zastaví, ne tiché zahození). Zdokumentováno jako
  vědomě PŘIJATÝ limit (spolu s `truncated=False`), ne guard, co by
  spolehlivě ničil hotovou práci na běžně velkých kapitolách.

- **IMPORTANT (Task 5 Step 2 - Unix syntax na Windows projektu):**
  Souhlasím - `/tmp`, `mkdir -p`, inline `VAR=val cmd` je bash/POSIX,
  projekt běží primárně na Windows/PowerShell (`Shell: PowerShell
  (primary); Bash tool also available`). Přidávám k existujícímu bash
  příkladu i PowerShell variantu (`New-Item`, `$env:...`), ať jde krok
  provést v obojím.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 2: Codex přinesl nový, silnější fakt (`queue_for_run`'s "error =
automatický retry" docstring) - obrátil jsem kolo-1 rozhodnutí o
`StylistError`, teď se přebaluje na `FatalRunError` (celý běh se
zastaví, ne tichý per-kapitolový retry navěky). Druhý bod odhalil, že
kolo-1's VLASTNÍ fix (`CODEX_TRANSLATE_MAX_CHARS` guard) má vedlejší
efekt - spolehlivě zahodí hotovou scénovou práci při revizi delší
kapitoly - guard zrušen, nahrazen zdokumentovaným limitem (timeout jako
fallback). Třetí bod (Windows shell syntax) opraven přidáním PowerShell
varianty vedle bash.
