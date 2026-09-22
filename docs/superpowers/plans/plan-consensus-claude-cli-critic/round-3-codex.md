## BLOCKING

- Task 3, `_cmd_polish` a `polish_server` regenerate: `_client_factory` mění jen `agent=="critic"`. Následný `cf("stylist_check")` v `_polish_one_chapter()` zůstane `AnthropicClient`; při úspěšném kritiku tedy po placeném Codex stylování stále vyžaduje `ANTHROPIC_API_KEY` a API volání. Preflight CLI tomu nezabrání. Oprava: buď přepnout i `stylist_check` na `ClaudeCliClient`, nebo zachovat a eager ověřit API klíč před stylováním; upravit cíl a manuální testy podle zvolené varianty.

## IMPORTANT

- Task 3, `_claude_cli_preflight()` a volání `_client_factory`: preflight vrací absolutně resolvnutý `claude_cmd`, ale všechny tři cesty jej zahodí a factory znovu používá `["claude"]`. Mezi preflightem a skutečným voláním se tak může změnit PATH/binárka; preflight také neověřuje binárku, která se nakonec spustí. Oprava: předat `claude_cmd` do `_client_factory`/`ClaudeCliClient` a používat výhradně preflightem resolvnutou cestu.

- Task 2, validace `usage` a `ClaudeCliClient.complete()`: `usage` i obě tokenová pole jsou volitelné; při chybějících či nulových hodnotách klient tiše zapíše `1`. To falšuje audit `llm_calls` a skryje změnu/poškození CLI kontraktu. Oprava: vyžadovat `usage.input_tokens` i `output_tokens` jako nezáporná celá čísla, nebo explicitně používat `None`/zdokumentovaný odhad a testovat jej; nikdy nepřepisovat skutečnou nulu na 1.

## VERDICT
CHANGES_NEEDED