# Round 14 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem dohledal DALŠÍ 3 skryté výskyty stale
"multiset" terminologie (kolo 13 přejmenování na sekvenci nepokrylo
`polish()`'s vlastní docstring, "tři vrstvy" architektonický přehled a
poznámku u `_NUMBER_RE` o ztrátě "%") a jeden CELÝ odstavec v
"Rozhodnutí" (kolo 4-6 historie), co pořád tvrdil, že se desetinný
oddělovač normalizuje - to už kolo 14 samo zrušilo v témže běhu, takže
bych to jinak zanechal stale hned po vlastní opravě.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `shutil.copy2` není spolehlivý snapshot SQLite:** ověřil
  jsem si přímo v `src/state.py` - `connect()` nenastavuje žádný
  `journal_mode` (jen `foreign_keys = ON`), takže WAL/SHM riziko je v
  TÉHLE konkrétní kódové bázi teoretické, ne aktuální. Ověřil jsem si
  taky existující `_MUTATING`/`state.run_lock` mechanismus v `main.py` -
  `polish` už je (podle týhle spec) v `_MUTATING`, takže souběžný cizí
  zápis je z velké části vyloučený i bez týhle opravy. I tak jde o
  levné, principiální vylepšení (SQLite vlastní API pro přesně tenhle
  účel, ne o moc složitější než `shutil.copy2`) - přidána `_snapshot_db`
  (`Connection.backup()` + `PRAGMA integrity_check`), `import shutil` v
  `main.py` runtime kódu odpadl (nahrazen `import sqlite3`).
- **IMPORTANT - obecné infrastrukturní výjimky mimo `_polish_one_
  chapter` zůstávají nezachycené:** ostrý bod - přímo jsem si ověřil
  precedens v EXISTUJÍCÍM `_cmd_run` (`main.py:232`) a zjistil, že MÁ
  IDENTICKOU mezeru (taky jen `FatalRunError`/`KeyboardInterrupt` na
  top-level, taky nechráněný `finally: state.finish_run`). Rozhodl jsem
  se OPRAVIT `_cmd_polish` (rozšířit top-level `try` na CELÝ příkaz,
  přidat `except Exception` catch-all), ale VĚDOMĚ NEDOTKNOUT `_cmd_run`
  (mimo rozsah týhle spec, `_cmd_run` tímhle plánem jinak není měněný) -
  zdokumentováno explicitně v novém Rozhodnutí bullet, aby nesoulad mezi
  sourozeneckými příkazy nezůstal tichý.
- **IMPORTANT - normalizace `.`/`,` může skrýt významovou změnu
  (Python 3.5):** REVERZUJI vlastní kolo-13 pozici - Codexův konkrétní
  protipříklad ("Python 3.5" jako verzové číslo/identifikátor, ne
  desetinná hodnota) je kvalitativně jiný argument, než jaký jsem v
  kole 13 vyvracel (tam šlo o tisíce-vs-desetiny ambiguitu, tohle je
  číslo-vs-identifikátor ambiguita) - a je přesvědčivý. Normalizace
  ZRUŠENA (ne zúžena - kontextová disambiguace by vyžadovala přesně tu
  "drahou NLP úlohu", co je jinde v dokumentu záměrně mimo rozsah).
  Test invertován, "Rozhodnutí" próza z kola 6/13 opravena.
- **NIT - stale "multiset" próza:** ověřeno a opraveno na 3 dalších
  místech (nad rámec Codexem citovaných řádků - grep sweep našel víc).
- **NIT - "finish_run se zavolá vždy":** ověřeno - kolo 13 sám zavedl
  podmínku (`rid is not None`) i best-effort chování, próza ale pořád
  tvrdila bezpodmínečné "vždy". Opraveno.
- **NIT - rozpor "vytvoří zálohu" vs. "NEvytvoří při samých
  unchanged/rejected/failed" v témže bullet:** ověřeno, opraveno
  podmínění první věty.

## Claude VERDICT

Po aplikaci 3 IMPORTANT (1 s reverzí vlastní kolo-13 pozice po novém,
kvalitativně jiném argumentu) + 3 NITS z kola 14 (vlastní sweep našel
další 3+1 skrytých výskytů nad rámec Codexem citovaných) nenacházím nic
dalšího.

`CONSENSUS`

## Summary for log

Kolo 14: Codex našel 3 IMPORTANT (0 BLOCKING - první kolo bez BLOCKING od
kola 11) + 3 NITS. Nejzávažnější zvraty: (1) `shutil.copy2` nahrazen
SQLite vlastním `Connection.backup()` + integrity_check - `import
shutil` v `main.py` odpadl; (2) top-level `try/except` v `_cmd_polish`
rozšířen na CELÝ příkaz (dřív chráněný jen `_snapshot_db`), s explicitní
poznámkou, že `_cmd_run` má IDENTICKOU mezeru, ale je mimo rozsah týhle
spec; (3) REVERZOVÁNA vlastní kolo-13 pozice - normalizace desetinného
oddělovače ZRUŠENA po konkrétním "Python 3.5" protipříkladu (číslo vs.
identifikátor, ne tisíce vs. desetiny - kvalitativně jiný argument než
ten, co jsem v kole 13 odmítl). Design je teď kompletní, 0 BLOCKING od
kola 11, klesající IMPORTANT trend (5→4→4→3→3) - čeká se na kolo 15
Codexu.
