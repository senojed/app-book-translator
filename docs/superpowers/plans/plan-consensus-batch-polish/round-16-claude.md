# Round 16 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **BLOCKING - `require_lock()` v `PipelineLLMClient.complete()` je až
  PO `_guard()` - interaktivní cost guard (`interactive=True`, CLI od
  kola 13) může při překročení stropu na potvrzení uživatele zapsat
  `runs.spend_ceiling` (`state.set_run_spend_ceiling`) BEZ ověřeného
  zámku.** Ověřeno čtením `_guard()` (src/llm/client.py:136-171) -
  potvrzeno, `_guard()` DĚLÁ skutečný DB zápis v interaktivní větvi.
  Přidána DRUHÁ `require_lock` kontrola PŘED `_guard()` (kontrola PO
  `_guard()` z kola 11/12 ZŮSTÁVÁ taky - `_guard()` může čekat na
  vstup libovolně dlouho, zámek může zmizet PRÁVĚ během čekání).
  Nový test: `require_lock=False` + přes strop → `_guard()` se vůbec
  NESPUSTÍ (`confirm` callback nula volání), žádný `spend_ceiling`
  zápis.
- **IMPORTANT - ztráta zámku uvnitř `PipelineLLMClient.complete()`
  vyhazovala obyčejný `FatalRunError`, endpointův generický `except
  Exception` ho mapoval na 500, ne na dokumentovaných 503 (stejný jako
  startovní `require_lock()` kontrola).** Přidána `LockLostError(
  FatalRunError)` podtřída (`src/llm/client.py`) - VŠECHNO, co dnes
  odchytává `except FatalRunError` (CLI propagace), funguje beze změny
  (dědičnost), ale regenerate endpoint teď má SAMOSTATNÝ `except main.
  LockLostError` PŘED obecným `except Exception`, mapuje na 503. Nový
  test ověřuje 503 (ne 500) při ztrátě zámku uvnitř `_polish_one_chapter`.

## Claude VERDICT

CHANGES_NEEDED (souhlas s BLOCKING i IMPORTANT, plná implementace)

## Summary for log

Páté kolo v řadě (10-16, s výjimkou 14/15) na téma lock-check
konzistence - tentokrát dva NOVÉ úhly: cost-guard's vlastní DB zápis
(přehlédnutý ve všech předchozích kolech) a HTTP status kód konzistence
(503 vs 500 pro STEJNOU podmínku). `LockLostError` podtřída je první
místo v týhle sérii, kde vznikla nová veřejná výjimka místo dalšího
lock-check volání - ukazuje, že jednoduché "zkontroluj znovu" už
nestačilo na udržení konzistentního API kontraktu.
