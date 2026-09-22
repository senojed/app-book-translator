# Round 2 — Claude critique

## Claude's own findings
### BLOCKING
(žádné vlastní nové nad rámec Codexova bodu)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **BLOCKING (`count_tokens` test očekává `4`, implementace `//4`
  vrátí `2`):** Souhlasím - vlastní aritmetická chyba, zkopíroval jsem
  komentář z `CodexLLMClient`'s testu (co používá `//2`) bez přepočtu
  hodnoty pro `ClaudeCliClient`'s odlišný `//4` poměr.

  **Oprava:** Opraven test na `== 2`, implementace `//4` zůstává
  (konzistentní s `FakeLLMClient`'s stejným poměrem).

- **IMPORTANT (`_claude_cli_preflight()` jen v `_cmd_run`, chybí v
  `polish`/polish-server):** Souhlasím a ověřil jsem přímo - `_run_
  critic()` (a tedy `ClaudeCliClient`) se volá i z `_polish_one_chapter`
  (`_cmd_polish`'s dávka, `critic.review()`'s vlastní docstring "kolo
  15 NIT" to potvrzuje) A z `polish_server.py`'s regenerate endpointu
  (`main._client_factory(rid, ...)`, řádek ~379). Obojí provede DRAHÉ
  Codex stylizační volání PŘED kritikem - stejné riziko jako `_cmd_run`.

  **Oprava:** `_claude_cli_preflight()` teď volaná i v `_cmd_polish`
  (main.py) a `polish_server.py`'s regenerate handleru, hned za jejich
  existující `_polish_preflight()` kontrolou. Files/Interfaces v Task 3
  rozšířené o `src/review_ui/polish_server.py`/`tests/test_polish_
  server.py`.

- **IMPORTANT (`_claude_cli_preflight()`'s `json.loads` nevaliduje
  dict, ignoruje `returncode`):** Souhlasím - STEJNÁ třída chyby, co
  jsem OPRAVIL minulé kolo v `_exec_claude()`, ale zopakoval jsem ji v
  NOVÉ funkci, co jsem napsal TENTO kolo. `status.get(...)` na `[]`/
  `null`/string by spadlo na neklasifikovaný `AttributeError` mimo
  zdokumentovaný `(None, chyba)` kontrakt; nekontrolovaný `returncode`
  by nechal `json.loads` selhat matoucím způsobem na prázdném/
  nesmyslném stdoutu.

  **Oprava:** `_claude_cli_preflight()` teď kontroluje `result.
  returncode != 0` PŘED parsováním JSON, a `isinstance(status, dict)`
  PŘED `.get("loggedIn")`. Přidány 4 testy (nonzero exit, non-dict
  JSON, malformed JSON, not-logged-in).

- **IMPORTANT (`_exec_claude()`'s usage validace jen `isinstance(dict)`,
  ne číselnost polí):** Souhlasím - `input_tokens`/`output_tokens`
  mohou být string/bool/float/záporné číslo, `PipelineLLMClient.
  complete()`'s `finally` blok s nimi počítá aritmeticky (`it / 1e6 *
  in_rate`) - string by tam spadl na `TypeError` UVNITŘ `finally`
  (maskuje původní výjimku), `bool` by prošel tiše (Python `bool` je
  `int` podtřída), záporné číslo by zapsalo nesmyslný audit řádek.

  **Oprava:** `_exec_claude()` validuje `input_tokens`/`output_tokens`
  jako nezáporná celá čísla (explicitně vylučuje `bool`, i když je to
  technicky `int` podtřída). Přidán test se 4 neplatnými tvary (string,
  záporné, bool, float).

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 2: jeden BLOCKING (triviální aritmetická chyba v testu) + tři
IMPORTANT, VŠECHNY tři nálezy druhého typu jsou variace na STEJNÝ vzor
("validuj typ/tvar dat, co přicházejí zvenčí, ne jen přítomnost") -
dvakrát jsem tenhle vzor už OPRAVIL kolo 1 (payload dict/is_error/
subtype/result-str), ale zapomněl ho aplikovat na DALŠÍ dvě místa
(nová `_claude_cli_preflight()` funkce, usage polí číselnost) a na
DALŠÍ dva volající (`polish`/polish-server, ne jen `run`). Opraveno
všude. Druhé kolo v řadě s reálnými nálezy - žádný spor, jen nedůslednost
v aplikaci vlastních opravených vzorů.
