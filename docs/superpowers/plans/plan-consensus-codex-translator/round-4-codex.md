## BLOCKING

- Task 2, Step 3 (`_parse`, ř. 364–388): Kontrola pouze ověřuje výskyt `===KONEC===`, ne jeho pořadí ani že jde o poslední neprázdný řádek. Výstup s markerem uvnitř překladu/JSON nebo s obsahem po markeru může projít; při chybějícím `===METADATA===` se marker dokonce stane součástí překladu. To obchází právě zavedenou ochranu proti tichému přijetí neúplného výstupu. Opravte parser na přesnou strukturu a otestujte: každý marker právě jednou, pořadí `PREKLAD → METADATA → KONEC`, `raw.rstrip().endswith(MARK_END)`, žádný obsah po markeru.

- Task 5, Step 1 (`test_run_translator_flag_passed_to_client_factory`): Test spouští `run --translator codex`, ale nemockuje eager `_polish_preflight()`. Je tedy závislý na skutečném `STYLIST_ACCEPT_FS_RISK`, `CODEX_MODEL` a nainstalovaném Codex CLI; v čistém CI selže ještě před spy factory. Mockujte `_polish_preflight` na úspěšný návrat, stejně jako v následujícím redaction testu.

## IMPORTANT

- Task 2, Step 1: Chybí negativní testy pro nesprávně umístěný/duplicitní `===KONEC===` a pro text po něm. Bez nich lze implementovat deklarovanou ochranu jen jako současné nedostatečné `MARK_END in raw`.

## VERDICT
CHANGES_NEEDED