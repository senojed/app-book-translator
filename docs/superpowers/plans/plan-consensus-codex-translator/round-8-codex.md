## IMPORTANT

- Task 5, `_cmd_run` replacement: Preflight is moved before `state.recover_processing()`. A failed `run --translator codex` now leaves previously crashed chapters in `processing`, unlike every prior `run`. Run recovery before the preflight early return; preflight still remains before queue creation. Add regression test.

- Tasks 3 and 5, Codex error redaction: `CodexLLMClient` wraps `OSError`/`UnicodeError` as `FatalRunError(str(e))`; `_cmd_run` prints `FatalRunError` directly. This bypasses the planned Codex redaction path. Redact at wrapping or in the fatal handler, and test an `OSError("secret")` with reporting disabled.

- Task 3, `test_pipeline_client_uses_billed_model_for_price_not_caller_model`: The test verifies audit price/model but not `_guard()`. An implementation could still guard using the caller’s Claude model, causing erroneous cost-limit stops. Add a non-interactive test with `MAX_SPEND_USD=0` and a large `max_tokens`; Codex must proceed because its effective price is zero.

## VERDICT

CHANGES_NEEDED