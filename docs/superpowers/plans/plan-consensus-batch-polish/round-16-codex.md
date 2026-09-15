## BLOCKING

- Task 10, `PipelineLLMClient.complete()`: `require_lock()` je až po `_guard()`. `_guard()` může při interaktivním navýšení limitu zapsat `runs.spend_ceiling` bez ověřeného zámku. Přesuň kontrolu před `_guard()` a zopakuj ji po `_guard()` těsně před LLM voláním; přidej test s překročeným limitem a ztraceným zámkem, který ověří nulový DB zápis.

## IMPORTANT

- Task 10, `post_regenerate()`: ztráta zámku uvnitř `PipelineLLMClient.complete()` vyhodí `FatalRunError`, kterou obecný `except Exception` přeloží na HTTP 500. Rozhraní ale slibuje 503 pro zámek. Zaveď rozlišitelnou výjimku pro ztrátu zámku a mapuj ji na 503; přidej endpointový test ztráty zámku po `create_run`, před LLM voláním.

## VERDICT

CHANGES_NEEDED