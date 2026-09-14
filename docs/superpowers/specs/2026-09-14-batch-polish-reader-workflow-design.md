# Dávkový polish + čtenářský review workflow - design

## Kontext a cíl

`docs/superpowers/specs/2026-09-11-polish-review-design.md` (implementováno,
nasazeno) zavedlo tříkrokový workflow: `polish` (dávka → čeká na review) →
`polish-review` (web UI, kapitolu po kapitole schválíš/upravíš/zahodíš) →
commit do DB. Reálné použití (2026-09-13/14, ruční review kapitol 1-3)
ukázalo, že tenhle model neškáluje na ~50 kapitol knihy: čekat s otevřeným
prohlížečem na review KAŽDÉ kapitoly hned po jejím zpracování je
neúnosné.

Nový cíl: `polish` proběhne přes CELOU knihu bez zastavování a výsledek
se **rovnou stane finálním textem** (žádné čekající rozhodnutí). Uživatel
pak knihu přečte celou najednou (mimo tenhle nástroj), s seznamem nálezů
po ruce. Kde se mu obrat nelíbí (ať proto, že to našel kritik, nebo proto,
že to sám při čtení zaškrtlo), otevře konkrétní kapitolu v UI, upraví a
uloží - tahle úprava se PROMÍTNE rovnou do finálního textu.

Tenhle dokument **navazuje** na `2026-09-11-polish-review-design.md` a MĚNÍ
jeho centrální mechanismus (draft fronta čekající na schválení). Zámkový/
CAS/atomický-zápis aparát zavedený tam (`state.acquire_lock`/`refresh_lock`,
`threading.Lock` serializace requestů v rámci serveru, CAS kontrola PŘED
zápisem, tmp+`os.replace` atomické zápisy JSON) zůstává **beze změny** a
tenhle dokument ho dál používá - přepisuje se jen to, ODKUD editor bere
text k úpravě a KDY se výsledek `polish`e zapisuje do knihy.

## Mimo rozsah

- **Souběžné/paralelní zpracování víc knih v jednom běžícím serveru** -
  uživatel potvrdil, že knihy dělá POSTUPNĚ, ne paralelně. Řeší se jen
  levná příprava (parametrizace cesty, viz níž), ne "vyber knihu" UI.
- **Živý dashboard průběhu běhu** (vizuální přehled "co se teď děje" během
  `run`/`polish`) - odloženo na samostatný budoucí design, potvrzeno
  uživatelem ("určitě nejdřív dodeláme batch polish").
- **Automatický přepočet nálezů po ruční úpravě** - zvažováno a zamítnuto
  ve prospěch ručního zaškrtávání (viz sekce Nálezy níž) - je to
  spolehlivější (kritikovo hodnocení smyslu nejde levně/deterministicky
  ověřit) a jednodušší.
- **Živé napojení review UI na hlavní `run` frontu** - `run` (hlavní
  překlad) se tímhle dokumentem nemění vůbec, jen `polish` a review UI.
- Cokoli z `2026-09-11-polish-review-design.md`, co se tímhle dokumentem
  výslovně nemění (zámky, CAS princip, atomické zápisy, `_MUTATING`
  zapojení) - platí dál beze změny, není tu znovu vypisováno.

## Architektura - shrnutí toku

```
python main.py polish [--only IDX...] [--force]
    → pro každou `done` kapitolu: Codex + concordance + kritik + strukturální
      kontrola (BEZE ZMĚNY - `_polish_one_chapter` dál volá stejné funkce)
    → VÝSLEDEK SE ROVNOU ZAPÍŠE do `chapters.translated_text` + záznam
      do `polish.history.json` (source="polish-batch")
    → `polish.draft.json` a review-fronta jako koncept KONČÍ (viz níž)

python main.py polish-review
    → nová hlavní stránka: seznam VŠECH kapitol (status, počet nevyřešených
      nálezů, kdy naposled upravena) + tlačítko Export knihy + odkaz na
      Report nálezů
    → "Editovat" u kapitoly: otevře editor NAD AKTUÁLNÍM textem té kapitoly
      (ne nad draftem - draft jako čekající objekt neexistuje)
    → v editoru: "Znovu polish" (Codex znovu, výsledek jde do
      editovatelného pole, NEukládá se automaticky - ty rozhodneš a uložíš)
    → uložení PŘEPÍŠE `translated_text` + zapíše do historie (stejný
      apply mechanismus jako dnes, jen bez `polish.draft.json` zdroje)
```

## Nálezy: stabilní `id` + `resolved` flag

Dnešní nálezy (dicty z `concordance.check_chapter`, `pipeline._run_critic`,
`stylist.structural_findings`) nemají žádnou trvalou identitu - nejde
jednoznačně říct "tenhle konkrétní nález uživatel vyřešil", protože se
re-generují od nuly při každém `run`/`polish` běhu.

