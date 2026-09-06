## BLOCKING

- `Task 15`, ř. 2080: `pipeline.process_chapter(..., guide=g)` používá `g`, ale plán nikde v `run` větvi nedefinuje načtení guide.
  - Fix: před smyčkou explicitně `g = guide.load_guide(config.GUIDE_PATH)` a test na `run` bez existujícího `guide.json`.

- `Task 15`, ř. 2037-2040: `canonical_en=scope_key` používá nedefinovanou proměnnou. Má být `q["scope_key"]`.
  - Fix: přepiš přesně na `scope_key = q["scope_key"]` před větvením, nebo používej přímo `q["scope_key"]`.

## IMPORTANT

- `Task 15`, ř. 2033+: `apply_answer` nejdřív volá `state.answer_question`, potom mění glossary/guide/requeue. Když pozdější krok spadne, otázka zůstane zodpovězená, ale rozhodnutí se nemusí propsat.
  - Fix: pro DB část použít jednu transakci; u guide JSON aspoň validovat před `answer_question` a psát přes temp file + atomický replace. Přidat test selhání uprostřed.

- `Task 9`, ř. 1307+: lock je popsaný jako “soubor neexistuje → zapiš”. To není atomické; dva procesy mohou lock vzít současně.
  - Fix: atomické vytvoření přes `os.open(..., O_CREAT|O_EXCL)` / ekvivalent pro Windows; po stale locku recheck + atomický replace. Přidat race-oriented test aspoň na double acquire.

- `Task 6`, ř. 984 vs spec ř. 512: spec říká “approved vyhrává”, ale plán u `seed_from_guide` říká jen že `status` se nezmění, ne že se nesmí přepsat `cz`, `accepted_alt`, `type`, `note`.
  - Fix: explicitně: pokud existující řádek `status="approved"`, reseed nesmí měnit `cz/status/accepted_alt`; může max doplnit aliasy/note podle jasného pravidla. Přidat test.

- `Task 12`, ř. 1631-1634 + `Task 15`, ř. 2039-2040: blocking `scope_key` se normalizuje na lowercase a pak se použije jako `canonical_en`. Tím se trvale ztratí původní povrch (“The White Council” → “the white council”).
  - Fix: ukládat zvlášť stabilní dedup key a původní surface, nebo `scope_key` neničit lowercase normalizací.

- `Task 5`, ř. 894-896: když `count_tokens` selže non-fatal výjimkou, cost guard použije hrubý `len/4` odhad. To je pro cost guard slabé místo.
  - Fix: buď `FatalRunError`, nebo konzervativní horní odhad. Přidat test, že selhání `count_tokens` nepustí volání podceněné.

- `Task 15`: testy nepokrývají `scan` lifecycle: `OutputTruncated` / `ValueError` ze scouta → `FatalRunError`, `finish_run(status="fatal")`, žádný zápis draftu.
  - Fix: přidat CLI test pro obě chyby.

## NITS

- `Task 9`: stale lock test používá `ts: "old"`. Plán by měl říct, že neparsovatelný timestamp = stale, jinak executor může implementovat parser, který spadne.

- Ověřil jsem aktuálnost model ID jen orientačně: Anthropic docs uvádí `claude-sonnet-5` jako Active. Zdroj: https://docs.anthropic.com/en/docs/about-claude/model-deprecations

## VERDICT

CHANGES_NEEDED