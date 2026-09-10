# Round 7 — Claude critique

Codex: CHANGES_NEEDED (1 IMPORTANT, 3 NITS). Konvergence: úzké body.

## Claude's own findings
Žádné nové vlastní.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - redakce ve skutečné `_run_critic` neověřena:** testy `_run_critic` mockují. Nový `critic.review` dává `data.get('verdict')!r` do `ValueError`; `_run_critic` z ní staví pseudo finding `issue="kritik selhal: {e}"`. **Analýza:** default-safe JE - pseudo jde jen do `findings`, ne do `rec` (`_rejection_reasons` ho nevybere, má `action="note"`); `reason_types` má jen fixní `critic/critic_failed`; `_run_critic` nic netiskne (ověřeno `src/pipeline.py:52-63`). **Fix (belt-and-suspenders):** Task 11 integrační test `test_polish_one_chapter_real_critic_failure_redacts_by_default` - SKUTEČNÝ `critic.review`+`_run_critic`, fake klient vrací `verdict:"SECRET123"` 2×, opt-in OFF → assert secret není v `rec` ani stdout.
- **NIT - canary runner jen timeout, ne Ctrl+C:** **Fix:** `except BaseException` (timeout i KI) → `_kill_process_tree` + omezený wait; úklid `T1`/`T2` v `finally`.
- **NIT - `open(out.txt).read()` bez encoding:** **Fix:** `open(of, encoding="utf-8")`.
- **NIT - `_polish_one_chapter` docstring "tři append větve" stale:** **Fix:** Task 11 Step 3 - druhá odchylka, uprav větu docstringu na "JEDEN append ve `finally`, `rec` dopočítán z DB".

### Disagreed
Žádné.

## Claude VERDICT

`CHANGES_NEEDED` - 1 IMPORTANT (belt-and-suspenders test) + 3 NITS. Vlastních 0. Blížíme se konsensu.

## Summary for log

Kolo 7: Codex 1 IMPORTANT + 3 NITS. IMPORTANT: redakce ve skutečné `_run_critic` - analýza ukázala default-safe, přidán integrační test jako pojistka. NITs: canary runner `except BaseException` + `finally` úklid + utf-8 encoding; docstring "tři append" → "jeden ve finally". Sporné: 0. Konvergence: 0 BLOCKING už 4 kola za sebou, IMPORTANT klesá.
