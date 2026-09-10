# Round 18 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem grep sweepnul zbylé `shutil.copy2`
výskyty (Codex potřetí v řadě citoval konkrétní řádky jako stale) -
potřetí jsem nenašel žádný neoprávněný current-tense výskyt. Beru tohle
jako ustálený vzorec - Codexovo číslování řádků se zjevně odvozuje od
verze dokumentu před mými vlastními opravami v témže kole, ne po nich.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `Counter` oprava je fakticky neúčinná:** MIMOŘÁDNĚ
  přesný bod - ověřil jsem si přímo `src/concordance.py` řádek po řádku:
  `leak` vrací nejvýš JEDEN nález na term_id (`leaked[0]`), `inconsistency`
  filtruje přes vlastní `reported` množinu, `omission` Mention se
  přidává jen `if not mentions` (nejvýš jednou). Scénář "1× → 2×", co
  motivoval kolo-16 `Counter` fix, je touhle cestou NEDOSAŽITELNÝ -
  `check_chapter()` sama garantuje unikátnost. Vráceno na jednodušší
  množinové srovnání + integrační test s REÁLNÝM `check_chapter()`
  místo hand-built duplicitních findings.
- **IMPORTANT - test dlouhého vstupu koliduje s kolo-17 size guardem:**
  ověřil jsem přímo - `long_cz` je přes 100 000 znaků, nad `STYLIST_
  MAX_CHARS=60000`, test by spadl na guardu dřív, než by otestoval stdin
  mechanismus. `monkeypatch` limit nahoru pro tenhle test.
- **IMPORTANT - regresní test na `pages=100` nerozliší opravu od
  chyby:** ověřil jsem si přesně - `timeout=0` vede k `TimeoutError` u
  OBOU variant (`pages=-1` i `pages=100`), jen v jiný moment. Přepsáno
  na přímé ověření argumentu přes spy na `sqlite3.Connection.backup`.
- **IMPORTANT - bezpečnostní hranice čtení mimo `-C` zůstává
  neověřená:** MÍSTO dalšího dohadování jsem to OVĚŘIL ŽIVĚ - spustil
  jsem `codex exec --sandbox read-only -C <izolovaný adresář>` s
  promptem žádajícím přečíst soubor MIMO `-C`. Codex ho ÚSPĚŠNĚ přečetl
  a vrátil přesný obsah (`Get-Content` na cestě mimo pracovní adresář,
  93ms, žádné odmítnutí). `read-only` tedy DEFINITIVNĚ omezuje jen
  ZÁPISY, ne ČTENÍ - riziko prompt injection z textu knihy je teď
  POTVRZENÉ, ne teoretické. Přijal jsem ČÁSTEČNĚ jinak, než Codex navrhl
  (plná OS/kontejnerová sandboxizace nebo neagentní API) - to je podle
  mě disproporční infrastrukturní rozhodnutí mimo rozsah týhle spec
  (stejná logika jako kolo-16 rozhodnutí o obnově DB), patří uživateli.
  Místo toho: zdokumentovaný OVĚŘENÝ nález (ne domnělý), povinný canary
  test v "Manuální ověření", explicitní bullet v "Mimo rozsah" s
  odůvodněním.
- **NIT - próza o EN-vs-stylizovaném srovnání čísel:** ověřeno, opraveno
  na "PŮVODNÍ CZ vs. stylizovaný CZ".
- **NIT - rozsah "Bezpečnostní detaily (kola 1-6)":** ověřeno, rozšířeno.

## Claude VERDICT

Po aplikaci 4 IMPORTANT (1 s reverzí vlastní kolo-16 pozice po přímém
ověření concordance.py, 1 s live-testem místo dalšího dohadování) + 2
NITS z kola 18 nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 18: Codex našel 4 IMPORTANT (0 BLOCKING, páté kolo v řadě) + 2
NITS. Dva mimořádně hodnotné nálezy: (1) kolo-16 `Counter` fix řešil
scénář, co je díky dedup logice v `concordance.py` STRUKTURÁLNĚ
nedosažitelný - vráceno na jednodušší množinové srovnání s integračním
testem; (2) bezpečnostní otázka "čte read-only sandbox mimo -C?" byla
5 kol nevyřešená prózou o nejistotě - VYŘEŠENA živým testem přímo v
téhle relaci (ANO, čte) - riziko prompt injection z textu knihy
exfiltrující citlivá data je teď POTVRZENÉ, zdokumentované, s povinným
canary testem, plná izolace vědomě mimo rozsah (infrastrukturní
rozhodnutí pro uživatele). Dál opraveny dva testy, co by po kole 17
tiše přestaly testovat to, co měly. Design je teď kompletní, 0 BLOCKING
pět kol v řadě - čeká se na kolo 19 Codexu.
