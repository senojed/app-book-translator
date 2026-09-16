# Round 11 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

### NITS
(žádné vlastní nové)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`args.translator == "codex"` nerozlišuje původ chyby):**
  Souhlasím, ověřil jsem - kritik je VŽDY `AnthropicClient`, i při
  `--translator codex` (Global Constraints, beze změny). Kolo 10's
  `if args.translator == "codex":` gate v `_cmd_run`'s `except
  FatalRunError` reagovalo na NASTAVENÍ backendu, ne na PŮVOD chyby -
  kritikův cost guard/`LockLostError` (100% Claude-side) by tak dostal
  stejné flagged+redakci určené pro Codex-translator selhání, přímo v
  rozporu s deklarací "Claude cesta beze změny".

  **Oprava:** Nová `CodexTranslatorFatalError(FatalRunError)` (`src/llm/
  client.py`, hned za `LockLostError` - stejný vzor) - `CodexLLMClient.
  complete()` teď vyhazuje TENHLE typ místo holého `FatalRunError`.
  `_cmd_run` dostane SAMOSTATNOU `except CodexTranslatorFatalError`
  větev PŘED obecnou `except FatalRunError` - typ SÁM garantuje původ,
  žádná běhová podmínka na `args.translator` potřeba. Obecná `except
  FatalRunError: raise` zůstává BEZE ZMĚNY (pre-existující chování).
  Přidán test ověřující, že obecný `FatalRunError` (simulující kritikův
  cost guard) NEDOSTANE flagged zacházení.

- **IMPORTANT (`^marker$` nepřijme CRLF):** Souhlasím - `$` v Pythonu
  (MULTILINE) matchuje TĚSNĚ před `\n`, ne za `\r\n` dohromady, takže
  `\r` by zůstal MEZI markerem a `$` pozicí na CRLF řádku. Windows-
  primární projekt (systémový prompt to potvrzuje) - reálné riziko, i
  když `subprocess`/`open()`'s textový mód univerzální newlines obvykle
  řeší SAM (ověřil jsem - `Popen(text=True)` i `open(..., "r")` mají
  `newline=None` default, což CRLF→LF překládá automaticky), tenhle
  parser je ale backend-agnostický (vlastní deklarovaný cíl "obrana do
  hloubky i pro Claude cestu"), takže se na to nespoléhá.

  **Oprava:** `_parse()` normalizuje `raw.replace("\r\n", "\n").replace
  ("\r", "\n")` JAKO PRVNÍ krok, PŘED jakoukoli validací. Přidán
  regresní test s CRLF markery.

- **IMPORTANT (`StylistTimeoutError` testy jen mockují, neověřují
  reálnou raise-site):** Souhlasím - existující `tests/test_stylist.py::
  test_polish_raises_on_timeout` (reálný subprocess, `time.sleep(5)` +
  `timeout=1`) ověřuje `pytest.raises(StylistError, match="timeout")` -
  `StylistTimeoutError` JE `StylistError`, takže by tenhle test prošel i
  BEZ mojí kolo-9 raise-site opravy (regrese by neodhalil).

  **Oprava:** Zpřísněn na `pytest.raises(stylist.StylistTimeoutError,
  match="timeout")` - stejný test, přesnější typ, ověřuje SKUTEČNOU
  `subprocess.TimeoutExpired` větev, ne mock.

### Agreed but already addressed
- **NIT (preambule před `===PREKLAD===` se tiše zahodí):** Souhlasím,
  je to REÁLNÉ chování (ne bug) - zdokumentováno explicitně v Task 2's
  Interfaces jako VĚDOMĚ přijatý, asymetrický toleranční limit (mírnější
  PŘED prvním markerem, přísný PO poslední - odůvodnění přidáno).

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 11: tři IMPORTANT body. (1) Kolo-10's `args.translator == "codex"`
gate reagovalo na NASTAVENÍ backendu, ne na PŮVOD chyby - kritikova
Claude-side FatalRunError (cost guard) by dostala Codex-specifické
flagged zacházení; opraveno novou `CodexTranslatorFatalError` podtřídou,
rozlišení podle TYPU. (2) `^marker$` regex nepřijme CRLF řádky - reálné
riziko na Windows-primárním projektu i přes obvyklou automatickou
normalizaci v subprocess/file-read textových módech; opraveno explicitní
CRLF→LF normalizací jako první krok `_parse()`. (3) Existující timeout
test v `test_stylist.py` ověřoval jen rodičovský typ `StylistError`,
neověřoval SKUTEČNOU raise-site opravu; zpřísněno na `StylistTimeoutError`.
Plus NIT o zdokumentování preambule-tolerance.
