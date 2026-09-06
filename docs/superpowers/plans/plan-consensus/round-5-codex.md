## BLOCKING

- `Task 9`, lock interface, line ~1286: plán tvrdí, že na Windows lze použít `os.kill(pid, 0)` jako liveness check. To je nebezpečné. Python docs pro Windows říkají, že jiné signály než `CTRL_C_EVENT` / `CTRL_BREAK_EVENT` vedou k `TerminateProcess`; `0` tedy není bezpečný portable check.  
  Fix: na Windows použít nedestruktivní check přes `ctypes.OpenProcess(SYNCHRONIZE, False, pid)` + `WaitForSingleObject(..., 0)`, nebo `subprocess`/`tasklist` parser. Ne `os.kill(pid, 0)`. Zdroj: https://docs.python.org/3.11/library/os.html#os.kill

## IMPORTANT

- `Task 7` + `Task 16`: nejasná konverze `style_notes` → `style` a `suggested_cz` → `cz`. Scout/draft používá `style_notes` a `terms[].suggested_cz` / `places[].suggested_cz`; `guide`, `review_ui` a `glossary.seed_from_guide` čekají finální `style`, `terms[].cz`, `places[].cz`. Testy nepokrývají běžný save termínu/place ze scout draftu.  
  Fix: explicitně definovat normalizaci v `merge_draft_and_guide`/UI POST a přidat testy pro term/place/style roundtrip až do `seed_from_guide`.

- `Task 15`, `requeue.apply_answer`: spec říká, že odpověď na term/name může přidat další schválené tvary do `accepted_alt`; plán jen volá `promote(db, tid, answer)`. Tím se ztratí schválené varianty a concordance bude dál hlásit falešné inconsistency.  
  Fix: definovat syntaxi odpovědi pro alternativy nebo samostatný CLI parametr, volat `add_accepted_alt`, přidat test.

- `Task 11`/`Task 15`, `scan --chunked`: plán definuje `scan_chunks(chunks: list[str])`, ale CLI neříká, jak chunky vytvořit z kapitol ani podle jakého limitu. Executor s nulovým kontextem může implementovat libovolné dělení. Test CLI pro `scan --chunked` chybí.  
  Fix: přidat deterministický chunking algoritmus a test, např. kapitoly skládat do chunků pod token/word limit.

- `Task 5`, cost guard: po překročení limitu akceptuje libovolné číslo jako nový strop, i menší než `spent + est`, a pak volání pustí. To odporuje smyslu guardu.  
  Fix: validovat `new_limit >= spent + est`, jinak reprompt/FatalRunError; přidat test.

- `Task 15`, drift scheduling: “Každých `CROSS_REF_EVERY_N` hotových kapitol” není implementačně přesné. Není jasné, zda počítat zpracované kapitoly, kapitoly se stavem `done/flagged`, nebo `idx % N`; test chybí.  
  Fix: definovat pravidlo, např. po úspěšném `done/flagged` commitu, když `done_or_flagged_count % N == 0`, a přidat CLI/pipeline test.

## NITS

- `Task 14` Step 4 říká “8 pipeline testů”, ale uvedených testů je 7.
- `Task 5` Step 5 říká “8 pipeline_client testů”, ale uvedených testů je 7.
- `Task 16` validace je slabší než spec “žádné prázdné povinné”; explicitně vyjmenovat required pole pro characters/places/terms/relationships.

## VERDICT

CHANGES_NEEDED