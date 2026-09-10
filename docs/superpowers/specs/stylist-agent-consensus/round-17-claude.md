# Round 17 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem grep sweepnul zbylé `shutil.copy2`
výskyty (Codex opět citoval konkrétní řádky jako stale) - stejně jako v
kolech 15-16 jsem nenašel žádný neoprávněný current-tense výskyt.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `-C` izoluje jen pracovní adresář, ne uživatelův globální
  Codex config:** MIMOŘÁDNĚ ostrý bod - ověřil jsem si přímo `codex exec
  --help` a `--ignore-user-config` SKUTEČNĚ existuje ("Do not load
  $CODEX_HOME/config.toml; auth still uses CODEX_HOME"). Tohle přímo
  vysvětluje VŠECHNY hangy, co jsem během tohohle plan-consensus procesu
  zažil (context7 MCP, magic MCP - obojí v uživatelově globálním
  configu, ne v `-C` izolovaném adresáři) - a znamená, že BEZ týhle
  vlajky by `polish` v PRODUKCI zdědilo STEJNÉ riziko při každém
  spuštění. Přidáno do argv, testu i manuálního checklistu. Druhou
  polovinu bodu (jestli `read-only` omezuje i ČTENÍ, ne jen zápisy) jsem
  NEOVĚŘIL s jistotou přes `--help` - zdokumentováno jako otevřená
  otázka, ne tiše přehlédnuto ani falešně vyřešeno.
- **IMPORTANT - kolo-16 "mazání sidecarů AŽ PO os.replace" má vlastní
  crash okno:** souhlasím, že jde o zbývající riziko - přidal jsem
  zdokumentovanou poznámku (SQLite hot-journal validace by měla
  chránit, ale NEOVĚŘENO s jistotou v týhle relaci) a praktický, levný
  krok navíc (druhý `integrity_check` po celém postupu), bez rozšiřování
  na plnou automatizaci (viz kolo-16 rozhodnutí o proporcionalitě, co
  zůstává v platnosti).
- **IMPORTANT - žádný size guard/konfigurovatelný timeout pro dlouhé
  kapitoly:** přijato jako levná, proporční oprava - `config.STYLIST_
  TIMEOUT_SECONDS`/`STYLIST_MAX_CHARS` přidány, `STYLIST_MAX_CHARS`
  explicitně zdokumentován jako HRUBÁ pojistka (ne přesný odhad
  tokenového limitu neznámého modelu). Nemění rozhodnutí "žádné dělení
  kapitoly" - jen rychlé odmítnutí místo čekání na jistý timeout.
- **NIT - próza "guide_block dostávají translator/kritik" je fakticky
  nepravdivá:** ověřil jsem přímo v REÁLNÉM `src/pipeline.py` -
  `_run_critic(en, cz, client)` volá `critic.review(en, cz, client)` BEZ
  `guide_block`, ten dostává jen `translate_scene`/`revise_chapter`
  (translator). Opraveno na 3 místech - navíc potvrzuje (nevyvrací) můj
  vlastní kolo-6 argument, že kritik nemá signál na registr.
- **NIT - chybová tabulka neúplná:** doplněny 2 chybějící řádky (číselný
  guard, size guard) a upřesněn řádek o multiplicitě (kolo 16).

## Claude VERDICT

Po aplikaci 3 IMPORTANT + 3 NITS z kola 17 nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 17: Codex našel 3 IMPORTANT (0 BLOCKING, čtvrté kolo v řadě) + 3
NITS. NEJDŮLEŽITĚJŠÍ nález celého procesu: `--ignore-user-config` -
přímo vysvětluje VŠECHNY hangy tohohle plan-consensus procesu (context7/
magic MCP v uživatelově globálním configu) a bez něj by `polish` v
produkci zdědilo stejné riziko. Přidáno do produkčního kódu, ne jen do
mého review procesu. Dál: zdokumentované zbývající riziko u obnovy ze
zálohy (crash okno po os.replace, SQLite validace neověřena s jistotou)
+ druhý integrity_check jako levná obrana; konfigurovatelný timeout +
size guard pro extrémně dlouhé kapitoly; oprava fakticky nepravdivé
prózy o tom, kdo dostává guide_block (NE kritik, ověřeno přímo v
src/pipeline.py). Design je teď kompletní, 0 BLOCKING čtyři kola v řadě
- čeká se na kolo 18 Codexu (tentokrát s --ignore-user-config i pro
vlastní review volání, mělo by to konečně přestat viset).
