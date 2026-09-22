# Round 8 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT

- **Spec's `ClaudeCliClient` skeleton a `_client_factory` ukázka
  chybí `claude_cmd` parametr:** Po Codexově nálezu (timeout
  nesoulad) jsem preventivně prošel CELÝ spec proti plánu (viz
  Summary) a našel DALŠÍ, dosud nezachycený nesoulad - specovo
  `__init__(self, model: str, timeout=None)` a `_client_factory`
  ukázka `ClaudeCliClient(config.MODEL_CRITIC)` neodpovídají plánovu
  kolo-3 fixu (`claude_cmd` jako PRVNÍ pozicní argument, provlečené z
  preflightu, ne bare `"claude"` znovu-resolvnuté uvnitř klienta).

  **Oprava:** spec's `ClaudeCliClient.__init__` skeleton doplněn o
  `claude_cmd: list[str]`. `_client_factory` ukázka rozšířena o
  celou funkci (ne jen vnitřní `factory()`) s `claude_cmd` parametrem
  a komentářem vysvětlujícím PROČ (preflightem resolvnutá binárka, ne
  bare string).

## On Codex's points

### Agreed + fixed

- **IMPORTANT (spec vs. plán - timeout mechanismus a fatálnost):**
  Souhlasím, ověřeno přímo ve specu - "Subprocess volání" sekce
  pořád ukazovala `subprocess.run(..., timeout=timeout, ...)`, zatímco
  implementační plán (`_exec_claude()`) správně používá
  `Popen(...).communicate(input=user, timeout=timeout)` +
  `_kill_process_tree()` na timeout/přerušení (Windows proces-strom
  killing, reuse ze `stylist.py`). Navíc spec's "Chybové stavy" sekce
  řadila `subprocess.TimeoutExpired` mezi FATÁLNÍ `ClaudeCliFatalError`
  důvody, zatímco plán ho drží SAMOSTATNĚ jako nefatální
  `ClaudeCliTimeoutError` (`_run_critic()`'s `except Exception:
  pseudo-finding` větev ho zachytí jako transientní chybu, ne jako
  run-zastavující auth/fatal chybu) - druhý, dosud nezachycený
  nesoulad spec/plán ve STEJNÉ sekci.

  **Oprava:** spec's "Subprocess volání" sekce aktualizována na
  `Popen`+`communicate`+kill-process-tree vzor. "Chybové stavy" sekce
  opravena - `TimeoutExpired` odstraněn ze seznamu fatálních důvodů,
  přidán nový odstavec vysvětlující SAMOSTATNOU nefatální
  `ClaudeCliTimeoutError` cestu.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 8: Codexův jeden IMPORTANT (spec/plán nesoulad - timeout
mechanismus a fatálnost `TimeoutExpired`) potvrzen a opraven. Po
tomhle nálezu jsem preventivně prošel CELÝ spec proti CELÉMU plánu
(místo čekání na Codexovo postupné odhalování - kolo 7 i kolo 8 obě
našla RŮZNÉ spec/plán nesoulady ve STEJNÉ třídě problému) a našel
DALŠÍ nesoulad sám (`ClaudeCliClient.__init__`/`_client_factory`
skeleton chybí `claude_cmd`, kolo-3 fix). Opraveno oboje. Plán samotný
beze změny oba nálezy - pouze spec dohnán na aktuální stav plánu.
