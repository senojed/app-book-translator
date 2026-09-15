# Round 11 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **BLOCKING - `require_lock()` kontrola nepokrývá zápisy UVNITŘ
  `_polish_one_chapter`:** ověřeno čtením `src/llm/client.py:103-196` -
  `PipelineLLMClient.complete()` (volané přes `cf("critic")`/`cf(
  "stylist_check")`) zapisuje `llm_calls` řádek při KAŽDÉM volání,
  nezávisle na kontrole na začátku handleru/kolo-10 re-checku před
  `finish_run`. Potvrzeno jako reálná mezera, ne jen kosmetická - kritik/
  stylist_check mohou dělat víc než jedno volání (retry), Codex volání
  (`stylist.polish`) mezi nimi trvá dost dlouho na to, aby okno bylo
  relevantní (i když existující heartbeat vlákno riziko z větší části
  kryje). Přidán volitelný `require_lock` parametr do `PipelineLLMClient.
  __init__`/`complete()` (kontrola PŘED `_inner.complete`, `None`
  výchozí = beze změny pro CLI `run`/`polish`) a do `main._client_factory`
  (stejné jméno, průchozí). Server endpoint (Task 10) teď volá
  `_client_factory(rid, interactive=False, require_lock=app.state.
  require_lock)`. Nové testy: `tests/test_pipeline_client.py` (přímé
  chování `PipelineLLMClient` - `require_lock=False` → `FatalRunError`
  PŘED voláním i PŘED `record_llm_call`, žádný auditní řádek; `require_
  lock=True` → normální průběh) + `tests/test_polish_server.py` (drátování
  - endpoint volá `_client_factory` se SPRÁVNÝM callbackem).

### Částečný nesouhlas (zdůvodněno)
- **IMPORTANT - Task 13 Step 8 migrace: automatický rollback `chapters.
  notes` ze zálohy, když zápis historie selže AŽ PO commitu notes.**
  Souhlas, že chybějící `try/except` kolem `save_history` byla reálná
  mezera (neošetřená výjimka = holý traceback, žádná návodná zpráva) -
  OPRAVENO přidáním `try/except` s jasnou zprávou. NESOUHLAS s
  navrhovaným AUTOMATICKÝM rollbackem přes dvě nezávislé zálohy -
  `findings.assign_ids` je čistě ADITIVNÍ/idempotentní (jen doplňuje
  chybějící pole, nikdy nic nepřepisuje/nemaže), takže "notes migrované,
  historie ne" NENÍ nekonzistentní/poškozený stav vyžadující rollback,
  jen neúplný a bezpečně DOKONČITELNÝ opakovaným spuštěním. Automatický
  rollback přes dvě zálohy by pro jednorázový, ručně spouštěný vývojářský
  skript (explicitně MIMO test-pokryté zdrojové soubory tohohle Tasku)
  byl neúměrná komplikace riskující VLASTNÍ chybu v samotném rollbacku -
  "oprav příčinu a spusť znovu" je jednodušší a stejně bezpečné.
  Automatizovaný pytest test na tenhle scénář se z týchž důvodů
  nepřidává (skript není součást pokryté kódové báze), zprávu ve
  skriptu ale ověří ruční test před prvním spuštěním na skutečných
  datech (existující "Spusť to PŘED prvním ostrým použitím..." odstavec).

## Claude VERDICT

CHANGES_NEEDED (1 reálný BLOCKING oprava, 1 IMPORTANT částečně opraveno/
částečně zdůvodněně odmítnuto)

## Summary for log

Po třech koleh CONSENSUS (8, 9, 10) se kolo 11 vrátilo k BLOCKING -
oprávněně: kolo-10 fix pokrýval jen JEDNO ze tří míst, kde `require_lock`
potřeba ověřit (start handleru, KAŽDÉ LLM volání uvnitř `_polish_one_
chapter`, `finish_run`). Oprava teď threaduje `require_lock` až do
`PipelineLLMClient` (sdílená třída, volitelný parametr, `None` výchozí
nemění CLI chování). Druhý bod (migrace rollback) je první PLNÝ
nesouhlas s Codexovým konkrétním návrhem opravy od kola 5 - zdůvodněno
idempotencí `assign_ids`, ne jen "už to je hotové jinde".
