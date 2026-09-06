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
