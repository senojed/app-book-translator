# Round 16 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (kolo-15's `except FatalRunError` je moc široký):**
  Souhlasím a ověřil jsem přesně proč - `_guard()` (`src/llm/client.py:
  150-193`) má PĚT různých `raise FatalRunError`/`LockLostError` míst
  (missing sazby, cost-limit překročen non-interactive, stdin
  nedostupné, uživatel zastavil běh, nevalidní strop, ztráta zámku) -
  kolo-15's `except FatalRunError as e:` chytalo VŠECHNY, ne jen tu
  jednu (`_price()`'s "nemá sazby"), co byla PŮVODNÍM cílem. Normální
  cost-guard stop (limit překročen) NENÍ Codex-specifická chyba - Claude
  backend by dopadl identicky - reklasifikace na `CodexTranslatorFatalError`
  by byla zavádějící (`_cmd_run`'s zpráva "fatální chyba běhu:
  CodexTranslatorFatalError" by implikovala něco rozbitého na Codex
  straně, i když je to jen normální rozpočtová kontrola).

  **Oprava:** Nová `MissingPriceError(FatalRunError)` podtřída -
  `_price()` ji vyhazuje MÍSTO holého `FatalRunError` (jeden řádek
  přepnutý). `PipelineLLMClient.complete()`'s `except` se zúží na
  `except MissingPriceError` - PŘESNĚ ohraničené na jediný případ, co
  má smysl přebalovat. Přidán test ověřující, že normální cost-guard
  stop pro Codex-backed inner klienta zůstává plain `FatalRunError`.

- **IMPORTANT (bare `raise` v `_cmd_run`'s `except CodexTranslatorFatalError`
  vynese neredigovanou zprávu):** Souhlasím - ověřil jsem, že `factory()`'s
  líný preflight (Task 4, kolo 12) konstruuje `CodexTranslatorFatalError
  (preflight_err)` BEZ `_redact_detail()` (`preflight_err` jde přímo z
  `_polish_preflight()`) - `_cmd_run`'s bare `raise` by tedy re-raisoval
  TUHLE nezredigovanou zprávu, a outer handler (`print(f"Fatální chyba
  běhu: {e}")`) by ji vypsal PŘÍMO na konzoli, i když `chapters.notes`
  (o pár řádků výš) dostal správně redigovanou verzi - nekonzistence.

  **Oprava:** `raise CodexTranslatorFatalError(detail) from e` (NOVÁ
  výjimka s REDIGOVANOU zprávou, původní zachovaná jako `__cause__`)
  místo holého `raise`. Přidán test s `capsys` ověřující, že konzolový
  výstup neobsahuje raw text.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 16: dva IMPORTANT body, oba v mém vlastním kolo-15 fixu. (1)
`except FatalRunError` bylo moc široké - chytalo VŠECH pět `_guard()`
raise-sitů, ne jen "nemá sazby" - opraveno novou `MissingPriceError`
podtřídou, zúžený `except`. (2) Bare `raise` v `_cmd_run`'s
`CodexTranslatorFatalError` handleru re-raisovalo neredigovanou
zprávu na konzoli navzdory redigovaným `notes` - opraveno konstrukcí
nové výjimky s redigovanou zprávou. Oba body pokračují v přesně stejném
vzoru jako předchozí kola - pozdější fix odhalí přesnost/mezeru v
dřívějším.
