# Round 13 — Claude critique

## Claude's own findings

Při implementaci Codexova bodu #2 (CLI `require_lock`) jsem sám našel a
opravil DALŠÍ, nezávislý problém nad rámec Codexova textu: `_polish_env`
testovací fixtura (`tests/test_cli.py`) mockuje `main._client_factory`
CELÝ, se signaturou `lambda rid, *, interactive: ...` - bez `require_
lock` kwarg. Přidání `require_lock=` do REÁLNÉHO volání v `_cmd_polish`
by bez opravy fixtury rozbilo KAŽDÝ existující test používající `_polish_
env` (`TypeError: unexpected keyword argument`). Opraveno v Task 5 Step 9
(mock teď přijímá a zahazuje `require_lock=None`). Zároveň jsem zjistil,
že tahle fixtura `_client_factory` ÚPLNĚ mockuje (žádný reálný
`PipelineLLMClient` nevzniká) - test na "ztráta zámku BĚHEM LLM volání →
FatalRunError" by přes ni nikdy nic neotestoval; přepsáno na dva menší,
přesnější testy (přímý test `_lock_still_owned`, samostatný drátovací
test).

## On Codex's points

### Agreed + fixed
- **IMPORTANT #1 - `require_lock()` v Task 10 regenerate NENÍ
  bezprostředně před `create_run()` (`glossary.all_terms()` mezi nimi).**
  Souhlas - přesunuto `glossary.all_terms()` PŘED kontrolu, kontrola je
  teď POSLEDNÍ věc před `create_run`. Nový test ověřuje 503 + žádný
  `runs` řádek při `require_lock()==False`.
- **IMPORTANT #2 - kolo-11 zdůvodnění "CLI nepotřebuje require_lock,
  drží zámek celou dobu" bylo nedostatečné - `_cmd_polish`'s `refresh_
  lock` běží až TĚSNĚ před commitem, ne před LLM voláními uvnitř
  `_polish_one_chapter`.** Souhlas, potvrzeno čtením main.py:1169-1176 -
  `cf = _client_factory(...)` a `_polish_one_chapter` volání (kritik/
  stylist_check) proběhnou PŘED jakýmkoli `refresh_lock` v týhle
  iteraci. Přidána modulová `_lock_still_owned(lock_path)` funkce
  (main.py, AKTIVNĚ obnovuje zámek, ne jen kontroluje - CLI na rozdíl
  od serveru nemá heartbeat vlákno), `_cmd_polish`'s `cf = _client_
  factory(...)` teď předává `require_lock=lambda: _lock_still_owned(
  config.LOCK_PATH)`. Stejná ochrana jako u serveru (Task 10), teď
  konzistentně na OBOU cestách, co `PipelineLLMClient` používají.

## Claude VERDICT

CHANGES_NEEDED (souhlas s oběma IMPORTANT body, plná implementace)

## Summary for log

Kolo 13 - stejná třída problému (lock-check timing) pokračuje do
ČTVRTÉHO po sobě jdoucího kola (10→11→12→13), teď dokončuje pokrytí i
pro CLI cestu `_cmd_polish`, kterou kolo 11 mylně považovalo za
bezpečnou beze změny. Server (Task 10) i CLI (Task 5) teď mají
SYMETRICKOU ochranu přes `PipelineLLMClient`'s `require_lock`. Vlastní
nález (fixture signature mismatch) ukazuje hodnotu psaní SKUTEČNÉHO
kódu při editaci plánu, ne jen popisu - následky změny signatury na
existující testy nejsou vždy zjevné z textu samotného.
