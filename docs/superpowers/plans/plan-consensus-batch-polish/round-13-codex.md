## IMPORTANT

- Task 10, `post_regenerate`: `require_lock()` není bezprostředně před `state.create_run()`: mezi nimi je `glossary.all_terms()`. Zámek může mezitím zaniknout a auditní zápis pak poruší vlastní Global Constraint. Přidej re-check přímo před `create_run` a regresní test ztráty zámku v tomto okně.

- Task 5/10, CLI `_cmd_polish` a `PipelineLLMClient(require_lock=None)`: odmítnuté zdůvodnění není dostačující. `_cmd_polish` nemá heartbeat; při dlouhém Codex/LLM volání může lock zestárnout a být převzat, zatímco následný `record_llm_call` zapíše bez ověření. Refresh až před chapter commitem je příliš pozdě. CLI musí refreshovat/ověřit lock před `create_run` i před každým auditním zápisem, obdobně jako server.

## VERDICT

CHANGES_NEEDED