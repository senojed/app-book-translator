# Round 1 — Claude critique (plán)

## Claude's own findings

### IMPORTANT
- **Monkeypatch pipeline testů předpokládá modulově-kvalifikované volání agentů.**
  Testy Tasku 14 dělají `monkeypatch.setattr(T, "translate_scene", ...)`. Pokud
  pipeline importuje `from src.agents.translator import translate_scene`, patch
  na modulu nezabere. → Přidán global constraint: pipeline volá
  `translator.translate_scene` / `critic.review` (modulově), a explicitní pokyn
  v Task 14 Step 3b.
- **`run` příkaz neměl smoke test.** Task 15 testoval init/status/export, ne
  `run`. → Přidány 2 testy: `test_run_processes_queue_with_monkeypatched_pipeline`
  a `test_run_fatal_error_closes_run_and_exits_nonzero`.
- **`run_drift_check` neměl test.** → Přidán do Task 14.

### NITS
- `Finding` přístup: testy používají `finding["type"]` (dict), ale interface
  říkal "dataclass". → Upřesněno: `TypedDict` nebo dict factory.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `import state` v client.py selže z repo root** — opraveno:
  `from src import state` (lazy, uvnitř metod) + nový global constraint o import
  layoutu + `conftest.py` + `pyproject` `pythonpath = ["."]` v Tasku 1.
- **BLOCKING: rozbitá translator metadata → tichá ztráta otázek/termínů** —
  opraveno: `===METADATA===` marker přítomen + nevalidní JSON → `ValueError`
  (kapitola `error`); marker úplně chybí → tolerovat prázdné. Test
  `test_broken_metadata_keeps_translation` nahrazen dvěma
  (`test_broken_metadata_json_raises`, `test_missing_metadata_section_tolerated`).
  Global constraint doplněn.
- **BLOCKING: transakce B nedospecifikovaná + `commit_chapter_result` mimo
  interface** — opraveno: plná specifikace `state.begin_chapter` (transakce A)
  a `state.commit_chapter_result` (transakce B) v Interfaces Tasku 14, včetně
  argumentů, kroků a rollbacku. Pipeline počítá `mentions`/`new_candidates`
  PŘED transakcí (concordance/glossary volání), state zůstává čisté. Přidán
  atomicity test (`test_commit_chapter_result_is_atomic` - FK porušení uprostřed
  → nic se nezapíše).
- **IMPORTANT: seeded `term_id` konvence rozpor** (global `slug` vs Task 6
  `term_` + slug) — opraveno: global constraint sjednocen na `"term_" + slug`;
  přidán `test_fresh_seed_id_and_terms_section`.
- **IMPORTANT: guide postrádá `terms`** — opraveno: `terms` doplněno do
  `load_guide`, `load_draft`, `merge_draft_and_guide` (klíč `term_en`),
  `seed_from_guide` (iteruje i `guide["terms"]`), testy
  (`test_load_guide_missing_returns_empty_shape`, `test_merge_carries_draft_terms`).
- **IMPORTANT: `merge_scout_facts` používá `name_en` i pro terms** — opraveno:
  section-specific klíče (`characters.name_en`, `places.name_en`,
  `terms.term_en`); přidán `test_merge_dedups_terms_by_term_en`.
- **IMPORTANT: drift stemming vágní** — opraveno: definovány `stem`, `form_key`
  (per-slovo stem join), `check_drift` grupuje podle `form_key`. Test
  `test_check_drift_groups` asertuje přesné kapitoly; přidány
  `test_check_drift_no_finding_for_simple_inflection`,
  `test_form_key_collapses_simple_inflection_not_different_stems`. Poznámka že
  naivní stemmer Češtinu plně nezvládne (otevřená otázka k pilotu).
- **IMPORTANT: critic parse-error retry netestován** — opraveno: přidány
  `test_review_retries_on_bad_json_then_succeeds`,
  `test_review_raises_valueerror_on_repeated_bad_json`.
- **IMPORTANT: `except Exception` v `run` by chytil `FatalRunError`** —
  opraveno: závazné pořadí `except` v Task 15 (`FatalRunError` PRVNÍ → re-raise),
  s konkrétním kódem.
- **IMPORTANT: `create_run`/`finish_run` fatal cesty** — opraveno: `run`/`scan`
  tělo v `try/finally`, `finally: finish_run(rid, status)` (`ok`/`fatal`/
  `interrupted`); testy ověřují `runs.status` a `ended_at`.
- **NIT: Task 2 "8 tests"** → 7.
- **NIT: `CALIBRATION_CHAPTERS` v global constraints** → odstraněno.
- **NIT: model/ceny** — Codex ověřil aktuální, bez akce.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 3 BLOCKING (Codex) + 8 IMPORTANT byly reálné (import layout,
tichá ztráta metadat, transakce B). Claude 3 vlastní IMPORTANT (monkeypatch,
run smoke, drift test). Velké změny v Task 14 - chce potvrzovací kolo.

## Summary for log
Kolo 1: Codex 3 BLOCKING (import `state`, tichá ztráta translator metadat,
transakce B nedospecifikovaná) + 8 IMPORTANT + 3 NIT. Claude 3 vlastní IMPORTANT
(pipeline monkeypatch modulově-kvalifikované volání, `run` bez smoke testu,
`run_drift_check` bez testu). Vše přijato. Klíčové: import layout formalizován
(`conftest.py`, `pythonpath`, `from src import`); `state.begin_chapter` +
`state.commit_chapter_result` plně specifikované jako transakce A/B; rozbitá
translator metadata = `ValueError` ne tiché prázdno; guide dostal `terms`
sekci; drift stemmer definován (`stem`/`form_key`); závazné pořadí `except`
v `run`. Sporné: nic.