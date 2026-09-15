## BLOCKING

- Task 10, `PipelineLLMClient.complete()` / `_guard()`: zámek se kontroluje před `_guard()` a až po něm, ale `_guard()` může po interaktivním `input()` zapsat `state.set_run_spend_ceiling()` mezi těmito kontrolami. Zámek tedy může během čekání zmizet a auditní zápis proběhne bez vlastnictví zámku. Předej callback do `_guard()` a ověř jej bezprostředně před `set_run_spend_ceiling()`; při selhání vyhoď `LockLostError`. Přidej test ztráty zámku právě mezi počáteční kontrolou a potvrzením uživatele.

## NITS

- Task 11, `post_resolve_finding`: `UPDATE chapters SET notes=?` nemění `updated_at`, přesto seznam kapitol zobrazuje „Naposled upraveno“. Doplň `updated_at=CURRENT_TIMESTAMP`.

## VERDICT
CHANGES_NEEDED