# Round 12 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`_client_factory`'s líná preflight kontrola vyhazuje
  holý `FatalRunError`):** Souhlasím - ověřil jsem, tahle kontrola běží
  UVNITŘ `factory("translator")`, volaná AŽ z `pipeline.process_chapter`
  (PO `state.begin_chapter()`, kapitola už `processing`) - i když eager
  preflight (kolo 8) tohle OBVYKLE odchytí dřív, je to SAMOSTATNÉ
  volání `_polish_preflight()` v jiném okamžiku - pokud SELŽE (i
  teoreticky vzácně), `raise FatalRunError(preflight_err)` by NEBYL
  zachycen novou typovou `except CodexTranslatorFatalError` větví
  (kolo 11), kapitola by zůstala v přesně tom limbu, co kolo 10/11
  měly vyřešit.

  **Oprava:** `factory()` vyhazuje `CodexTranslatorFatalError`, ne
  holý `FatalRunError`. Přidán test na tenhle konkrétní race (eager
  uspěje, línÁ selže) end-to-end přes `_cmd_run`, ověřující `flagged`.

- **IMPORTANT (Task 5's Interfaces text stále popisoval starý
  `args.translator`-gated mechanismus):** Souhlasím, ověřil jsem - text
  psal "když args.translator == 'codex'" pro `except FatalRunError`
  větev, i když SKUTEČNÁ implementace (kolo 11) už dávno flaguje podle
  TYPU (`CodexTranslatorFatalError`), ne podle běhové podmínky. Bez
  opravy by tenhle rozpor mohl při implementaci plánu svést zpátky ke
  starému (chybnému) mechanismu.

  **Oprava:** Přepsán Interfaces bod - explicitně popisuje typovou
  `except CodexTranslatorFatalError` větev PŘED obecnou `except
  FatalRunError`, žádná podmínka na `args.translator`.

- **IMPORTANT (`_parse()` validuje jen syntaxi JSON, ne tvar):**
  Souhlasím - `extract_json()` úspěšně parsuje `[]`, `null`,
  `{"new_terms": "x"}` (všechno validní JSON), ale `meta.get(...)` na
  ne-dict spadne na `AttributeError` (`[].get` neexistuje), a
  `list("x")` (string místo seznamu) by tiše rozsekal řetězec na znaky
  místo vyhození chyby - obojí je STEJNÁ třída "formát driftl" jako
  rozbité JSON, ale unikalo by klasifikaci jako `InvalidTranslationOutput`
  (a tím i kolo-6/11's fatální ochraně pro Codex cestu).

  **Oprava:** `_parse()` navíc ověří `isinstance(meta, dict)` a že
  `new_terms`/`rendered_terms`/`questions` (pokud přítomné) jsou
  seznamy OBJEKTŮ (ne jen seznamy) - jinak `InvalidTranslationOutput`.
  Přidány tři regresní testy (ne-dict metadata, pole špatného typu,
  položky pole nejsou objekty).

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 12: tři IMPORTANT body, všechny akceptovány. `_client_factory`'s
vlastní (dřívější, líná) preflight kontrola vyhazovala holý
`FatalRunError`, ne novou `CodexTranslatorFatalError` z kola 11 - stejná
mezera, jen JINÉ místo v kódu. Task 5's dokumentace (Interfaces) po
kole 11 nebyla plně přepsaná, stále popisovala starý mechanismus - riziko
regrese při implementaci. `_parse()` validovala jen JSON syntaxi, ne
tvar - syntakticky validní, ale špatně tvarované JSON by unikalo
klasifikaci jako formát-drift. Všechny tři opraveny, plán je teď
vnitřně konzistentní.
