## BLOCKING

- Task 2, Step 3: Implementace spojuje `system` a `user` do stdin; odporuje specifikaci, která vyžaduje `--system-prompt`. Instrukce kritika tak nemají systémovou prioritu vůči obsahu kapitoly. Opravte argv na `--system-prompt system` a stdin ponechte pouze pro `user`; doplňte test hranice rolí.

## IMPORTANT

- Global Constraints vs. Task 2 Steps 5/7: Timeout je jednou definován jako `ClaudeCliFatalError`, ale implementace jej záměrně nechává nefatální. To mění výsledný status kapitoly a odporuje specifikaci. Zvolte jedno chování, sjednoťte spec, implementaci a testy.
- Task 2, Step 3: Kontroluje se jen `is_error`; specifikace vyžaduje chybu i pro `subtype != "success"`. JSON pole navíc nejsou typově validována; `[]`, chybějící/neřetězcový `result` nebo nečíselné `usage` uniknou jako jiné výjimky či rozbijí audit. Validujte celý kontrakt payloadu a testujte každý případ.
- Task 2, Step 7: `ClaudeCliClient` přebaluje jen tři konkrétní výjimky. `UnicodeError` při dekódování stdout a další chyby wrapperu uniknou bez redakce do pseudo-nálezu/DB, přestože plán slibuje redakci chyb CLI. Zachyťte očekávané I/O/dekódovací/protokolové chyby a převeďte je na redigovaný `ClaudeCliFatalError`.
- Task 3: Po odstranění API preflightu zůstává dostupnost a OAuth autentizace `claude` CLI čistě líná. Při `--translator codex` může být přeložena placená kapitola, než kritik zjistí chybějící CLI nebo expirované přihlášení. Přidejte před frontu explicitní Claude CLI preflight a test, že při selhání není zavolán `process_chapter`.
- Task 2, Step 7: `max_tokens` se ignoruje a `truncated=False` je vždy. Tím se obchází retry mechanismus `critic.review()` a limit `MAX_TOKENS_CRITIC` nemá účinek. Zdokumentujte podporovaný ekvivalent CLI a mapujte jeho stav ukončení; pokud neexistuje, změňte kontrakt/retry tak, aby se nehlásilo nepravdivé „netruncated“.

## VERDICT

CHANGES_NEEDED