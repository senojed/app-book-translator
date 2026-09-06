# Round 4 — Claude critique (plán)

## Claude's own findings

### IMPORTANT
- **`_guard` chytal `except Exception` kolem `count_tokens` → spolkl by
  `FatalRunError`** (z `count_tokens` u neznámého modelu). → Opraveno:
  `except FatalRunError: raise` před generickým fallbackem.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `FatalRunError` z `critic.review` spolknut → kapitola `flagged`** —
  opraveno: pipeline chytá `except FatalRunError: raise` PŘED recoverable
  handlingem kritika. Test `test_critic_fatal_error_propagates_not_flagged`.
- **IMPORTANT: `_price()` vrací `0.0` pro neznámý model → cost guard tiše off** —
  opraveno: neznámý model v PRICE dict → `FatalRunError`. Test
  `test_unknown_model_price_raises_fatal`.
- **IMPORTANT: `float(ans)` na strop → `ValueError` může být bráno jako
  chapter error** — opraveno: cost guard 1 prompt + 1 reprompt na nevalidní
  vstup, pak `FatalRunError`. Test `test_cost_guard_invalid_ceiling_input_raises_fatal`.
- **IMPORTANT: export test coverage tenká** — opraveno: `test_export_full_markers`
  (flagged → `REVIDOVAT`, needs_human/error → `CHYBÍ KAPITOLA` + stdout varování,
  read-only assertion) + `test_export_only_done`.
- **IMPORTANT: review reseed negative test neefektivní** — opraveno: rozděleno na
  `test_review_reseeds_on_success` a `test_review_does_not_reseed_on_failure`
  (fresh DB, guide "uložen" ale rc=1 → `glossary.all_terms() == []`, rc == 1).
- **NIT: `except (OutputTruncated, ValueError, Exception)` == `except Exception`** —
  opraveno: `except Exception` s poznámkou že `KeyboardInterrupt` není `Exception`.
- **NIT: Task 16 nespouští `test_cli.py` explicitně** — opraveno: Step 6 přidán.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 1 BLOCKING (Codex) reálný (critic FatalRunError → flagged),
Claude 1 vlastní IMPORTANT (guard spolkne FatalRunError z count_tokens). Zbytek
test coverage. Rozsah klesá, chce 1 potvrzovací kolo.

## Summary for log
Kolo 4: Codex 1 BLOCKING (critic FatalRunError spolknut → flagged) + 4 IMPORTANT
(price 0.0 pro neznámý model; float(ans) ValueError; export coverage; review
reseed negative test) + 2 NIT. Claude 1 vlastní IMPORTANT (_guard except Exception
kolem count_tokens spolkne FatalRunError). Opraveno: FatalRunError se všude chytá
PRVNÍ a re-raise; _price raise na neznámý model; cost guard reprompt+fatal na
nevalidní vstup; export full-marker + only-done + read-only testy; review reseed
pozitivní/negativní test. Sporné: nic.