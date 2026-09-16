## IMPORTANT

- Task 5, `_cmd_run` `except FatalRunError as e`: Podmínka `args.translator == "codex"` nerozlišuje původ chyby. V režimu Codex ale kritik stále volá Claude; `FatalRunError` z Claude cost guardu či `LockLostError` proto nově označí kapitolu `flagged` a rediguje ji jako Codex chybu. To odporuje deklaraci, že Claude chování zůstává beze změny. Oprava: zaveď specifickou podtřídu pro fatální chyby Codex translatoru a flaguj pouze ji; obecný `FatalRunError` ponech původnímu chování.

- Task 2, `_marker_line_positions()`: Regex `^{marker}$` nepřijme CRLF řádky, protože před `$` zůstává `\r`. Parser je nově backend-agnostický, ale validní Claude odpověď s CRLF bude odmítnuta jako poškozená. Oprava: normalizovat `\r\n`/`\r` na `\n` před validací nebo použít kotvu tolerující `\r?`; přidej regresní test CRLF.

- Task 3, testy `StylistTimeoutError`: Testy pouze mockují `_exec_codex`, aby už vyhodil novou podtřídu. Neověřují, že skutečná větev `subprocess.TimeoutExpired` v `_exec_codex()` ji opravdu vytváří. Oprava: uprav existující timeout test ve `tests/test_stylist.py`, aby explicitně očekával `StylistTimeoutError`.

## NITS

- Task 2, `_parse()`: „PŘESNĚ tento tvar“ nekontroluje žádný obsah před `===PREKLAD===`; preambule se tiše zahodí. Buď ji zakaž a otestuj, nebo text plánu zmírni.

## VERDICT

CHANGES_NEEDED