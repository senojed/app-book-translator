## BLOCKING

- Task 2, Step 5 `test_claude_cli_client_count_tokens_is_conservative_estimate()` vs. Step 7 implementation: test expects `4`, but `(len("abcd") + len("efgh")) // 4` is `2`. The specified test suite cannot pass. Fix the expected value to `2` (consistent with existing client estimate), or change the implementation and its rationale consistently.

## IMPORTANT

- Task 3 `_claude_cli_preflight()` is applied only to `run`. `agent=="critic"` is also used by batch `polish` and the polish-server regenerate path, both after an expensive Codex styling call. Missing/unlogged-in Claude CLI will therefore fail only after paid work. Invoke the same preflight before those workflows start, and add regression tests proving no stylist call occurs on failure.

- Task 3 `_claude_cli_preflight()`: `json.loads(result.stdout)` is not validated as a dict, so valid JSON such as `[]`, `null`, or `"x"` raises uncaught `AttributeError` at `status.get(...)`. It also ignores `result.returncode`. Validate a zero exit code and a dict payload with boolean `loggedIn`; convert all malformed/nonzero outcomes to the documented `(None, error)` result. Add tests for nonzero exit, malformed JSON, and non-object JSON.

- Task 2, Step 3 `_exec_claude()` validates only that `usage` is a dict, despite claiming numeric validation. `input_tokens`/`output_tokens` may be strings, booleans, negatives, or floats; `PipelineLLMClient` subsequently performs arithmetic and can crash or write invalid audit data. Validate both fields as non-negative integers when `usage` is present, or explicitly use safe integer defaults. Add tests.

## VERDICT

CHANGES_NEEDED