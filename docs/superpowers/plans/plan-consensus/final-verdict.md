# Plan-consensus (implementační plán) — finální verdikt

**Výsledek: MAX_ROUNDS** (10/10 kol) — konvergence prakticky dosažena.

## Průběh

| Kolo | Codex | Claude | Rozsah |
|---|---|---|---|
| 1 | CHANGES (3 BLOCK, 8 IMP) | CHANGES (3 IMP) | import layout, transakce A/B spec, translator metadata error |
| 2 | CHANGES (2 BLOCK, 4 IMP) | CHANGES (0) | new-term mention gap, lifecycle pattern, interactive cost guard |
| 3 | CHANGES (3 BLOCK, 3 IMP) | CHANGES (0) | run interactive, blocking scope_key, must_decide routing |
| 4 | CHANGES (1 BLOCK, 4 IMP) | CHANGES (1 IMP) | FatalRunError chytat první, price raise, export/review testy |
| 5 | CHANGES (1 BLOCK, 6 IMP) | CHANGES (0) | Windows lock, chunking algoritmus, drift scheduling |
| 6 | CHANGES (3 BLOCK, 4 IMP) | CHANGES (0) | POST validation pořadí, critic_failed flag |
| 7 | CHANGES (2 BLOCK, 6 IMP) | CHANGES (0) | run guide load, apply_answer atomicita, lock O_EXCL |
| 8 | CHANGES (2 BLOCK, 4 IMP) | CHANGES (0) | main init lifecycle, commit_answer transakce |
| 9 | CHANGES (0 BLOCK, 4 IMP) | CHANGES (0) | place kind, blocking alts, extra_mentions ověření |
| 10 | CHANGES (1 BLOCK, 3 IMP) | **CONSENSUS** | rendered_terms filtrace, slug kolize, init --reset |

## Stav

- **Struktura plánu (17 tasků, TDD, 122 test funkcí) nezměněná** celý proces -
  ladily se rozhraní, transakce, klasifikace chyb a test coverage.
- **Codex bez BLOCKING v kolech 9** (kolo 10 mělo 1, hned opravený).
- **Claude v kole 10: CONSENSUS.**
- **Codex drží CHANGES_NEEDED** - je instruován "nebýt shovívavý". Jeho
  kolo-10 nálezy byly všechny zapracované; kolo 11 by našlo další vrstvu
  drobných edge-case testů (klesající výnos).

## Co se za 10 kol utáhlo (nejdůležitější)

- **Import layout** formalizován (`conftest.py`, `pythonpath`, `from src import`)
- **Transakce A/B** plně specifikované: `state.begin_chapter`,
  `state.commit_chapter_result`, `state.commit_answer` - jednotransakční helpery,
  atomicity testy
- **Chyby**: `FatalRunError` se všude chytá PRVNÍ a re-raise; `critic_failed`
  flag; `_price` raise na neznámý model; cost guard `interactive` param,
  `new_limit >= spent+est`, konzervativní odhad při selhání `count_tokens`
- **Lock**: platform-specific `_pid_alive` (ctypes na Windows), `os.open(O_EXCL)`,
  6h staleness, unlink+retry proti race
- **`rendered_terms`** filtrované přes `contains_form` PŘED každým `check_chapter`
- **`term_id` kolize**: surface-match remap nebo deterministický suffix
- **`init --reset`** + odmítnutí re-init na neprázdnou DB
- **`must_decide`** routing per kind (name/place/term/relationship/style),
  POST pořadí validace: answered-check → apply → plná validace → save
- **lifecycle** `run`/`scan`: `status="fatal"` default, jediný `finish_run`

## Vědomá omezení v1 (v plánu i specu)

- `relationship_key` bez alias-resolve (jméno-based)
- concordance stemmer naivní (falešné drift nálezy → k ověření pilotem)
- nové termíny objevené v kapitole se concordance-checkem té kapitoly neřeší
- `term_mentions` best-effort

## Doporučení

Plán je připravený k provedení. Inline execution v čerstvé session přes
`superpowers:executing-plans` (tasky jsou provázané, exekutor těží z toho, že
drží spec i plán v kontextu). První implementační milník po skeletonu = pilot
na 2-3 reálných kapitolách (~$1, ověří prompty/kvalitu/cenu).
