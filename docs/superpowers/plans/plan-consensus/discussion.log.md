# Plan-consensus (implementační plán) - discussion log

Plán: docs/superpowers/plans/2026-09-06-book-translator.md
Spec: docs/superpowers/specs/2026-09-06-book-translator-design.md
Start: 2026-09-06T18:00:40Z
Max kol: 10

---

## Kolo 1 — 2026-09-06T18:13:29Z
- Codex: CHANGES_NEEDED (3 BLOCKING, 8 IMPORTANT, 3 NIT) → round-1-codex.md
- Claude: CHANGES_NEEDED (3 vlastní IMPORTANT) → round-1-claude.md
- BLOCKING: import 'state' z repo root selže → import layout formalizován (conftest.py, pyproject pythonpath=["."], "from src import X" uvnitř src, lazy import state v client.py). Rozbitá translator metadata → tichá ztráta → nyní ValueError (marker přítomen+nevalidní JSON), chybějící marker = tolerovat. Transakce B nedospecifikovaná + commit_chapter_result mimo interface → plná spec state.begin_chapter (transakce A) + state.commit_chapter_result (transakce B, argumenty/kroky/rollback/atomicity test), pipeline počítá mentions/candidates PŘED transakcí.
- IMPORTANT: term_id konvence sjednocena na "term_"+slug; guide dostal 'terms' sekci (load/merge/seed/testy); merge_scout_facts section-specific klíče; drift stemmer definován (stem/form_key + testy + poznámka o limitech); critic parse-retry testy; závazné pořadí except v run (FatalRunError první); create_run/finish_run v try/finally.
- Claude vlastní: pipeline volá agenty modulově-kvalifikovaně (monkeypatch); run smoke testy; run_drift_check test.
- NIT: Task2 7 testů; CALIBRATION_CHAPTERS pryč.
- Sporné: nic.

## Kolo 2 — 2026-09-06T18:19:49Z
- Codex: CHANGES_NEEDED (2 BLOCKING, 4 IMPORTANT, 2 NIT) → round-2-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-2-claude.md
- BLOCKING: nový termín z new_terms nedostal term_mentions řádek (build_mentions před vložením kandidátů) → requeue ho nenašel → oprava: kandidáti do glossary_rows PŘED build_mentions + navíc explicitní mention {term_id, cz_form, chapter_idx, source:"rendered"} pro každý nový kandidát. finish_run ve finally i except → jeden závazný lifecycle pattern (status default "fatal", "ok" jen po úspěchu, jediný finish_run ve finally).
- IMPORTANT: relationship_key plán vs spec rozpor → SPEC upraven (bez resolve_surface, v1 omezení, plán+spec souhlasí). load_guide KeyError na chybějícím terms → load_guide normalizuje plný shape i pro starý soubor. cost guard scan má tvrdě zastavit → PipelineLLMClient interactive param (False = FatalRunError bez ptaní), scan/run předává interactive=False. Task 14 chybí requeue-po-kandidátovi test → end-to-end test v Task 15.
- NIT: test counts Task 6→6, Task 7→8, Task 5 doplněn.
- Sporné: nic.
