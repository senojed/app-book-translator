## BLOCKING

- Task 10, Step 3 (`LockLostError`): `_polish_one_chapter()` catches every `FatalRunError` and rethrows a new base `FatalRunError`. `LockLostError` therefore never reaches `except main.LockLostError` in `post_regenerate`; real lock loss returns 500, not required 503. Fix: add `except LockLostError: raise` before `except FatalRunError`, and test through real `_polish_one_chapter`, not a mock that raises `LockLostError` directly.

## IMPORTANT

- Task 11, `scope="history"`: resolving a history finding updates only `polish.history.json`; UI and report deliberately read only `chapters.notes`. The endpoint returns success but does not change the visible/current finding state, creating divergent `resolved` values. Fix: remove the unsupported `history` scope and its test, or atomically update matching current notes as well.

## VERDICT
CHANGES_NEEDED