# Round 3 — Claude critique

## Claude's own findings
### BLOCKING
(žádné vlastní nové nad rámec Codexova bodu)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **BLOCKING (`_client_factory` mění jen `agent=="critic"` -
  `stylist_check` STÁLE vyžaduje `AnthropicClient`/`ANTHROPIC_API_KEY`,
  eager preflight tomu nezabrání):** Souhlasím a ověřil jsem přímo -
  `_polish_one_chapter()` (`main.py:698`) volá NAVÍC `cf("stylist_
  check")` (`stylist.check_meaning_preserved()`) - TŘETÍ agent typ,
  co jsem přehlédl. `_client_factory`'s `else: inner = AnthropicClient()`
  větev ho chytá stejně jako dřív - MIMO rozsah tohohle plánu (brainstorming
  session explicitně řekla "Jen kritik"). Problém není v tom, že
  `stylist_check` zůstává na API (to je ZÁMĚR) - problém je, že MÉ
  VLASTNÍ kolo-2 preflight kontroly (`_cmd_polish`/regenerate) tenhle
  fakt SKRÝVALY - vypadalo by to, jako by eager kontrola řešila CELÉ
  riziko "draze zaplacená Codex stylizace, pak selhání", ale řešila jen
  POLOVINU (claude CLI stranu, ne API klíč stranu).

  **Oprava:** Global Constraints teď explicitně dokumentuje `stylist_
  check` jako MIMO rozsah. `_cmd_polish`/`polish_server.py`'s regenerate
  dostaly DRUHOU eager kontrolu (`if not config.ANTHROPIC_API_KEY`) HNED
  za `_claude_cli_preflight()`, stejný důvod - `run` (translator+kritik)
  už API klíč nepotřebuje vůbec, `polish` (translator/kritik + navíc
  `stylist_check`) klíč STÁLE potřebuje. Task 4's manuální ověření
  rozšířeno o SAMOSTATNÝ krok pro `polish` (s klíčem nastaveným),
  ověřující OBA backendy ve STEJNÉM běhu.

- **IMPORTANT (preflight resolvne `claude_cmd`, ale všechna tři volání
  ho zahodí a `factory()` znovu použije holé `["claude"]`):** Souhlasím
  - `_claude_cli_preflight()` resolvne ABSOLUTNÍ cestu A ověří
  přihlášení PRO TENHLE konkrétní binární soubor, ale `_client_factory`'s
  `elif agent == "critic": inner = ClaudeCliClient(["claude"], ...)`
  tuhle hodnotu IGNOROVALO a nechalo `ClaudeCliClient` resolvnout
  ZNOVU, líně, uvnitř `_exec_claude()` - TOCTOU mezera (PATH se
  teoreticky může změnit mezi preflightem a prvním skutečným voláním)
  a zbytečná duplicitní práce.

  **Oprava:** `_client_factory()` dostal nový volitelný `claude_cmd`
  parametr (default `None` → fallback `["claude"]`, beze změny chování
  pro volající bez eager preflightu). `_cmd_run`/`_cmd_polish`/
  polish-server teď PŘEDÁVAJÍ svůj preflightem resolvnutý `claude_cmd`
  do `_client_factory(...)`. Přidán test ověřující threadování.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 3: jeden BLOCKING (`stylist_check`, třetí agent typ, zůstává MIMO
rozsah plánu, ale moje kolo-2 preflight kontroly vytvářely mylný dojem
úplné ochrany - doplněna samostatná eager `ANTHROPIC_API_KEY` kontrola
+ explicitní dokumentace rozsahu) + jeden IMPORTANT (preflightem
resolvnutý `claude_cmd` se zahazoval, `_client_factory` resolvoval
znovu - threadováno přes nový volitelný parametr). Třetí kolo v řadě s
reálnými nálezy, klesající závažnost (kolo 1: architektonický BLOCKING,
kolo 2: aritmetická chyba + opakovaný vzor, kolo 3: rozsahová mezera +
TOCTOU nit) - plán se blíží stabilitě.
