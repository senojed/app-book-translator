## BLOCKING

- **`critic.review()`, lines 45–104:** Validation remains fail-open. Only `verdict=="revise"` is handled; missing or invalid `verdict` with empty `findings` passes. Strictly validate the complete schema and retry/reject any response where `verdict` is not exactly `pass|revise`, `findings` is not a list, or verdict and findings conflict.

## IMPORTANT

- **Guardrails, lines 306–318 and 390–402:** The earlier deterministic-check finding was only partially fixed. Paragraph count and total length do not detect changed numbers, dates, amounts, names, or dialogue structure. Add deterministic before/after invariants for numerals and other protected tokens; explicitly define allowed transformations.
- **Acceptance logic, lines 491–522:** Baseline comparison uses stale `notes` and only `(type, term_id)`. Glossary changes can create false “new” findings, while changing one bad `actual` value into another remains undetected. Recompute concordance for `cz_before` using the current glossary and compare normalized finding signatures including relevant values and severity/action.
- **`term_mentions`, lines 541–555:** Rebuilding with `rendered_terms=[]` cannot recover arbitrary translated forms previously supplied by the translator. The atomic commit deletes valid observations and may replace them with false omissions, corrupting later drift checks. Preserve still-present prior mentions or implement deterministic extraction of actual forms before replacing them.
- **Quality objective, lines 5–16 and 500–505:** The plan verifies safety but never verifies that style improved. All noncritical fluency/register findings are accepted, so a noticeably worse yet readable rewrite can replace the approved text. Add a comparative before/after style evaluation and require the new version to be preferred or demonstrably no worse.
- **Preflight and failure classification, lines 568–576 and 610–615:** The round-3 authentication/model issue is not actually fixed. `shutil.which` checks only executable presence; invalid credentials, unsupported model, or incompatible CLI still cause one failed invocation per chapter and exit successfully with run status `ok`. Perform one real capability check or classify nonzero CLI configuration/authentication failures as fatal.
- **Codex invocation, lines 275–284:** Codex sessions are persistent by default, so deleting the temporary directory does not ensure the chapter content disappears from local Codex session history. Add `--ephemeral`. Prefer `codex exec -` with `subprocess.run(input=prompt_text, ...)`, which the installed CLI supports and avoids requiring the agent to read a plaintext prompt file.

## NITS

- **CLI filtering, lines 578–586:** `--only` silently succeeds when requested chapters are absent, not `done`, or already styled. Report skipped IDs and reasons, matching existing `run --only` behavior.
- **Output validation, lines 296–318:** A fenced or prefaced response can satisfy paragraph and length checks and later be accepted as a minor formatting issue. Reject Markdown fences and obvious response wrappers deterministically.

## VERDICT

CHANGES_NEEDED