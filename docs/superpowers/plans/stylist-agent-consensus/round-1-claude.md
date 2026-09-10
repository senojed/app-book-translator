# Round 1 — Claude critique

## Claude's own findings

### BLOCKING
- **Task 5, 3 spec-verbatim pozitivní testy porušují délkový guard** (`0.5 <= len(styled)/len(cz) <= 1.5`, spec 929-930): `test_polish_returns_output_file_contents` (poměr 50/32=1.56), `test_polish_invokes_codex_with_expected_argv` (stejný fake výstup), `test_polish_uses_config_timeout_and_strips_model` (24/15=1.6). Latentní chyba zděděná ze specu. **Fix:** Task 5 rozdělen na Step 1a (verbatim-safe) + Step 1b (3 opravené verze s bezpečným poměrem, inline).

### IMPORTANT
- **`_print_usage` používá raw `print`** (main.py:52-59), `_cmd_polish` (spec 1919) ji volá bez guardu. `BrokenPipeError` z ní → vnější `except Exception` → `run_error`/`return 1` navzdory úspěšné dávce; spec scénář 2730-2736 by pak selhal. **Fix:** Task 12 Step 3.0 - `_print_usage` `print` → `_say`; `_polish_env` už ji nemockuje.
- **Fake Codex skripty čtou `sys.stdin.read()`** - potomkův cp1252 stdin (Windows, Python <3.15) rozbije český prompt navzdory rodičovskému `Popen(encoding="utf-8")`. **Fix:** Global Constraint + Task 5 - stdin-čtoucí fake skripty používají `sys.stdin.buffer.read().decode("utf-8")`.
- **`test_polish_long_input` očekává délku bez `.strip()`** - `polish()` výstup stripuje (spec 909), `long_cz` končí mezerou. **Fix:** `.strip()` na očekávané straně.
- **Task 11/12 nepokrývaly řídicí větve** - `critic_failed` skip meaning-check, generická výjimka pokračuje, interrupt po/před commitem, `--force`+interrupt, `_client_factory` pád po `create_run`, `_run_critic` FatalRunError stopne dávku, redakční matice, provenience slepé skvrny. **Fix:** ~12 nových inline testů do Task 11 + Task 12.
- **Task 13 nevracel `config.STYLIST_ACCEPT_FS_RISK = False`** po ověření - plán by skončil s defaultně zapnutou rizikovou funkcí. **Fix:** Task 13 Step 5 POVINNÉ vrácení + `git diff config.py` kontrola.

### NITS
- Task 8 provenience test (spec 323-329) patří do Task 11 (potřebuje `_polish_one_chapter`) - přesunuto.
- Self-review tvrdil "úplné pokrytí" - změkčeno na "vědomě neplné, executor doplní ze spec seznamu".

## On Codex's points

### Agreed + fixed
- **BLOCKING délkový guard** (Codex B1): shodné s mým nálezem. Task 5 Step 1b.
- **BLOCKING `long_cz` `.strip()`** (Codex B2): fixed, `.strip()` na expected.
- **BLOCKING keep-untranslated test** (Codex B3): můj test s `expected=False` odporoval spec kódu (1291-1293 vloží `actual` do `surfaces` před `cz==canonical` checkem). Ale `concordance.check_chapter` (spec 171) takový `leak` nález NIKDY nevytvoří pro keep-untranslated termín. **Fix:** test přepsán - leak nález prostě není v `after_findings`, přidané "Mouse" → nezamítnuto. Konzistentní s kódem i spec scénářem 2631-2633.
- **IMPORTANT UTF-8 fake stdin** (Codex): fixed, viz výš.
- **IMPORTANT `_print_usage`** (Codex): fixed, viz výš.
- **IMPORTANT chybějící testy konkordance/provenience/dedup** (Codex): přidán case/deklinace test, real-`check_chapter` integrační test, dedup-B-a-A test do Task 8; provenience test do Task 11.
- **IMPORTANT chybějící backup timing testy** (Codex): přidán "nothing accepted → stará záloha zachována + snapshot uklizen" do Task 12; "no promotion on reject" do Task 11.
- **IMPORTANT chybějící řídicí větve** (Codex): ~12 testů, viz výš.
- **IMPORTANT redakční matice** (Codex): parametrizovaný test `(False,1,"False",None)` na rejected gate v Task 11; redakce `str(e)` v generic-exception testu Task 12.
- **IMPORTANT Task 13 model/config/isolace + revert** (Codex): Step 2 rozšířen o config-suppression a context-isolation kontroly, Step 3 o model-enforcement, Step 5 POVINNÝ revert.
- **NIT Task 4 rozsah 433-715** (Codex): opraveno na 433-746.
- **NIT Task 1 rozsah + fences** (Codex): opraveno na 344-400, poznámka nekopírovat markdown fence.
- **NIT Task 11 monkeypatch bordel** (Codex): vyřešeno - `from src.agents import stylist` modulově v Task 7, lokální import ze specu VYNECHÁN, jednotný `main.stylist.<attr>`.
- **NIT commit trailer** (Codex): Global Constraint - trailer VŽDY, ukázky ho pro stručnost vynechávají.

### Disagreed
Žádné - všechny Codexovy body platné.

## Claude VERDICT

`CHANGES_NEEDED` - vlastní BLOCKING (délkový guard) + shoda s Codexem na ~8 IMPORTANT. Vše aplikováno do plánu.

## Summary for log

Kolo 1: Codex CHANGES_NEEDED (3 BLOCKING, 7 IMPORTANT, 3 NITS), Claude CHANGES_NEEDED (1 vlastní BLOCKING, shoda na zbytku). Hlavní: 3 spec-verbatim testy porušují délkový guard (latentní spec chyba) → Task 5 opravené verze; `_print_usage` raw print → `_say`; fake stdin cp1252 → `sys.stdin.buffer`; ~15 chybějících testů řídicích větví/redakce/konkordance doplněno do Task 8/11/12; Task 13 POVINNÝ revert `STYLIST_ACCEPT_FS_RISK`. Plán edituje ~10 sekcí. Sporné: 0.
