## BLOCKING

- Task 10, `post_regenerate`: LLM klient během `_polish_one_chapter` zapisuje `llm_calls` (a případně `runs` cost-limit) bez nového `app.state.require_lock()` bezprostředně před zápisem. Kontrola jen před `create_run` a `finish_run` nesplňuje vlastní Global Constraints; zámek lze během dlouhého volání ztratit. Oprav: předej do `PipelineLLMClient`/`_client_factory` callback ověřující zámek před každým auditním zápisem; při ztrátě vyhoď řízenou chybu. Přidej test ztráty zámku před `record_llm_call`.

## IMPORTANT

- Task 13, Step 8 migrace: `chapters.notes` se commitne dříve než se uloží upravená historie. Selže-li následné `save_history`, zůstane migrace napůl; existující zálohy se pouze vytvoří, ale plán neurčuje automatický rollback ani konkrétní recovery postup. Oprav: implementuj kompenzační rollback z obou záloh při selhání druhého zápisu, bezpečným atomickým restore postupem, a otestuj selhání `save_history`.

## VERDICT

CHANGES_NEEDED