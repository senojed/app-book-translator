# Round 5 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`--help`'s vlastní `returncode` se nekontroluje):**
  Souhlasím - stejná mezera, co jsem opravil pro `auth status` kolo 2,
  zopakoval jsem ji v NOVÉM `--help` volání kolo 4. Neúspěšné `--help`
  s náhodou obsaženými flagovými substringy ve zbytkovém/částečném
  stdoutu by prošlo jako "úspěch".

  **Oprava:** `if help_result.returncode != 0: return None, ...` PŘED
  substring kontrolou. Přidán test.

- **IMPORTANT (`not status.get("loggedIn")` přijme truthy string
  `"false"`):** Souhlasím - `"loggedIn": "false"` (STRING, ne bool) je
  v Pythonu TRUTHY (`not "false"` je `False`) - `_claude_cli_preflight()`
  by tohle chybně přijalo jako přihlášené, obcházející celou eager
  ochranu.

  **Oprava:** `status.get("loggedIn") is not True` - striktní bool
  kontrola. Přidán test s `"loggedIn": "false"` (string).

- **IMPORTANT (existující fake/spy `_client_factory` náhrady ve 4
  testech nemají `claude_cmd`, nová keyword je rozbije `TypeError`):**
  Souhlasím a ověřil jsem přímo proti REÁLNÝM testovacím souborům (ne
  jen plánu) - `tests/test_cli.py:1048,1709,1728` a `tests/test_polish_
  server.py:914` - VŠECHNY čtyři definují `_fake_client_factory`/
  `spy_factory` BEZ `claude_cmd` parametru. Moje kolo-3 oprava
  (threadování `claude_cmd` do `_client_factory(...)` volání v
  `_cmd_run`/`_cmd_polish`/regenerate) by je VŠECHNY rozbila.

  **Oprava:** Explicitní seznam všech čtyř míst s přesnou opravou
  (přidat `claude_cmd=None` do signatury, u `spy_factory` navíc
  přeposlat do `real_factory(...)`). Přidán SAMOSTATNÝ nový end-to-end
  test (`test_run_threads_preflight_resolved_claude_cmd_into_client_
  factory`), co ověřuje SKUTEČNÉ předání hodnoty přes `_cmd_run`, ne
  jen že `_client_factory` umí parametr přijmout.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 5: tři IMPORTANT, dva jsou OPAKOVÁNÍ stejného vzoru (returncode/
striktní typová kontrola) na NOVĚ přidaném kódu z minulých kol - stejná
třída nedůslednosti jako kolo 2. Třetí je reálná regrese - moje kolo-3
threadování `claude_cmd` by rozbilo čtyři EXISTUJÍCÍ testy z JINÉ,
dřívější plánu (codex-translator-backend), ne z tohohle plánu - Codex
ho našel jen proto, že skutečně přečetl reálné testovací soubory, ne
jen tenhle plán. Opraveno vše, plán teď explicitně vyjmenovává VŠECHNA
místa, co potřebují úpravu mimo vlastní nové soubory.