**Změna:** těsně předtím, než se seznam nálezů zapisuje do trvalého úložiště
(`chapters.notes` po `run`u, `polish.history.json` po `polish`u), projdi
seznam a KAŽDÉMU nálezu bez `id` přiřaď `id: uuid.uuid4().hex` a
`resolved: false`. Jeden úzký bod změny (těsně před zápisem), ne zásah do
každé nález-produkující funkce zvlášť.

**Nový endpoint** `POST /api/findings/resolve` - payload
`{scope: "notes"|"history", idx: int, finding_id: str, resolved: bool}`.
Pod stejným `write_lock`/`require_lock()` vzorem jako apply/revert (viz
`2026-09-11` spec). `scope="notes"` přepíše odpovídající nález v
`chapters.notes` (read-modify-write JSON sloupce, bez dotčení zbytku
řádku). `scope="history"` najde POSLEDNÍ historický záznam pro `idx`
(stejná definice "poslední" jako v `2026-09-11` spec - poslední prvek
pole, ne podle času) a přepíše nález tam. Nenalezený `finding_id` → 404.

**Proč ne automatický přepočet:** zvažováno (concordance/strukturální
nálezy by šly přepočítat levně, deterministicky), ale kritik kontroluje
VÝZNAM, ne text - levný přepočet by u kritikových nálezů buď lhal
("vyřešeno", i když není), nebo by vyžadoval drahé nové LLM volání při
KAŽDÉ ruční úpravě. Ruční zaškrtnutí je jednodušší, spolehlivější (člověk
ověřuje, ne heuristika) a funguje stejně pro všechny typy nálezů.

**Co se zobrazuje kde:** editor kapitoly ukazuje nálezy TÉ kapitoly
(nejnovější historický záznam + `chapters.notes`) s checkboxy. Report
nálezů (viz níž) ukazuje totéž napříč všemi kapitolami, s počtem
nevyřešených jako souhrn.

## `_polish_one_chapter` a `_cmd_polish` (přestavba)

`_polish_one_chapter` (výpočet: Codex, concordance, strukturální kontrola,
kritik, `check_meaning_preserved`) se NEMĚNÍ. Mění se, co se s výsledkem
DĚLÁ:

- `outcome in ("unchanged", "failed")` - beze změny, žádný zápis, jen
  metrika do `polish-reports/*.json`.
