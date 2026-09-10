# Round 12 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem si všiml, že `docstring` u
`_polish_one_chapter` ("Výjimky NEchytá") potřeboval doplnit o novou
výjimku (`FatalRunError` ze zálohy/DB zápisu) - opraveno, aby próza
odpovídala novému kódu hned, ne až v příštím kole.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - záloha/DB zápis se počítá jako per-kapitolová chyba:**
  ostrý, přesný bod - ověřil jsem přímo, že vnější `except Exception` v
  `_cmd_polish`'s smyčce obaluje CELÉ volání `_polish_one_chapter`,
  včetně `_backup_db_once`/`state.commit_chapter_result` uvnitř. Selhání
  zápisu (plný disk, poškozená DB) by tak dopadlo jako obyčejné
  `outcome="failed"` JEDNÉ kapitoly - a pokud by jiná kapitola v dávce
  skončila "unchanged"/"rejected" (ne "failed"), `status="fatal"`
  podmínka (`counts["failed"] == len(chapters)`) by NEsepnula, run by
  skončil `"ok"` navzdory rozbité DB. Opraveno - `_backup_db_once` +
  `commit_chapter_result` zabaleny do vlastního `try/except`, co
  JAKOUKOLI výjimku převede na `FatalRunError` (ten vnější smyčka
  nechytá per-kapitolově, `except FatalRunError: raise` stojí nad
  `except Exception`).
- **IMPORTANT - chybí regresní testy pro selhání zálohy/zápisu a pro
  procentní opravy:** přidáno 5 nových scénářů - selhání samotného
  `shutil.copy2` při snapshotu, selhání `os.replace`/`commit_chapter_
  result` UPROSTŘED smíšené dávky (ověřuje, že fronta se dál nezpracuje a
  předchozí zapsané kapitoly zůstávají), a ekvivalence/rozlišení čtyř
  mezerových variant čísla+procenta.
- **IMPORTANT - "Rozhodnutí" próza pořád popisuje starý přímý/líný
  copy2 mechanismus:** souhlasím ČÁSTEČNĚ jinak, než navrhoval Codex
  (přepsat bully) - rozhodl jsem se PONECHAT historický popis (je to
  chronologický log rozhodnutí, ne aktuální dokumentace mechanismu) ale
  přidat explicitní POZNÁMKU přímo na obě místa, že mechanismus je od
  kola 9 nahrazený - stejný vzorec, jaký dokument už používá u
  kolo-4-čísel bullet ("ODSTRANĚNO jako protimluv"). Tohle přímo řeší
  Codexovu specifickou námitku ("pozdější bullet ten rozpor
  neodstraňuje") bez přepisování historie.
- **NIT - `_fake_codex`'s `write_text` bez `encoding="utf-8"`:** ověřil
  jsem - `body!r` může nést český text, `repr()` ho vloží do zdrojáku
  doslovně (ne uniklý), `write_text` bez encoding na Windows sáhne po
  cp1252, co českou diakritiku (č/ě/ř/š/ž/ů) neumí - STEJNÁ třída chyby,
  jakou produkční `Popen` řešil v kole 5 BLOCKING. Opraveno + pro
  konzistenci i druhý podobný `write_text` (argv test), i když ten má
  jen ASCII obsah (defenzivní, ne oprava aktuálně spustitelného bugu).

### Disagreed
- **NIT - próza "žádný soubor s textem knihy" odporuje `-o out.txt`
  (řádky 666-673):** udělal jsem přímé ověření DRUHÉ kolo za sebou (viz
  i kolo 10) - živý text na aktuálním místě (bezpečnostní detail 1 v
  `stylist.py` docstringu) MÁ explicitní caveat "pozor - STYLIZOVANÁ
  verze se stejně zapíše přes `-o`". Jediný výskyt bez tohohle caveatu je
  Rozhodnutí bullet, co sám sebe popisuje jako JIŽ OPRAVENOU nadsázku z
  kola 6. Nenašel jsem žádné aktuální místo, kde by tohle tvrzení bylo
  nesprávné - beru Codexovo číslo řádku jako odkaz na stav před nějakou
  dřívější opravou.

## Claude VERDICT

Po aplikaci 3 IMPORTANT + 1 NIT z kola 12 (1 NIT rozporován podruhé po
přímém ověření) nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 12: Codex našel 3 IMPORTANT (záloha/DB zápis se dřív počítala jako
per-kapitolová chyba, ne infrastrukturní - mohla vést k `status="ok"`
navzdory rozbité DB; chybí regresní testy pro selhání zápisu a procentní
opravy z kol 10-11; "Rozhodnutí" próza pořád primárně popisuje starý
backup mechanismus bez odkazu na kolo-9 náhradu) + 2 NITS (próza o
souboru s textem knihy - rozporováno podruhé, už opravené v kole 6;
`_fake_codex` bez explicitního UTF-8 encoding). Nejzávažnější oprava:
selhání zálohy/DB zápisu teď correctly propaguje jako `FatalRunError`
(zastaví celý běh), ne jako obyčejná per-kapitolová `failed` chyba, co
mohla maskovat rozbitou infrastrukturu za normální výsledek běhu. Design
je teď kompletní - čeká se na kolo 13 Codexu.
