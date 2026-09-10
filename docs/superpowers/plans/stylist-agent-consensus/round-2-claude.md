# Round 2 — Claude critique

Codex: CHANGES_NEEDED (4 IMPORTANT, 2 NITS). Konvergence: BLOCKING pryč.

## Claude's own findings

### IMPORTANT
- **Task 5 rozdělené `Step 1a`/`Step 1b`** - Step 2/3/4/5 číslování zůstalo konzistentní, ověřeno.

Žádné nové vlastní BLOCKING/IMPORTANT - kolo 1 pokrylo strukturální problémy, kolo 2 je dolaďování.

## On Codex's points

### Agreed + fixed
- **IMPORTANT `polish()` neubíjí sirotčí proces při KeyboardInterrupt** (spec 880-891 killne jen na `TimeoutExpired`): Codex má pravdu - Ctrl+C během `communicate()` nechá `node.exe` běžet a čerpat kvótu, přesně to, kvůli čemu `_kill_process_tree` existuje. **Fix:** Task 5 Step 3 odchylka - `except BaseException: _kill_process_tree(proc); proc.wait(timeout=10); raise` za `except TimeoutExpired`. +test `test_polish_kills_process_tree_on_keyboard_interrupt`.
- **IMPORTANT Task 11 provenience test slabý** (stejný termín/forma/scéna, nesleduje `build_mentions` args, `_c()` text neobsahuje formu): **Fix:** přepsán - dva RŮZNÉ termíny (A rendered, B detected), spy na `check_chapter` I `build_mentions`, přesná rovnost `rendered` argumentu (`[{term_id: t/a, cz_as_used: Áčko, scene_idx: 3}]`), +prázdný `cz_form` se zahodí. Protože B není ve `rendered_terms`, přeznačit na 'rendered' ho `build_mentions` nemůže.
- **IMPORTANT Task 9/12 chybí test okamžiku zálohy** (přesun snapshotu za `create_run` by prošel): **Fix:** Task 12 `test_cmd_polish_backup_predates_run_bookkeeping` - `.pre-polish-backup` po úspěšné dávce NEMÁ `runs` řádek (snapshot z doby PŘED `create_run`).
- **IMPORTANT Task 13 nemá bezpečný konec při selhání** (config revert až pozdějším krokem; běh nad pracovní DB): **Fix:** Task 13 přepsán - canary test PRVNÍ; reálný běh nad KOPIÍ DB v `<TMP>`; config JEN `config.*` atributy za běhu skriptu, `config.py` na disku se NEMĚNÍ → není co vracet; canary používá fresh soubor s náhodným obsahem.
- **NIT rozsahy řádků pořád obsahují fence** (config 344→345, modul 433→434): OVĚŘENO `sed` - fence ``` je na 344 resp. 433, kód začíná 345 resp. 434. **Fix:** Task 1 → 345-400, Task 4 → 434-746, self-review taky.
- **NIT Task 2 "non-list findings → rozbité" neplatí pro null/chybějící** (spec 188): pravda, `raw_findings is not None and not isinstance(list)`. **Fix:** Interfaces upřesněno ("non-list A non-None"); +test `test_review_findings_null_or_missing_is_empty_not_broken`.

### Disagreed
Žádné.

## Claude VERDICT

`CHANGES_NEEDED` - 4 Codex IMPORTANT platné, aplikováno. Vlastních BLOCKING/IMPORTANT 0.

## Summary for log

Kolo 2: Codex CHANGES_NEEDED (4 IMPORTANT, 2 NITS), Claude 0 vlastních. IMPORTANT: `polish()` sirotčí proces při Ctrl+C → `except BaseException` kill; Task 11 provenience test přepsán na 2 termíny + spy na build_mentions; +test že záloha předchází `runs` řádku; Task 13 přepsán na kopii DB + runtime config (bez editace config.py). NITs: fence v rozsazích (345/434), null findings. Sporné: 0. Konvergence 3B→0B, 7I→4I.
