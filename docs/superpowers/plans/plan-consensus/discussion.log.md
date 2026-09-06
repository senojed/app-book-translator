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

## Kolo 3 — 2026-09-06T18:26:20Z
- Codex: CHANGES_NEEDED (3 BLOCKING, 3 IMPORTANT, 2 NIT) → round-3-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-3-claude.md
- BLOCKING: run používal interactive=False (jako scan) → run=interactive=True, jen scan hard-stop. apply_answer promote na scope_key blocking otázek co nejsou term_id → blocking scope_key = povrch, apply_answer má resolve_term_or_surface + add_approved (nové glossary helpery). must_decide odpovědi se nikam nezapisovaly → server.apply_must_decide routuje do terms/characters/relationships/rules podle kind, pak must_decide smaže.
- IMPORTANT: nové termíny v kapitole exempt z concordance té kapitoly (v1 chování explicitní); review reseed automatizovaný test (monkeypatch run_review_server 0/1); INSERT + IntegrityError remap místo INSERT OR IGNORE (visící FK).
- NIT: nt/cand naming sjednoceno; test count review UI.
- Sporné: nic.

## Kolo 4 — 2026-09-06T18:32:32Z
- Codex: CHANGES_NEEDED (1 BLOCKING, 4 IMPORTANT, 2 NIT) → round-4-codex.md
- Claude: CHANGES_NEEDED (1 vlastní IMPORTANT) → round-4-claude.md
- BLOCKING: FatalRunError z critic.review spolknut → kapitola flagged, run pokračuje → oprava: FatalRunError se všude chytá PRVNÍ a re-raise (pipeline critic handling, _guard kolem count_tokens).
- IMPORTANT: _price 0.0 pro neznámý model = cost guard tiše off → raise FatalRunError. float(ans) na strop ValueError → reprompt 1x, pak FatalRunError. Export coverage tenká → full-marker/only-done/read-only testy. Review reseed negative test neefektivní → rozděleno pozitivní/negativní (fresh DB, guide uložen ale rc=1 → žádný reseed).
- NIT: except Exception (ne trojice); Task 16 spouští test_cli.py.
- Sporné: nic. Rozsah klesá.

## Kolo 5 — 2026-09-06T18:39:37Z
- Codex: CHANGES_NEEDED (1 BLOCKING, 6 IMPORTANT, 3 NIT) → round-5-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-5-claude.md
- BLOCKING: os.kill(pid,0) na Windows = TerminateProcess → _pid_alive platform-specific (POSIX os.kill, Windows ctypes OpenProcess), lock přebírá zámek starší 6h.
- IMPORTANT: merge_draft_and_guide výstup = finální názvy polí (cz/render/style/address) předvyplněné z draft suggested_*; apply_answer syntaxe "cz | alt1 | alt2" → accepted_alt; scout.chunk_chapters greedy packing pod SCOUT_CHUNK_WORD_LIMIT=40000 + CLI; cost guard new_limit >= spent+est; drift scheduling přesně (po done/flagged commitu, count % N); Task 16 validace vyjmenovat required pole.
- NIT: test counts (Task 14→7, Task 11→7, Task 5→8).
- Sporné: nic.

## Kolo 6 — 2026-09-06T18:43:56Z
- Codex: CHANGES_NEEDED (3 BLOCKING, 4 IMPORTANT) → round-6-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-6-claude.md
- BLOCKING: merge test vs interface rozpor (newguy render) → test opraven na "translate". chunk_chapters čekal objekt, CLI předává dict → přijímá oboje. validation PŘED apply_must_decide → nesmyslná odpověď se uloží → POST pořadí: answered-check → apply_must_decide → PLNÁ validace výsledku → save.
- IMPORTANT: Task 11 code fence neuzavřený → doplněn. critic failure action:"note" nespustí flagged → explicitní critic_failed flag. scan ValueError bublá jako stacktrace → except (OutputTruncated,ValueError)→FatalRunError. must_decide routing testy jen term → přidány name/relationship/style/update-existing.
- Sporné: nic.

## Kolo 7 — 2026-09-06T18:50:44Z
- Codex: CHANGES_NEEDED (2 BLOCKING, 6 IMPORTANT, 2 NIT) → round-7-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-7-claude.md
- BLOCKING: run nenačítá g=guide.load_guide → doplněno + test bez guide.json. apply_answer nedefinované scope_key → scope_key=q["scope_key"].
- IMPORTANT: apply_answer ordering (guide atomicky → DB v jedné transakci); save_guide/save_draft atomické temp+os.replace; lock os.open(O_CREAT|O_EXCL) atomické; seed_from_guide u approved nesahá na cz/status/accepted_alt (jen aliasy); blocking scope_key neztrácí velikost písmen (jen strip, ne lower); count_tokens fail → len/2 konzervativní nadhad; scan lifecycle testy (truncated/bad json → fatal, žádný draft).
- NIT: neparsovatelný lock ts = stale.
- Sporné: nic.

## Kolo 8 — 2026-09-06T18:56:41Z
- Codex: CHANGES_NEEDED (2 BLOCKING, 4 IMPORTANT, 1 NIT) → round-8-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-8-claude.md
- BLOCKING: init bere lock ale data/ neexistuje + chybí state.init_db → main() dělá bootstrap_stdout + makedirs + init_db PŘED dispatchem. Task 8 test "Fů"/"Fůha" - stem je sjednotí → test data "Šedý plášť"/"Popelář".
- IMPORTANT: new_terms shoda s existujícím povrchem "přeskoč" → ztráta mention → přidej explicitní mention s resolved term_id. style/other scope_key hash remap nespecifikován → pipeline normalizuje všechny questions (sha1(text)[:16]). apply_answer atomicita falešná → state.commit_answer jednotransakční helper (glossary_ops SQL nad conn). stale lock takeover race → unlink + O_EXCL retry smyčka.
- NIT: validate čte payload.get(section, []).
- Sporné: nic.
