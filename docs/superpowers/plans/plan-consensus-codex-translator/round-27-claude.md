# Round 27 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (checkpoint uloží `flagged`, ale re-raise ho nechá main.py
  přepsat na `error`):** Souhlasím - ověřil jsem přesně proti main.py's
  generickému `except Exception as e: state.update_chapter(status=
  "error", ...); continue` - `state.update_chapter()` mění JEN explicitně
  předané sloupce (`translated_text` zůstává), ale `status` SE PŘEPÍŠE
  z `flagged` (checkpoint) na `error`. `state.queue_for_run()` pak
  `error` kapitoly AUTOMATICKY vyzvedne PŘI KAŽDÉM dalším `run`u -
  přesně to, čemu `flagged` (kolo 10/11) mělo zabránit. Tenhle bug byl
  v MÉM VLASTNÍM kódu z kola 25 (kontrola fáze, transakce B prep) - obě
  místa blindly `raise`-ovala PO checkpointu, bez ohledu na typ výjimky.

  **Oprava:** Rozdělil jsem OBĚ `except (Exception, KeyboardInterrupt)`
  klauzule na DVĚ: `except (FatalRunError, KeyboardInterrupt) as e:`
  (opravdu fatální - checkpoint + `raise`, CELÝ run se zastaví, beze
  změny) a `except Exception as e:` (obyčejná chyba - checkpoint a
  rovnou VRÁTIT jeho výsledek, `process_chapter()` se tedy vrátí
  NORMÁLNĚ, main.py nikdy nedostane šanci status přepsat). `_checkpoint_
  flagged()` teď vrací `process_chapter()`-tvarovaný výsledek (dřív
  nevracela nic) - volající pro NEfatální větev tenhle výsledek přímo
  `return`-uje. Revizní smyčka (kolo 3/13/18/20/21/22/24) UŽ tenhle
  vzor měla správně (`except Exception: revision_failed=...; break` -
  NIKDY nere-raisovala) - jen dvě NOVÉ (kolo 25) checkpoint místa
  udělala chybu. Scénová smyčka (kolo 23/24) NENÍ dotčená - ta žádný
  `commit_chapter_result()` nevolá, jen obnovuje staré otázky a
  re-raisuje STEJNOU výjimku beze změny (main.py rozhoduje status
  přesně jako PŘED jakýmkoli z těchhle kol - žádná regrese k opravě).

  Aktualizovány TŘI existující regresní testy (kolo 25/26 - `test_
  kontrola_phase_fatal_error_preserves_scene_translation`, `test_
  transakce_b_prep_fatal_error_preserves_final_translation`, `test_
  checkpoint_glossary_fetch_failure_preserves_existing_mentions`) -
  místo `pytest.raises(...)` teď ověřují, že `process_chapter()` vrátí
  `status="flagged"` BEZ výjimky.

  **Integrační test přes `_cmd_run` (Codexův konkrétní návrh) -
  ČÁSTEČNĚ nesouhlasím s formou, ne s cílem:** Všechny existující
  testy v `tests/test_cli.py` mockují `pipeline.process_chapter` PŘÍMO
  (established hranice: `test_cli.py` testuje CLI drátování, `test_
  pipeline.py` testuje `process_chapter()`'s vnitřek) - žádný existující
  test nevolá REÁLNÝ `process_chapter()` skrz `_cmd_run`. Fix je úplně
  SEBEOBSAŽENÝ v `process_chapter()`'s návratovém chování (žádná NOVÁ
  logika v main.py) - opravené `test_pipeline.py` testy tenhle fakt už
  přímo ověřují (funkce se vrátí, ne vyhodí). Integrační test by
  vyžadoval NOVÝ vzor (translator/critic mocky v `test_cli.py`, co tam
  dnes nejsou) pro marginální přírůstek jistoty. Rozhodl jsem se cíl
  (ověřit, že se `flagged` nepřepíše) splnit přes opravené unit testy,
  ne přidávat integrační test napříč hranicí souborů.

### Agreed + fixed (NIT)

- **NIT (`// 2` odhad může vrátit `0` pro krátký neprázdný text):**
  Souhlasím - `max(1, ...)` na obou místech (`complete()`'s `input_
  tokens`/`output_tokens`, `count_tokens()`). Existující test
  (`test_codex_llm_client_calls_exec_codex_and_wraps_result`) beze
  změny - hodnoty pro jeho vstupy (3+3 znaky) jsou nad `1`, `max()`
  je neovlivní.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 27: jeden IMPORTANT bod (skutečný bug v MÉM VLASTNÍM kódu z kola
25 - checkpoint uložil `flagged`, ale blindly re-raisoval i pro
NEfatální chyby, main.py's generický handler pak status přepsal na
`error`, čímž zrušil celý smysl checkpointu) + jeden NIT (`max(1,...)`
proti nulovému token odhadu). Opraveno rozdělením except klauzulí na
fatální (checkpoint+raise) a nefatální (checkpoint+return) větev,
`_checkpoint_flagged()` teď vrací tvarovaný výsledek. Tři existující
testy upraveny na nové chování. Osmé kolo v řadě - regrese v kódu
napsaném MINULÉ kolo, ne nová nekrytá fáze.