- Jinak (Codex navrhl jinou stylizaci) - `_cmd_polish` teď PŘÍMO zavolá
  stejnou commit logiku, co dnes dělá `POST /api/polish/apply`
  (`state.commit_chapter_result` + zápis do `polish.history.json`,
  `source="polish-batch"`), místo aby vracel draft dict k ručnímu
  schválení. Nálezy (concordance + strukturální + kritik +
  případně meaning-check) se zapisují do historie STEJNĚ jako dnes do
  draftu, akorát rovnou i do DB `chapters.notes` (přes
  `commit_chapter_result`'s `notes_json`).

`polish.draft.json` a preflight "nevyřízený draft = odmítni běh" MIZÍ.
`--force` sémantika (přepiš i kapitoly, co polish už prošly) zůstává.

**Chybová hláška z `_cmd_polish` per kapitola** se přepisuje z "návrh
připraven, půjde k review" na "kapitola N: stylizováno, zapsáno
(M nálezů)" - odpovídá novému rovnou-zapiš chování.

## Editor bez živého draftu

Dnešní editor (`polish.html`) čte `ch.styled`/`ch.cz_before` z živého
draft objektu. Přestavuje se na:

- **Zdroj textu:** `translated_text` AKTUÁLNÍ (dnešní) kapitoly z DB -
  to, co je v editovatelném poli NÁVRH při otevření.
- **"Vrať na originál"** - najde NEJSTARŠÍ historický záznam pro `idx`
  (první `polish` běh, kdy se kapitola poprvé změnila) a jeho
  `cz_before` (= stav před JAKÝMKOLI polishem). Chybí-li historie úplně
  (kapitola nikdy neprošla polishem), tlačítko se skryje.
- **"Vrať na Codex"** - najde POSLEDNÍ historický záznam pro `idx`, jeho
  `styled_by_codex`. Stejně skryté, když historie neexistuje.
- **Uložení** - STEJNÝ apply mechanismus jako dnes (CAS kontrola proti
  aktuální DB, `commit_chapter_result`, nový záznam do historie,
  `source="polish-review"`). Findings u téhle nové historie položky =
  cokoli editor v tu chvíli zobrazoval (nálezy z posledního `polish`u
  nebo ze "Znovu polish" volání, viz níž) - ŽÁDNÝ přepočet (viz sekce
  Nálezy výš).

## "Znovu polish" tlačítko

Nový endpoint `POST /api/polish/regenerate` - `{idx: int}`. Zavolá
`_polish_one_chapter` PRO JEDNU kapitolu (stejná logika jako dávka), ale
**nic nezapisuje** - vrátí `{styled, findings, reason_types}` přímo v
odpovědi. Frontend jen naplní editovatelné pole (`textarea.value =
result.styled`, stejně jako dnešní `btnCodex` handler) a zobrazí nové
nálezy vedle pole. Bezstavové - žádná perzistence na serveru mezi
voláním a uložením; prohlížeč drží stav v textovém poli, dokud
neklikneš Uložit. Odejdeš-li ze stránky bez uložení, výsledek se ztratí -
stejné chování jako dnešní tlačítko "Vrať na Codex", žádná změna.

## Nová hlavní stránka: seznam kapitol

`GET /` (nahrazuje dnešní "fronta čekajících draftů"). Řádek na kapitolu:
`idx`, `title`, `status` (barevně/značkou jako `_MARKERS` v `main.py`),
počet nevyřešených nálezů (`resolved: false` napříč notes + poslední
historií), `updated_at` (existující sloupec `chapters.updated_at`).
Tlačítko **Editovat** vede na editor (viz výš). Nahoře tlačítko
**Export knihy** a odkaz **Report nálezů**.

## Export knihy (tlačítko)

`_cmd_export` (dnešní CLI příkaz) se rozdělí: čistá funkce
`export_book(db_path, only_done: bool) -> tuple[str, list[int]]` (cesta k
výslednému souboru + seznam vynechaných kapitol), volaná jak z `_cmd_
export`, tak z nového `POST /api/export` endpointu (`polish-review`
server). Endpoint pod stejným zámkovým vzorem (čtení, ne zápis do DB -
stačí `require_lock()` kontrola, ne plný `write_lock`). Odpověď: cesta k
souboru + počet vynechaných kapitol, ukáže se v UI.

## Report nálezů

Nová funkce `build_findings_report(db_path, history_path) -> list[dict]`
- pro každou kapitolu spojí `chapters.notes` (nálezy z `run`) + nálezy
POSLEDNÍHO historického záznamu pro `idx` (nálezy z `polish`u, pokud
proběhl), seřadí podle `idx`. Dva výstupy ze STEJNÉ funkce:

- **`GET /findings`** - HTML stránka v `polish-review` UI, čitelná k
  vytištění (žádné interaktivní ovládací prvky navíc, jen kapitola →
  nález → status vyřešeno/nevyřešeno).
- **txt soubor** vedle `output/kniha_cz.txt` (např. `output/kniha_cz.
  findings.txt`), zapsaný při kliknutí na Export knihy (bod výš) NEBO
  samostatným tlačítkem na `/findings` stránce.

Zahrnuje VŠECHNY nálezy bez ohledu na závažnost (potvrzeno uživatelem -
"dej vše", s tím, že se to případně po vyzkoušení na pár kapitolách
zúží).

## Levná příprava na další knihy

`config.py`: nová `PROJECT_DIR = os.environ.get("BOOK_TRANSLATOR_PROJECT_
DIR", ".")`. `DATA_DIR`/`OUTPUT_DIR` se odvozují jako `os.path.join(
PROJECT_DIR, "data")`/`os.path.join(PROJECT_DIR, "output")` místo
natvrdo `"data"`/`"output"`. Žádná další změna - přechod na jinou knihu
= spustit CLI/server s jinak nastavenou proměnnou prostředí (nebo z
jiného pracovního adresáře). `.env` loading (`_load_dotenv`) zůstává
beze změny, hledá se vedle `config.py` jako dnes.

## Testování

- Finding id/resolved: přiřazení při prvním zápisu, idempotence (nález s
  existujícím `id` se nepřepíše).
- `/api/findings/resolve`: obě `scope` varianty, nenalezený `finding_id`,
  zámkové/CAS chování stejné jako existující apply/revert testy.
- `_cmd_polish` nová cesta: kapitola s rozdílem se rovnou zapíše do DB +
  historie, žádný `polish.draft.json` nevzniká.
- Editor bez draftu: `GET` kapitoly bez historie (tlačítka skrytá), s
  historií (baseline tlačítka fungují), uložení přepíše DB + přidá
  historii.
- `/api/polish/regenerate`: nic nezapisuje do DB/historie, vrací
  `styled`+`findings`.
- `export_book`: stejné chování jako dnešní `_cmd_export` testy, jen
  přes novou signaturu; `/api/export` endpoint volá stejnou funkci.
- `build_findings_report`: sloučení `chapters.notes` + poslední historie,
  řazení podle `idx`, prázdný případ (žádné nálezy).
- `config.py` parametrizace: `BOOK_TRANSLATOR_PROJECT_DIR` nastavená vs.
  chybějící (default `.`).

## Otevřené otázky

- Report nálezů zahrnuje VŠE (žádný filtr závažnosti) - po vyzkoušení na
  prvních ~5 kapitolách dávky se může ukázat, že je to moc šumu; ponecháno
  jako budoucí úprava (filtr podle `severity`), ne teď.
- `polish.draft.json` soubor samotný (starý mechanismus) - tenhle
  dokument ho přestává používat, ale nemaže existující kód okolo něj
  (`polish_store.load_draft`/`save_draft`) automaticky; smazání
  mrtvého kódu je součástí implementace, ne samostatné rozhodnutí.
