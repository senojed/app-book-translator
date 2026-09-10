# Round 3 — Claude critique

Codex: CHANGES_NEEDED (1 BLOCKING, 2 IMPORTANT). Nový BLOCKING je fallout kolo-1 fixu.

## Claude's own findings
Žádné nové vlastní BLOCKING/IMPORTANT.

## On Codex's points

### Agreed + fixed
- **BLOCKING - `sys.stdin.buffer.read().decode("utf-8")` (kolo 1 fix) rozbil CRLF normalizaci:** Codex má pravdu. `Popen(text=True)` na Windows překládá `\n`→`\r\n` na ZÁPISU; `buffer` (raw) translaci zpět NEDĚLÁ, takže regexové kotvy `---\n(...)` nesednou na `---\r\n`. Kolo 1 fix vyměnil cp1252 problém za CRLF. **Fix:** parsující fake skripty používají `sys.stdin.buffer.read().decode("utf-8").replace("\r\n", "\n")` - obojí najednou. Global Constraint upřesněn (2 důvody: decode + normalizace); `test_polish_roundtrips_utf8_diacritics` i `test_polish_long_input` fake skripty aktualizovány.
- **IMPORTANT - `test_polish_kills_process_tree_on_keyboard_interrupt` vadný:** spouštěl reálný proces + mockoval `_kill_process_tree` počítadlem → `proc.wait(10)` na reálném dítěti čekajícím na EOF stdin timeoutuje (10s), test pomalý, sirotek. **Fix:** kompletní `FakePopen` (žádný reálný proces), assert přesné pořadí `["communicate", "kill_tree", "wait:10"]` + `pytest.raises(KeyboardInterrupt)`.
- **IMPORTANT - Task 13 `shutil.copy2` živé DB:** spec 1333+ `shutil.copy2` výslovně odmítá (souběžné zápisy, WAL) - `_snapshot_db` existuje právě proto. **Fix:** Task 13 Step 3 skript volá `main._snapshot_db("data/state.sqlite3", "<TMP>/verify.sqlite3")`, pak `config.DB_PATH`.

### Disagreed
Žádné.

## Claude VERDICT

`CHANGES_NEEDED` - 1 BLOCKING + 2 IMPORTANT od Codexe, všechny platné a aplikované. Vlastních 0.

## Summary for log

Kolo 3: Codex CHANGES_NEEDED (1 BLOCKING, 2 IMPORTANT), Claude 0 vlastních. BLOCKING: kolo-1 stdin fix (`buffer.read().decode`) rozbil CRLF - Windows `text=True` zápis dělá `\n`→`\r\n`, raw čtení to nevrací → `+ .replace("\r\n","\n")`. IMPORTANT: KI test přepsán na plný FakePopen (reálný proces = 10s timeout + sirotek); Task 13 `shutil.copy2` → `_snapshot_db`. Sporné: 0. Všechno fallout dřívějších fixů, ne nové designové díry.
