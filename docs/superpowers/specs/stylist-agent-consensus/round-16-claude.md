# Round 16 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem grep sweepnul zbylé `shutil.copy2`
výskyty (Codex znovu citoval konkrétní řádky jako stale) - stejně jako v
kole 15 jsem nenašel žádný neoprávněný current-tense výskyt; všechny
jsou buď legitimní restore recept, historicky rámované, nebo moje vlastní
nové texty.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - deadline v `_snapshot_db` je neúčinný:** ostrý, přesný
  bod - ověřil jsem si přímo Python `sqlite3` dokumentaci: `backup()`'s
  výchozí `pages=-1` zkopíruje CELOU DB v JEDNOM kroku, takže `progress`
  callback (a tedy kolo-15 deadline) by se zavolal nejvýš jednou, AŽ PO
  dokončení - byl by čistě kosmetický, ne skutečný časový limit. Přidán
  `pages=100`, aby `backup()` udělalo víc kroků a `progress` měl reálnou
  šanci zasáhnout uprostřed. Přidán regresní test (velká DB + `timeout=0`
  → `TimeoutError`, ne tiché dokončení).
- **IMPORTANT - množinové srovnání v `_polish_rejected` ignoruje
  multiplicitu:** ostrý bod - ověřil jsem přímo kód: `k not in
  baseline_keys` je `False` pro klíč, co v baseline BYL, bez ohledu na
  to, KOLIKRÁT se teď objevuje PO stylizaci. Stylista, co zopakuje
  identický pre-existující problém na DALŠÍM místě, by tak prošel jako
  "nic nového". Přepsáno na `Counter`-based srovnání POČTŮ výskytů.
- **IMPORTANT - mazání `-wal`/`-shm` PŘED `os.replace` otvírá okno pro
  poškození AKTUÁLNÍ DB:** souhlasím s pořadím (mazání AŽ PO úspěšném
  `os.replace`) a s přidáním `-journal` (rollback-mode sidecar, co tenhle
  projekt SKUTEČNĚ používá, na rozdíl od teoretického WAL). NESOUHLASÍM
  s plným rozsahem návrhu ("testovaná, zamykaná příkazová obálka") -
  obnova zůstává dokumentovaný ruční postup pro disaster recovery
  (`main.py` musí být zastavený jako explicitní precondice), plná
  automatizace by byla nová netriviální schopnost (vlastní příkaz,
  vlastní testy, vlastní zamykání), disproporční rozsah pro spec o
  stylistickém průchodu. Přidán explicitní bullet do "Mimo rozsah".
- **NIT - `_paragraph_count` nezachytí CRLF/whitespace-only prázdné
  řádky:** přijato jako levná, bezrizikova oprava - i když jsem si
  ověřil, že v TÉHLE konkrétní cestě (`open(out_path, "r", encoding=
  "utf-8")` bez `newline=""` dělá univerzální normalizaci konců řádků
  při čtení) je riziko spíš teoretické, ne aktuální. Normalizace +
  regex split na prázdný řádek s bílými znaky.

### Disagreed (částečně)
- **IMPORTANT - obnova ze zálohy jako plně automatizovaná/testovaná
  příkazová obálka:** viz výš - přijal jsem ORDERING/journal část,
  odmítl jsem plnou automatizaci s odůvodněním proporcionality rozsahu.

## Claude VERDICT

Po aplikaci 3 IMPORTANT (1 částečně - přijato jádro, odmítnut rozsah) +
1 NIT z kola 16 nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 16: Codex našel 3 IMPORTANT (0 BLOCKING, třetí kolo v řadě) + 2
NITS. Nejzávažnější: deadline v `_snapshot_db` byl fakticky nefunkční
(výchozí `pages=-1` znemožňoval `progress` callbacku zasáhnout
uprostřed) - opraveno `pages=100`. `_polish_rejected`'s množinové
srovnání ignorovalo multiplicitu (opakovaný pre-existující problém by
prošel jako "nic nového") - přepsáno na `Counter`. Obnova ze zálohy:
pořadí mazání sidecarů opraveno (AŽ PO `os.replace`, ne před ním) a
přidán `-journal`, ale ODMÍTNUTA plná automatizace (testovaná/zamykaná
příkazová obálka) jako disproporční rozsah - zůstává dokumentovaný ruční
postup, nový bullet v "Mimo rozsah" to zdůvodňuje. Design je teď
kompletní, 0 BLOCKING tři kola v řadě - čeká se na kolo 17 Codexu.
