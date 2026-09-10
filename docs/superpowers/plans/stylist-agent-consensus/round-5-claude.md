# Round 5 — Claude critique

Codex: CHANGES_NEEDED (2 IMPORTANT, 2 NITS). Vše fallout kolo-4 přídavků.

## Claude's own findings
Žádné nové vlastní. Ale kolo 4 append-fix (kolo-4 verze s vnitřním `except KeyboardInterrupt`) měl sám mezeru - viz Codex I1, uznávám.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - kolo-4 append fix stále ztrácí záznam:** KI během `_say(...)` v `except Exception`, než je `rec` sestavené, propadne bez appendu (sousední `except KeyboardInterrupt` handler z `except Exception` neběží). **Fix:** kolo-5 verze - žádný vnitřní `except KeyboardInterrupt`; JEDEN `finally` s BEZPODMÍNEČNÝM `report.append(rec)`; `rec` se v `finally` DOPOČÍTÁ ze stavu DB (`translated_text` změněn → `polished`, jinak `interrupted`), když ho žádná větev nesestavila. V `except Exception` se `rec` sestaví PŘED `_say`. +test `test_cmd_polish_ki_during_error_logging_records_exactly_once` (helper ValueError, `_say` na "neočekávaná chyba" vyhodí KI, report má právě 1 záznam).
- **IMPORTANT - Task 13 Step 2 přímé `codex exec` bez timeoutu:** právě testovaný hang na MCP by zablokoval ověření donekonečna. **Fix:** Step 2 dostal konkrétní `Popen` runner - explicitní UTF-8, `cwd=T1`, `communicate(timeout=180)`, `_kill_process_tree` + omezený `wait` při `TimeoutExpired`.
- **NIT - identitní stráž zbytečná:** pravda - v kolo-5 verzi je JEN jeden `finally` a jeden append, stráž pryč, komentář opraven na "invariant STRUKTURNÍ".
- **NIT - Task 13 `unchanged` je legitimní:** pravda, model může vrátit totožný text. **Fix:** Step 3 uznává `unchanged` jako platný výsledek short-circuit větve; pro živé ověření guardrailů+commitu → jiná kapitola.

### Disagreed
Žádné.

## Claude VERDICT

`CHANGES_NEEDED` - 2 Codex IMPORTANT platné (obojí fallout kolo-4), aplikováno. Vlastních 0.

## Summary for log

Kolo 5: Codex 2 IMPORTANT + 2 NITS, vše fallout kolo-4 přídavků. IMPORTANT: (1) kolo-4 append fix měl vlastní KI mezeru (během `_say` v error handleru) → kolo-5 verze: JEDEN `finally`, bezpodmínečný append, `rec` dopočítán z DB, +test; (2) Task 13 přímý `codex exec` bez timeoutu → konkrétní Popen runner s kill. NITs: identitní stráž pryč, `unchanged` uznán. Sporné: 0. Vzorec "přídavek plodí přídavek" (jako spec kola 27-38) - append invariant je teď snad konečně těsný.
