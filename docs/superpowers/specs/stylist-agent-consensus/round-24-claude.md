# Round 24 — Claude critique

## Claude's own findings
(žádné vlastní nad rámec Codexových)

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `_snapshot_db` deadline nemá skutečný test:** správně -
  pages=100 test ověřuje jen předání argumentu, ne že callback fakt
  přeruší nebo že se `TimeoutError` propaguje. Regrese odstranící
  `progress=_check_deadline` by prošla. Přidán test: proxy `.backup()`
  (přes stejný `main.sqlite3.connect` monkeypatch) zavolá předaný
  `progress` callback, `main.time.monotonic` monkeypatchnutý tak, aby
  druhé volání bylo za deadline → `_check_deadline` vyhodí `TimeoutError`,
  test ho očekává z přímého `main._snapshot_db(...)`.
- **NIT - `_codex_argv` docstring + kolo-19 bullet: stale próza:**
  ověřeno - od kola 20 argv test VĚDOMĚ nevolá `_codex_argv` (ruční
  oracle). Obě formulace opraveny na "canary odkazuje, argv test
  NEVOLÁ".
- **NIT - "jedna přepisovaná záloha na běh" nepřesné:** správně - běh
  bez přijaté změny zálohu ani nepromuje. Upřesněno na "nejvýš jedna
  záloha za běh, jen před PRVNÍM přijatým zápisem".

## Claude VERDICT

Po aplikaci 1 IMPORTANT + 2 NITS z kola 24 (0 BLOCKING, páté kolo v
řadě) nenacházím nic dalšího. IMPORTANT byl doplnění chybějícího testu,
NITs stale próza.

`CONSENSUS`

## Summary for log

Kolo 24: Codex našel 1 IMPORTANT + 2 NITS (0 BLOCKING). IMPORTANT:
`_snapshot_db` deadline neměl skutečný test (pages=100 test ověřuje jen
argument) - přidán test s proxy `.backup()` volající callback +
monkeypatchnutý `time.monotonic` za deadline → `TimeoutError`. NITs:
`_codex_argv` docstring/bullet stale (argv test ho od kola 20 nevolá),
"Mimo rozsah" backup próza upřesněna. Čeká se na kolo 25 (24/30 stropu).
