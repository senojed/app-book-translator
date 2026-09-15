# Ruční review stylistického průchodu - design

> **Nahrazeno** `docs/superpowers/specs/2026-09-14-batch-polish-reader-workflow-design.md`
> (2026-09-14) - draft fronta popsaná tímhle dokumentem byla odstraněna,
> `polish` teď zapisuje rovnou. Zámkový/CAS/atomický-zápis aparát popsaný
> níž ZŮSTÁVÁ v platnosti beze změny, jen se přestal používat pro
> draft-specifické endpointy (`apply`/`discard`/draft preflight).

## Kontext a cíl

`polish` (viz `docs/superpowers/specs/2026-09-08-stylist-agent-design.md`,
CONSENSUS po 38 kolech, implementováno a nasazeno) dnes rozhoduje SÁM: podle
konkordance/kritika/kontroly významu kapitolu buď přijme (zapíše do DB), nebo
zamítne (zahodí Codexův výstup, ponechá originál). Reálný běh (2026-09-11,
Turn Coat kap. 1-2) ukázal: kritik se jako "revise" chová i u drobných,
diskutabilních přídavků (Codex přidal příjmení "Dresden", číslovku "Sedm" -
věcně nadbytečné, ale ne nutně nežádoucí). Automatické all-or-nothing
rozhodování tak zahazuje i stylizace, které by uživatel po přečtení klidně
chtěl - jen s drobnou ruční úpravou.

Cíl: **žádná kapitola se nezapíše do `chapters`/`term_mentions` (žádná
změna přeloženého textu) bez lidského schválení** (kolo 4 IMPORTANT -
zpřesnění: `runs`/`llm_calls` bookkeeping `create_run`/`record_llm_call`/
`finish_run` v DB zůstává beze změny, `polish` je pořád `interactive=True`
placené volání, jak popisuje sekce `_polish_one_chapter` níž - "žádný
zápis do DB" by bylo nepravdivé tvrzení). Uživatel
vidí text před/po a kritikovy nálezy, a text před uložením může sám ručně
upravit (ne jen "ano/ne" na celý Codexův výstup) - tím se obchází problém,
který originální spec řešil a odložil ("jak aplikovat rozhodnutí o jednom
nálezu, když Codex vrátí celý přepsaný odstavec, ne diff") - člověk je tím,
kdo "aplikuje" úpravu, rukou v textovém poli, ne kód.

Tenhle dokument **rozšiřuje** `polish`, nenahrazuje ho - `stylist.py`
(volání Codexu), `critic.py`, `concordance.py`, `_rejection_reasons`
(výpočet doporučení) zůstávají beze změny. Mění se jen to, co se s
výsledkem/doporučením DĚLÁ (dřív: auto-commit/auto-reject; teď: draft →
lidská revize → commit).

## Mimo rozsah

- Rozhodování po JEDNOTLIVÉM nálezu (checkbox u každého nálezu) - vědomě
  odmítnuto ve prospěch jednoho editovatelného textového pole na kapitolu
  (viz Kontext výš). Uživatel může nálezy číst a rozhodnout se sám, ale
  UI mu je neaplikuje.
- Souběžné review víc uživateli / na víc strojích najednou - jeden lokální
  proces jako `review` dnes.
- Automatizovaná/testovaná obnova CELÉ DB ze zálohy (stejné omezení jako
  originální `polish` spec) - zůstává ruční postup. Per-kapitolové "vrať
  zpět" (viz níže) je NOVÁ schopnost, co tohle NAHRAZUJE pro běžný případ
  (nechtěná JEDNA kapitola), ne pro katastrofickou obnovu celé DB.
- Editace TITULKU, přeuspořádání kapitol, cokoli mimo `translated_text` -
  review UI mění jen text jedné kapitoly.
- `STYLIST_REPORT_REJECTED_TEXT` gate a `polish-reports/*.json` soubor
  jako koncept (agregátní metrika, doplňkový nástroj vedle tohohle
  workflow) - zůstávají. Konkrétní `outcome` HODNOTY, co se do reportu
  zapisují, se MĚNÍ (viz `_cmd_polish` sekce níž) - stará "auto-přijato/
  auto-zamítnuto" dichotomie už neodpovídá novému workflow (nic se
  needitor-review automaticky nepřijímá ani nezamítá).

## Architektura

Tři kroky místo dnešního jednoho:

```
python main.py polish           # Codex + kontroly, ŽÁDNÝ zápis do `chapters`/
                                 # `term_mentions` (žádná změna přeloženého
                                 # textu - `runs`/`llm_calls` bookkeeping
                                 # beze změny, viz kolo 4 IMPORTANT níž)
                                 # -> data/polish.draft.json (čeká na rozhodnutí)
python main.py polish-review    # web UI: text před/po (editovatelné), nálezy
                                 # -> uložením per-kapitolově zapíše do DB
                                 # -> data/polish.history.json (archiv rozhodnutí)
                                 # (revert jedné kapitoly taky odsud)
```

`_cmd_polish`/`_polish_one_chapter` (existující, `main.py`) se refaktorují:
stejné volání Codexu + guardrailů, ale MÍSTO commitu/zahození vrátí "draft"
záznam. Nová funkce (voláno z `polish-review` apply endpointu) dělá to, co
dřív dělala přijímací větev `_polish_one_chapter` - zálohu + commit.

### `data/polish.draft.json`

Vzniká/přepisuje se během `polish`. Obsahuje JEN kapitoly, co čekají na
rozhodnutí (Codex vrátil jiný text než originál A prošel strukturální
kontrolou v `stylist.polish()` - kapitoly `unchanged`/`failed` sem NEJDOU,
není co rozhodovat, jde jen o `polish-reports/*.json` metriku jako dnes).

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-11T22:00:00+02:00",
  "codex_model": "gpt-5.6-terra",
  "chapters": [
    {
      "idx": 1,
      "title": "Chapter 1",
      "cz_before": "...",
      "styled": "...",
      "revision_rounds": 0,
      "reason_types": ["critic/fidelity"],
      "findings": [ /* co `_polish_one_chapter` SKUTEČNĚ spočítala - viz
                       níž, NENÍ vždy concordance+critic+meaning-check */ ],
      "rendered_terms": [ /* translatorem hlášené formy, viz kolo 18 -
                              NEMĚNNÁ hodnota, přenáší se dál beze změny */ ]
    }
  ]
}
```

**`findings` NENÍ vždy "plné"** (kolo 1 IMPORTANT - oprava dřívějšího
tvrzení, co si odporovalo se stávajícím kódem): `_polish_one_chapter` volá
`check_meaning_preserved` (meaning-check) JEN když `reasons` po
concordance+kritikovi vyjde prázdné (existující short-circuit kvůli ceně
LLM volání, `main.py` beze změny). `findings` v draftu je tedy PŘESNĚ to,
co tahle funkce fakticky spočítala - concordance VŽDY, kritik VŽDY,
meaning-check JEN když concordance+kritik samy o sobě zamítnutí
nezaručily. Draft záznam nenese informaci "meaning-check se nespustil" -
to je vlastnost už stávajícího `_rejection_reasons` chování, tenhle
dokument ji jen zdědí, nemění.

**Preflight `polish`:** pokud `data/polish.draft.json` existuje a NENÍ
prázdný (= obsahuje aspoň jednu kapitolu v `chapters`), `_cmd_polish`
odmítne běžet ("N kapitol čeká na review, spusť `python main.py
polish-review` nejdřív") - žádné tiché přepsání/sloučení nevyřízené dávky.

**Zápis je INKREMENTÁLNÍ, ne až na konci dávky** (kolo 1 IMPORTANT - pád
uprostřed dlouhé dávky by jinak zahodil všechny už zaplacené Codex
návrhy): po KAŽDÉ kapitole, co skončí jako draft záznam, `_cmd_polish`
přepíše CELÝ `polish.draft.json` (existující záznamy z týhle dávky +
nový) atomicky (tmp soubor ve stejném adresáři + `os.replace` - stejný
princip jako `_snapshot_db`/`_backup_db_once` u DB). Cena je zanedbatelná
(soubor s pár desítkami kapitol, ne gigabajty) proti riziku ztráty
placené práce.

**Zápis JSON obecně** (draft i historie): vždy tmp+`os.replace` ve
stejném adresáři, nikdy přímý `open(path, "w")` na finální cestu (stejné
riziko částečného zápisu jako u DB zálohy). Při čtení: neplatný JSON,
neznámý/chybějící `schema_version`, nebo `chapters`/`entries` špatného
typu → jasná chyba se zastavením (ne tichý pád na prázdný stav, co by
potichu zahodil existující draft/historii).

**Validace NA ÚROVNI JEDNOTLIVÝCH záznamů, ne jen obálky** (kolo 3
IMPORTANT - dřív specifikován jen typ `chapters`/`entries` jako celku,
ne obsah jednotlivých položek; poškozený/cizí/ručně upravený jeden
záznam by jinak spadl jako `KeyError`/500 hluboko v `GET`/`apply`/
`revert`, ne jako čitelná chyba hned při startu). Povinná pole a typy:

Draftová OBÁLKA (`polish.draft.json` kořen, kolo 4 IMPORTANT - dřív
validován jen typ `chapters`, ne hlavičková pole): `schema_version`
(`int`), `generated_at` (`str`), `codex_model` (`str`, NEPRÁZDNÝ - apply
endpoint ho používá jako `model` argument pro `_stylist_marker`, prázdná/
chybějící hodnota by vyrobila nesmyslný marker "stylizováno přes Codex
(model=)"). Stejná politika jako u záznamů níž - chybí/špatný typ →
celý soubor neplatný.

Draft záznam (`polish.draft.json` → `chapters[]`): `idx` (`int`),
`title` (`str`), `cz_before` (`str`), `styled` (`str`),
`revision_rounds` (`int`), `reason_types` (`list[str]`), `findings`
(`list[dict]`), `rendered_terms` (`list[dict]`, kolo 18 - translatorem
hlášené formy termínů, `_polish_one_chapter`'s existující lokální
výpočet, teď navíc uložený do draftu).

Historický záznam (`polish.history.json` → `entries[]`): `idx` (`int`),
`applied_at` (`str`, ISO 8601), `cz_before` (`str`), `cz_after` (`str`),
`styled_by_codex` (`str`), `title` (`str`), `findings` (`list[dict]`),
`rendered_terms` (`list[dict]`, kolo 18 - PŘEVZATÉ z draftu/
předchozího historického záznamu, NIKDY přepočítané znovu z živé DB,
viz zdůvodnění u `apply`/`revert` níž), `source` (`str`, JEN
`"polish-review"` nebo `"revert"`).

Chybějící pole, špatný typ, nebo neplatná hodnota `source` → celý
soubor se považuje za neplatný (stejná politika jako neplatná obálka
výš) - server se nespustí / endpoint vrátí chybu, NEpokračuje s
částečně přečteným/odhadnutým obsahem.

**Unikátnost `idx` v draftu** (kolo 6 IMPORTANT - dřív nevalidováno):
`polish.draft.json` → `chapters[]` nesmí mít dva záznamy se stejným
`idx` - ručně poškozený/upravený soubor s duplicitou by udělal apply/
discard nejednoznačným (kterou položku myslel?). Validace při čtení to
odmítne stejnou politikou jako výš (celý soubor neplatný).

**"Poslední záznam pro `idx`" se určuje POŘADÍM V POLI, ne časem**
(kolo 6 IMPORTANT, zpřesnění kola 5 - dřív "poslední" znamenalo
"nejnovější `applied_at`", ale zápisy do historie jsou VŽDY sekvenční
(jeden proces, `threading.Lock` z kola 2 serializuje i souběžné HTTP
požadavky, CAS navíc vylučuje souběžné operace nad stejnou `idx`) -
pole samo je tedy VŽDY v chronologickém pořadí zápisu, i kdyby dva
záznamy náhodou měly identický `applied_at` (hodinové rozlišení
systémových hodin na některých platformách, i mikrosekundová shoda
teoreticky možná). Přesná definice: "poslední záznam pro `idx`" =
POSLEDNÍ prvek pole `entries`, co má daný `idx` (iterace od konce),
NIKDY srovnání `applied_at`. `applied_at`/parsovaný čas (kolo 5 UTC
fix) se používá JEN pro ZOBRAZENÍ/řazení v `GET /api/polish` (globální
"posledních N", "co se nedávno dělo") - ne pro určení, co je "poslední"
pro revert/CAS účely.

**Selhání zápisu draftu je infrastrukturní, ne per-kapitolová chyba**
(kolo 3 IMPORTANT - dřív nespecifikováno): stejný princip jako dnešní
záloha/DB commit v `_polish_one_chapter` (plný disk, práva - to samé
riziko, co může postihnout DB zálohu, může postihnout i draft.json).
Selže-li atomický zápis `polish.draft.json` po úspěšném (a zaplaceném)
Codex volání pro danou kapitolu, `_cmd_polish` to zabalí jako
`FatalRunError` a CELÝ běh `polish` se zastaví (STEJNÝ vzor jako
existující zabalení kolem `_backup_db_once`/`commit_chapter_result` -
viz `main.py` `_polish_one_chapter`) - ne per-kapitolové `"failed"` a
tiché pokračování na další kapitolu, co by dál pálilo Codex volání bez
šance výsledek uložit.

### `data/polish.history.json`

Append-only archiv rozhodnutých kapitol, KDE zápis do historie proběhl
úspěšně (od tohohle workflow dál - historii nemá zpětně, jen co vznikne
od teď). Slouží jako podklad pro per-kapitolové "vrať zpět", NE jako
duplicitní DB ani jako neomylný audit log "úplně všeho" - DB je vždy
zdroj pravdy o tom, CO je v knize (kolo 3 IMPORTANT, oprava dřívějšího
"VŠECH" - viz "Zbytkové riziko" v sekci `polish-review` níž, kde je
popsáno PŘESNĚ za jakých okolností záznam v historii chybí, i když DB
zápis proběhl).

```json
{
  "schema_version": 1,
  "entries": [
    {
      "idx": 1,
      "applied_at": "2026-09-11T22:05:00+02:00",
      "cz_before": "...",
      "cz_after": "...",
      "styled_by_codex": "...",
      "title": "Chapter 1",
      "findings": [ /* nálezy platné v době rozhodnutí */ ],
      "rendered_terms": [ /* převzaté z draftu, viz kolo 18 */ ],
      "source": "polish-review"
    }
  ]
}
```

`source` je řetězcový enum se dvěma platnými hodnotami: `"polish-review"`
(vzniklo z `POST /api/polish/apply`) nebo `"revert"` (vzniklo z
`POST /api/polish/revert`) - žádná jiná hodnota není platná (kolo 1
IMPORTANT, opravuje zápis se svislítkem, co nebyl platný JSON, jen
neformální zkratka pro "jedno ze dvou").

`title` se ukládá do historie i přesto, že je odvoditelná z DB - je to
JEDINÝ způsob, jak `GET /api/polish` sekci "Historie" zobrazí čitelný
název kapitoly bez dalšího dotazu do DB pro smazané/přejmenované
záznamy (kolo 1 NIT).

**Posledních N záznamů** (`GET /api/polish` pro sekci "Historie"):
N=20, řazeno podle `applied_at` sestupně (nejnovější první), NEfiltrováno
podle `idx` - jde o globální "co se nedávno dělo", ne per-kapitolový
výpis (kolo 1 NIT, dřív nespecifikováno).

**`applied_at` VŽDY jako UTC, "poslední"/řazení podle PARSOVANÉHO
času** (kolo 5 IMPORTANT - dřív nespecifikováno, riziko chyby): ISO
8601 řetězce s RŮZNÝM offsetem (např. při přechodu na letní/zimní čas)
NEJSOU navzájem lexikograficky řaditelné podle času, jaký ve skutečnosti
označují - řazení podle syrového řetězce by dalo špatné pořadí přesně
kolem přechodu, a "poslední záznam pro `idx`" (apply/revert CAS i
revert samotný na tom staví) by mohlo vybrat ŠPATNÝ záznam. Fix:
`applied_at` (i `generated_at` v draftu) se VŽDY zapisuje jako UTC s
explicitním `Z` sufixem (`datetime.now(datetime.timezone.utc)
.isoformat().replace("+00:00", "Z")`, NE lokální čas bez offsetu).
Validace při čtení (viz tabulka povinných polí výš) vyžaduje PŘESNĚ
tenhle tvar, ne jen "cokoli parsovatelné" (kolo 8 NIT - jinak je "vždy
UTC s `Z`" jen deklarace, ne vynucený kontrakt): řetězec musí KONČIT
`"Z"` A `datetime.fromisoformat(value[:-1] + "+00:00")` musí uspět -
hodnota s JINÝM offsetem (`+01:00` apod.), i kdyby byla jinak
parsovatelná, se odmítne stejně jako nevalidní JSON (celý soubor
neplatný). "Poslední záznam pro `idx`" i řazení v `GET /api/polish` se
počítá VŽDY nad naparsovaným `datetime` objektem, nikdy porovnáním
syrových řetězců.

**Revert:** review UI u archivovaných kapitol nabídne "vrať na verzi před
stylizací" - najde POSLEDNÍ (nejnovější) záznam pro dané `idx`, jeho
`cz_before` zapíše jako nový `translated_text`, a připojí NOVÝ záznam do
historie (`source: "revert"`, `cz_before` = to, co se právě vrátilo,
`cz_after` = obnovený text). Díky tomu je revert sám o sobě odvolatelný
(klikni "vrať zpět" znovu = vrátí revert). (Zpřesnění kolo 19-21 - viz
`revert` endpoint níž: existuje i varianta "vrať na PŮVODNÍ verzi"
celého souvislého řetězce stylizací, ne jen jeden krok zpět.)

## Data flow a klíčové funkce

### `_polish_one_chapter` (refaktor)

Beze změny: `stylist.polish()`, `styled == cz` krátký okruh (žádný draft
záznam, jen `unchanged` metrika), konkordance baseline+after, kritik,
`_rejection_reasons` (počítá se POŘÁD, jako DOPORUČENÍ - `reason_types`
+ `findings` jdou do draftu VŽDY, bez ohledu na to, jestli je prázdné nebo
ne). `FatalRunError` propaguje stejně jako dnes (kritik/meaning-check jsou
pořád reálná placená volání - `create_run`/`record_llm_call`/`finish_run`
beze změny, `polish` je pořád `interactive=True`).

Nové: funkce už NEVOLÁ `_backup_db_once`/`state.commit_chapter_result`.
Vrací draft dict (`idx`, `title`, `cz_before`, `styled`, `revision_rounds`,
`reason_types`, `findings`, `rendered_terms` - kolo 18, existující
lokální proměnná `rendered_terms`, co si funkce dnes už počítá PŘED
konkordancí/kritikem, se teď navíc PŘIDÁ do vraceného dict místo aby
zůstala jen lokální; `polish-review` ji později POUŽIJE místo
přepočtu z živé DB, viz zdůvodnění v sekci `polish-review` níž) nebo
`{"outcome": "unchanged"}` / `{"outcome": "failed", "error": ...}` (ty
dvě varianty stejné jako dnes, jen nejdou do `polish.draft.json`, jen do
`polish-reports/*.json`).

### `_cmd_polish` (refaktor)

Stejný preflight (FS-risk gate, model, `_resolve_codex_cmd`) + NOVÝ
preflight (nevyřízený draft = odmítni). Loop přes `chapters_by_status(db,
("done",))` (`--only`/`--force`... `--force` teď znamená "i kapitoly, co
mají v `notes` marker z dřívějšího PŘIJETÍ tímhle workflow" - stejná
sémantika jako dnes). Sbírá draft záznamy, na konci zapíše
`polish.draft.json` INKREMENTÁLNĚ (viz sekce `polish.draft.json` výš -
po každé kapitole, ne až na konci; "přeskočí zápis, když je prázdný"
teď znamená "soubor nikdy nevznikne, když dávka neproduková JEDINOU
draft kapitolu" - žádné "nic ke kontrole" soubory).

**`polish-reports/*.json` outcome přejmenování** (kolo 1 IMPORTANT):
`_REPORT_OUTCOMES` dnes = `("polished", "unchanged", "rejected",
"failed", "fatal", "interrupted")` - "polished"/"rejected" popisovaly
AUTOMATICKÉ rozhodnutí, které teď `_polish_one_chapter` nedělá (obojí
končí jako draft záznam čekající na člověka). Fix: `_REPORT_OUTCOMES`
nahrazuje `"polished"` a `"rejected"` JEDNÍM `"drafted"` (`_polish_
one_chapter` vrací draft dict pro OBA dřívější případy - `reason_types`
uvnitř draft záznamu zůstává rozlišovací informace, prázdné pro
"dřív by prošlo", neprázdné pro "dřív by bylo zamítnuto", jen se teď
NEPOUŽÍVÁ k rozhodnutí, jde do UI jako kontext). Report `summary`
dict tedy má klíče `("drafted", "unchanged", "failed", "fatal",
"interrupted")`. `_cmd_polish` finální hláška ("Vylepšeno: X, beze
změny: Y, zamítnuto kontrolou: Z, selhalo: W") se přepisuje na
"Navrženo k review: X, beze změny: Y, selhalo: Z" (žádné "vylepšeno"/
"zamítnuto" - o tom teď rozhoduje `polish-review`, ne tenhle příkaz).
Existující testy na `_write_polish_report`/`_cmd_polish` výstup z
`2026-09-08` specu se přepíší na nový tvar (stejná poznámka jako u
`_polish_one_chapter` v sekci Testování níž).

**Záloha DB** (`_snapshot_db`/`_backup_db_once`) se z `_cmd_polish`
ODSTRAŇUJE - `polish` už nezapisuje nic do `chapters`, není co zálohovat
kvůli tomuhle kroku. Přesouvá se do `polish-review` apply endpointu (viz
níž) - PŘESNĚ TAM, kde teď skutečný zápis vzniká.

**`init --reset` a draft/historie** (kolo 1 IMPORTANT - dřív
neřešeno): `init --reset` nahrazuje CELOU knihu, `idx` číslování začíná
znovu od 1 - starý `polish.draft.json` by pak ukazoval na kapitoly JINÉ
knihy pod stejnými čísly. Apply/revert samotné to nemůže poškodit (viz
CAS kontrola níž - `cz_before`/`cz_after` uloženého záznamu se prostě
nebude shodovat s obsahem nové knihy, zápis se odmítne), ale nechat
starý draft ležet by zbytečně matlo review UI cizí knihou. Proto
`_cmd_init` s `--reset` navíc PŘEJMENUJE (NEmaže NIC) OBA soubory, pokud
existují: `data/polish.draft.json` → `data/polish.draft.<UTC timestamp,
formát YYYYMMDDTHHMMSSffffffZ>.json` a `data/polish.history.json` →
`data/polish.history.<stejný formát>.json` - MIKROsekundová přesnost
(kolo 6 IMPORTANT, oprava - sekundová přesnost by u dvou resetů ve
STEJNÉ sekundě dala STEJNÝ název a starší archiv by se tiše přepsal).
Obojí přes `os.rename` (NE `os.replace`) - existující cíl (prakticky
nemožné i s mikrosekundovou přesností, ale ne nulová šance) → `init
--reset` skončí chybou PŘED jakýmkoli zásahem do DB.

**Draft se ARCHIVUJE, NE maže** (kolo 8 IMPORTANT, oprava - dřív draft
mazán, historie přejmenována; DVĚ různé operace s DVĚMA různými
selháními znamenaly, že selže-li přejmenování historie PO úspěšném
smazání draftu, placená/nenahraditelná Codex práce v draftu je
NENÁVRATNĚ pryč, i když DB zůstala nedotčená a `init --reset` šel jinak
bezpečně zopakovat). Starý draft je po přejmenování mimo
`polish.draft.json` (preflight ho nevidí, review UI ho nezobrazí), ale
zůstává na disku pro ruční nahlédnutí, stejně jako archivovaná historie.

**Obě přejmenování musí být dohromady VŠE NEBO NIC** (kolo 9 IMPORTANT -
oprava kola 8: "obojí je jen přejmenování, tak na pořadí nezáleží" byla
polopravda - i dvě NEdestruktivní operace mají mezistav. Uspěje-li
přejmenování draftu, ale SELŽE přejmenování historie, `init --reset`
sice skončí chybou PŘED `state.reset_book` (DB netknutá), ale
NEZKONTROLOVANÝ draft je teď mimo `polish.draft.json` - `polish-review`
ho nevidí, preflight `polish`u ho nevidí, vypadá to, jako by nic
nečekalo na review, i když čeká, jen pod jiným jménem. To je HORŠÍ než
prostá ztráta dat - uživatel ani neví, že má něco zkontrolovat).
Fix - pořadí + rollback, žádný nový mechanismus navíc, jen použití
STEJNÉHO `os.rename` primitiva obousměrně: (1) nejdřív přejmenuj
historii (pokud existuje) - selže-li, nic se nestalo, draft je pořád
na svém místě, `init --reset` prostě skončí chybou. (2) pak přejmenuj
draft (pokud existuje) - selže-li TOHLE, VRAŤ přejmenování historie
zpět (`os.rename` na původní jméno), teprve pak vrať chybu - výsledný
stav na disku je PŘESNĚ stejný, jako kdyby `init --reset` vůbec
neproběhl. (3) teprve po ÚSPĚCHU OBOU kroků pokračuje `state.reset_book`.

**Rollback musí pokrýt i selhání TŘETÍHO kroku** (kolo 10 IMPORTANT,
rozšíření kola 9 - "vše nebo nic" platilo jen pro DVĚ přejmenování,
ne pro celou sekvenci): selže-li `state.reset_book` PO úspěšném
přejmenování OBOU souborů (DB transakce se sama vrátí, `reset_book`
neprovede částečnou změnu - stará kniha v DB zůstává), review fronta
STÁLE patřící ke STÁLE aktivní staré knize by zmizela z aktivních cest
(`polish.draft.json`/`polish.history.json`), přestože kniha, ke které
patří, dál existuje. Fix: (4) selže-li krok (3), VRAŤ OBĚ přejmenování
zpět (draft i historii, stejným `os.rename` obousměrně jako v kroku
(2)), teprve pak vrať chybu - výsledný stav je znovu přesně takový,
jako by `init --reset` vůbec neproběhlo. Stejné zbytkové riziko jako u
kola 9 (SAMOTNÝ rollback by teoreticky mohl selhat - disk zmizel
uprostřed sekvence): `init --reset` v tom vzácném případě vypíše PŘESNÝ
stav všech tří položek (obě jména souborů na disku + stav DB), ať si to
uživatel může opravit ručně; plný dvoufázový commit protokol napříč
souborovým systémem a SQLite transakcí na tohle není úměrný.

**Pořadí: úklid PŘED `state.reset_book`** (kolo 2 IMPORTANT, oprava -
dřív navrženo obráceně): souborový úklid proběhne JAKO PRVNÍ krok
`_cmd_init --reset`, teprve PO jeho úspěchu se volá `state.reset_book`.
Selže-li úklid (práva, zamčený soubor), `init` skončí chybou a DB
zůstává NEDOTČENÁ - stará kniha dál existuje, uživatel může problém
opravit a zkusit znovu. Opačné pořadí (reset DB, pak úklid) by při
selhání úklidu nechalo NOVOU prázdnou/částečně naplněnou DB se STARÝM
draftem/historií - hůř rozpoznatelný a hůř opravitelný stav.

### `polish-review` (nový příkaz + `src/review_ui/polish_server.py`)

FastAPI + uvicorn, stejný vzor jako `src/review_ui/server.py` (`review`).
Na rozdíl od `review` (jedno uložení = konec) tenhle server běží, dokud ho
uživatel nezavře - může rozhodnout jen NĚKTERÉ kapitoly a zbytek nechat na
příště (zůstanou v `polish.draft.json`).

**`polish-review` patří do `_MUTATING`** (kolo 1 BLOCKING - dřív chybělo):
`main.py` dnes drží `state.run_lock` po CELOU dobu `args.func(args)` pro
každý příkaz v `_MUTATING` (`review` už tohle dělá stejně - lock držený
po celou dobu běžícího serveru, ne jen per-request). Bez zápisu do
`_MUTATING` by `polish-review` mohl běžet SOUČASNĚ s `run`/`answer`/
druhou instancí `review` a zapisovat do stejné DB bez zámku. Fix: přidat
`"polish-review"` do `_MUTATING` v `main.py`. Druhá instance (`polish` i
`polish-review`) při pokusu o souběžný běh dostane existující
`state.LockError` hlášku - žádné nové chování, jen správné zapojení do
stávajícího mechanismu.

**Zámek musí přežít dlouhé review sezení** (kolo 2 BLOCKING - dřív
přehlédnuto): `state._lock_is_live` (`src/state.py:275`) prohlásí zámek
za mrtvý, když je starší `_LOCK_STALE_SECONDS` (6 hodin) - BEZ OHLEDU na
to, jestli PID pořád žije. Tenhle mechanismus byl navržený pro dávkové
příkazy (`polish`, `run`), co běží nejvýš desítky minut; `polish-review`
je interaktivní server, co může zůstat otevřený přes celý pracovní den
(uživatel odejde, vrátí se). Bez fixu by po 6 hodinách JINÝ mutující
příkaz (nebo druhá `polish-review` instance) zámek smazal a rozjel se
SOUČASNĚ s pořád živým, pořád naslouchajícím serverem - přesně to, čemu
má `_MUTATING` zápis výš zabránit. Fix: `polish-review` server po
úspěšném `acquire_lock` spustí vlákno na pozadí (`threading.Timer`
řetězené, nebo `threading.Thread` s `while` smyčkou a `time.sleep`), co
každých `_LOCK_STALE_SECONDS // 2` (3 hodiny) PŘEPÍŠE `ts` pole v
zámkovém souboru na aktuální čas (stejný JSON tvar jako `acquire_lock` -
`{"pid": os.getpid(), "ts": <teď>.isoformat()}`), NE přes `acquire_lock`
(ten by na existující soubor spadl na `FileExistsError`). Vlákno se
ukončí (`daemon=True` postačí, žádné explicitní zastavení není potřeba)
spolu s procesem serveru. Vyžaduje malou novou funkci v `src/state.py`
(např. `refresh_lock(lock_path)`), co soubor jen přepíše - `main.py`
sám zámek nedrží jako proměnnou, kterou by šlo předat dál, takže
`polish-review` handler čte `config.LOCK_PATH` přímo, stejně jako
`main()` dnes.

**Refresh/release musí ověřit VLASTNICTVÍ zámku** (kolo 3 BLOCKING -
dřív přehlédnuto, doplňuje fix výš): scénář - stroj (notebook) usne na
DÉLE než 6 hodin s běžícím `polish-review`; refresh vlákno spí taky (OS
suspend zastaví i Python vlákna), takže se `ts` NEstihne obnovit PŘED
uspáním. Po probuzení je zámek podle timestampu "starý", takže by ho
JINÝ proces (uživatel si nevšimne, že stará karta pořád běží, spustí
`run`/druhou `polish-review`) mohl legitimně převzít (`acquire_lock`
zámek smaže a založí nový, viz `src/state.py:299-306`). Bez ověření
vlastnictví by pak PŮVODNÍ (probuzený) server svým dalším refresh tikem
PŘEPSAL cizí (nový, legitimní) zámek svým PID/časem, a při svém ukončení
`release_lock` by ho SMAZAL - přesně to dvojí zapisování, co má `_MUTATING`
zabránit, teď obcházené vlastním "obranným" mechanismem. Fix: `refresh_
lock(lock_path)` PŘED přepisem načte aktuální obsah zámku a porovná
`pid` s `os.getpid()` - neshoda (nebo zámek zmizel) → vyhodí
`state.LockError` (ztratili jsme vlastnictví), NEpřepisuje nic. Samotný
ZÁPIS je atomický tmp+`os.replace` (kolo 13 IMPORTANT - dřív neřečeno,
implikovalo obyčejné `open(lock_path, "w")`: krátké okno, kdy je soubor
prázdný/neúplný, by JINÝ proces mohl přečíst jako nevalidní JSON -
`_lock_is_live` to bere jako "zámek je mrtvý" a rovnou by ho převzal,
PŘESTOŽE originální server běží a zrovna zapisuje. Stejný princip jako
u draft/history JSON výš - "vždy tmp+`os.replace`, nikdy přímý zápis na
finální cestu" platí i pro zámkový soubor). Atomická záměna sama o
sobě stačí - úprava `acquire_lock`/`_lock_is_live` (mimo rozsah, viz
TOCTOU zdůvodnění výš) NENÍ potřeba, protože `os.replace` zaručuje, že
souběžný čtenář VŽDY vidí buď starý, nebo nový KOMPLETNÍ obsah, nikdy
částečný - cesta "nečitelný soubor → považuj za mrtvý" se tímhle
neaktivuje. Souběh background vlákna (kolo 2) a synchronního refreshu na
začátku requestu (kolo 7) navzájem NEVADÍ NA ÚROVNI OBSAHU - oba by
případně zapsali STEJNÝ fakt (naše vlastní PID, čerstvý čas), žádná
dodatečná serializace ROZHODOVACÍ logiky mezi nimi není potřeba. ALE
(kolo 16 BLOCKING - upřesnění, dřív chybělo): každé volání
`refresh_lock` MUSÍ použít VLASTNÍ, UNIKÁTNÍ dočasný soubor (např.
`tempfile.mkstemp` ve stejném adresáři, nebo `lock_path +
f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"`) -
NIKDY sdílenou pevnou cestu jako `lock_path + ".tmp"`. Sdílený tmp
soubor by totiž byl zranitelný přesně tou samou třídou chyby, co
atomický zápis měl vyřešit: dvě VLÁKNA (heartbeat + synchronní refresh
requestu) zapisující do TÉHOŽ tmp souboru souběžně by ho mohly
poškodit interleaved zápisy, a `os.replace` by pak publikoval
POŠKOZENÝ obsah na `lock_path` - jiný proces by ho přečetl jako
nevalidní JSON a zámek převzal, přesně ten bug, co kolo 13 mělo
zavřít. S unikátním tmp souborem na KAŽDÉ volání se tomuhle vyhne
úplně - `os.replace` je atomický bez ohledu na to, které vlákno "vyhraje"
(poslední zápis prostě přepíše logicky stejný obsah, harmless podle
odstavce výš). STEJNÉ pravidlo (unikátní tmp na každé volání, ne
sdílená cesta) platí i pro `acquire_lock`'s publish-přes-rename krok
z kola 14.

**`acquire_lock` má STEJNOU chybu při PRVOTNÍM získání zámku - fix
výš NESTAČÍ** (kolo 14 IMPORTANT - oprava chybného tvrzení z kola 13
"atomický refresh stačí, acquire_lock netřeba měnit": existující
`acquire_lock` (`src/state.py`) vytvoří soubor přes `os.open(lock_path,
O_CREAT|O_EXCL|O_WRONLY)` (atomicky VYTVOŘÍ prázdný soubor) a TEPRVE
POTOM do něj zapisuje JSON payload přes `os.fdopen(fd,...).write()` -
ÚPLNĚ STEJNÉ okno, jaké kolo 13 opravilo u `refresh_lock`, jen na
úplně PRVNÍM získání zámku: druhý proces ve stejné chvíli přečte
prázdný soubor, `_lock_is_live` to vyhodnotí jako mrtvý zámek, smaže
ho a založí vlastní - OBA procesy pak běží současně, přesně to, co má
`_MUTATING` zabránit, od úplně prvního okamžiku. Tohle NENÍ pokryto
kolem 13 fixem (ten opravil jen `refresh_lock`, ne `acquire_lock`) -
tvrzení "úprava `acquire_lock` mimo rozsah" z kola 4 bylo o ÚPLNĚ jiné
věci (přechod na OS-level `flock`/`msvcrt.locking`, širší redesign) a
zůstává v platnosti PRO TU otázku, ale netýká se TÉHLE, mnohem menší a
levnější opravy. Vzhledem k tomu, že tahle spec už `src/state.py`
zamykací modul opakovaně (kolo 2-4, 13) rozšiřuje o novou funkcionalitu
potřebnou PRÁVĚ pro dlouho běžící `polish-review`, je nekonzistentní
tenhle POSLEDNÍ kus nechat rozbitý - fix: `acquire_lock` napíše CELÝ
JSON payload do UNIKÁTNÍHO dočasného souboru (`lock_path +
f".{os.getpid()}.tmp"`), a teprve HOTOVÝ (plně napsaný, zavřený)
soubor "publikuje" na `lock_path` přes `os.rename` (NE `os.replace`) -
na Windows (tenhle projekt cílí na Windows, viz systémové prostředí;
stejný předpoklad už `init --reset` archivace v kole 6 spoléhá) `os.
rename` na EXISTUJÍCÍ cíl vyhodí `FileExistsError` (na rozdíl od POSIX,
kde by tiše přepsal - POZOR při případném běhu na Linuxu/macOS by se
tahle vlastnost MUSELA ověřit/nahradit `os.link`+`os.unlink` vzorem,
tady se spoléhá na zdokumentované Windows chování), takže `except
FileExistsError` větev v `acquire_lock` (existující kód, beze změny
struktury) zůstává funkční beze změny - jen se do ní teď NIKDY nedostane
souběžný proces uprostřed zápisu, protože soubor se na `lock_path`
objeví buď VŮBEC, nebo už KOMPLETNÍ.
`release_lock(lock_path)` (existující funkce, dnes `main.py:1356`
`run_lock` ji volá pro VŠECHNY `_MUTATING` příkazy, ne jen
`polish-review`) stejně: PŘED `os.unlink` ověří `pid == os.getpid()`,
neshoda → NEmaže (cizí, teď legitimní zámek), stejné tiché
"nemazat, není naše" chování jako dnešní `except FileNotFoundError:
pass`. PID (ne náhodný token) stačí - tenhle nástroj běží na jednom
stroji pro jednoho uživatele, souběh "starý zámek smazán, PID rychle
znovu použitý JINÝM procesem, co náhodou taky zapíše zámek se stejným
PID přesně v tom okně" je natolik nepravděpodobný, že samostatný token
navíc nepřidává prakticky žádnou hodnotu. `polish-review` server:
refresh vlákno, co dostane `LockError`, nastaví sdílený
`threading.Event` ("zámek ztracen") a vypíše hlasité varování na
konzoli ("Zámek ztracen - jiný proces teď zapisuje do DB. Ukonči tenhle
`polish-review` (Ctrl-C) a spusť znovu."); apply/revert/discard
handlery kontrolují tenhle `Event` JAKO PRVNÍ krok (před validací i CAS)
- je-li nastavený, vrátí 503 bez jakéhokoli zápisu. Žádné automatické
ukončení serveru z vlákna na pozadí (uvicorn shutdown odsud je zbytečná
komplikace) - uživatel se dozví z chybové odpovědi/konzole a proces
ukončí ručně.

**Kontrola `Event` flagu NESTAČÍ - refresh musí proběhnout SYNCHRONNĚ
při KAŽDÉM zápisu** (kolo 7 IMPORTANT, doplňuje fix výš - mezera v
načasování): background vlákno refreshuje jen jednou za 3 hodiny.
Scénář - stroj usne přes 6 h, po probuzení server BĚŽÍ dál, ale jeho
DALŠÍ naplánovaný refresh tik může být klidně skoro 3 hodiny daleko;
MEZITÍM je zámek podle timestampu "starý" a JINÝ proces ho může
legitimně převzít - a `lock_lost` `Event` se nastaví AŽ při příštím
tiku vlákna, ne hned. Write handler, co by se spoléhal JEN na
zkontrolování `Event`u, by v týhle mezeře (až 3 hodiny široké, ne
mikrosekundy jako TOCTOU níž) klidně zapsal SOUČASNĚ s novým vlastníkem.
Fix: apply/revert/discard handlery volají `refresh_lock()` SYNCHRONNĚ
jako úplně PRVNÍ krok KAŽDÉHO requestu (před validací, CAS, čímkoli) -
ne se spoléhat na to, že to už udělalo vlákno na pozadí. `LockError`
odtud → 503 okamžitě, žádný zápis. Vlákno na pozadí (kolo 2 fix) tím
neztrácí smysl - drží zámek živý i BEZ požadavků (uživatel má kartu
otevřenou, ale nic neklika) - jen přestává být JEDINÝM mechanismem, co
detekuje ztrátu vlastnictví. Po týhle opravě zůstává jen už přiznané
mikrosekundové TOCTOU okno (viz níž), ne tahle mnohem širší
hodinová mezera.

**Zbytkové riziko - zámek je NAKONEC pořád jen souborový mutex, ne
skutečný OS-level exkluzivní zámek (přiznáno, MIMO ROZSAH)** (kolo 4
BLOCKING → kolo 15 BLOCKING, sjednoceno po několika kolech postupného
zpřísňování): kola 2, 3, 7, 13 a 14 postupně opravila KAŽDOU dílčí
neatomicitu, co šla opravit BEZ přepsání celého mechanismu - refresh i
prvotní `acquire_lock` teď publikují VŽDY kompletní, nikdy částečně
zapsaný soubor (atomický zápis), ověřují vlastnictví PID před
přepsáním/smazáním, a `polish-review` refreshuje jak periodicky, tak
synchronně na začátku KAŽDÉHO zápisového requestu. I PO tomhle všem
zůstává JEDEN fundamentální race, co žádná z těchhle oprav neřeší,
protože není o atomicitě jednoho zápisu, ale o CHYBĚJÍCÍ PODMÍNĚNOSTI
převzetí zastaralého zámku (kolo 15 BLOCKING): dva procesy A i B mohou
NEZÁVISLE přečíst TÝŽ starý zámek, OBA ho nezávisle vyhodnotit jako
"mrtvý" (`_lock_is_live() == False`), a pak OBA provést "smaž starý,
založ vlastní" - i kdyby to bylo přeuspořádáno/zrychleno na jeden
atomický krok, jde principiálně o NEPODMÍNĚNÉ přepsání souboru na dané
cestě (`os.unlink`/`os.replace` nezná/nekontroluje, ČÍ konkrétní starý
obsah tam zrovna je), ne o ověřenou výměnu "smaž TENHLE konkrétní starý
zámek, jinak selži" (compare-and-swap). Stihne-li B smazat starý a
založit svůj NOVÝ platný zámek dřív, než A provede SVÉ (na základě
stejného, teď už zastaralého čtení naplánované) smazání, A smaže
B's ŽIVÝ zámek a založí vlastní - oba pak běží současně. Skutečné
řešení potřebuje buď opravdový OS-level exkluzivní zámek (`msvcrt.
locking` na Windows / `fcntl.flock` na POSIX), nebo přesun vlastnictví
zámku do SQLite (transakce - `state.py` už s DB pracuje, `BEGIN
IMMEDIATE` by dal skutečnou atomicitu zdarma) - OBOJÍ by ale znamenalo
přepsat `acquire_lock`/`release_lock`/`_lock_is_live` mechanismus jako
CELEK, používaný VŠECH šesti `_MUTATING` příkazů a součást `2026-09-08`
konsensu, ne jen tenhle review workflow - žádná "ještě jedna atomická
operace navíc" tenhle typ race nezavře, protože jde o jinou TŘÍDU
problému (podmíněnost/vlastnictví, ne atomicita jednoho zápisu), na
rozdíl od VŠECH předchozích šesti kol lock oprav. Tohle je proto
POSLEDNÍ a ZÁSADNÍ hranice toho, co jde opravit v rámci "rozšiřuje
`polish`" scope týhle spec - zaznamenáno jako doporučené budoucí
rozšíření `2026-09-08` specu (samostatná diskuze/ping-pong o přechodu
na skutečný OS/DB zámek), ne řešeno tady. Praktické ohraničení: aby se
projevil, musí existovat SKUTEČNĚ zastaralý zámek (6+ h neaktivity, po
kole 2-7 fixech je tohle samo o sobě už vzácné pro `polish-review`) A
DVA NEZÁVISLÉ procesy musí zahájit `acquire_lock` téměř SOUČASNĚ - pro
jednoho uživatele, co ručně spouští příkazy v terminálu (ne server
obsluhující souběžné klienty), je tenhle konkrétní souběh dvou
NOVÝCH procesů výrazně nepravděpodobnější než cokoli, co předchozí
kola řešila.

**Souběžné HTTP requesty na TOMTÉŽ serveru** (kolo 2 BLOCKING - dřív
přehlédnuto): `state.run_lock` chrání jen před JINÝMI procesy (`run`,
`answer`, druhá instance) - v rámci JEDNOHO běžícího `polish-review`
serveru FastAPI/uvicorn může dva HTTP requesty (dva rychlé kliky, dvě
otevřené karty) zpracovávat souběžně (synchronní `def` handlery běží ve
sdíleném threadpoolu). Dva souběžné `apply`/`revert` na STEJNÉ `idx` by
mohly oba projít CAS kontrolou (oba čtou stejný "starý" DB stav dřív, než
kterýkoli stihne zapsat) a oba zapsat - přesně ten race, co CAS měla
zabránit, jen na jinou úroveň (mezi vlákny, ne mezi procesy). Fix: jeden
modulový `threading.Lock()` v `polish_server.py`, co obaluje CELÉ tělo
`apply`/`revert`/`discard` handlerů (CAS čtení + zápis DB + zápis obou
JSON souborů pod JEDNÍM `with lock:` blokem) - jednoduchá serializace v
rámci procesu, dostatečná pro jednoho uživatele v prohlížeči (žádný
distribuovaný/víceprocesový server tu neběží).

**Záloha DB v `polish-review`** (kolo 1 BLOCKING - dřív nedořešeno):
`_backup_db_once` PROMUJE už existující snapshot (`backup_state
["snapshot_path"]`) - sama snapshot nevytváří. Dnešní `_cmd_polish`
snapshot vytváří PŘED `create_run` (viz jeho sekce výš); `polish-review`
žádný `create_run`/dávku nemá, ale potřebuje STEJNÝ mechanismus: server
při STARTU (ne až při prvním zápisu - `run`u tu není, není proč čekat)
vytvoří `backup_state = {"done": False, "snapshot_path": db +
".pre-polish-review-snapshot"}` a zavolá `_snapshot_db(db, backup_state
["snapshot_path"])` (chyba zde = server se nespustí, žádný endpoint
neběží bez funkční zálohy). `POST /api/polish/apply` i `/revert` pak
volají `_backup_db_once(db, backup_state)` přesně jako dřív
`_polish_one_chapter` - PŘED prvním skutečným zápisem za běh serveru,
podruhé už no-op. Při ukončení serveru (Ctrl-C i čisté zavření) se
nepromovaný dočasný snapshot smaže stejným "best-effort `os.remove`,
`backup_state["done"]` teprve po `_backup_db_once`" vzorem jako
`_cmd_polish`.

**CAS kontrola PROTI zastaralému draftu/historii** (kolo 1 BLOCKING -
dřív žádná): mezi `polish` (vznikne draft) a kliknutím na "Uložit" v
`polish-review` může DB kapitolu změnit JINÝ běh (typicky `answer`, co
požádovanou kapitolu "requeuje" k přepočtu - `_cmd_answer`/
`requeue.apply_answer`). Draft postavený na starším `cz_before` by pak
bez kontroly přepsal novější legitimní text. Fix, oba zapisující
endpointy: PŘED voláním `_backup_db_once`/`commit_chapter_result` načíst
AKTUÁLNÍ `translated_text` I `status` z DB (`state.get_chapter(db,
idx)`) a porovnat OBOJÍ (kolo 17 IMPORTANT - dřív jen `translated_
text`; `answer`/`requeue.apply_answer` může kapitolu přepnout na
`status="pending"` (čeká na `run`), ANIŽ by hned změnil `translated_
text` - starý text tam zůstává, dokud `run` kapitolu skutečně
nezpracuje. CAS jen na text by tenhle případ PROPUSTIL - `apply`/
`revert` by pak zavolaly `commit_chapter_result(..., status="done",
...)` a TICHE vrátily kapitolu na `"done"`, čímž by obešly a zahodily
povinné přepracování po `answer`u, aniž by cokoli signalizovaly):
  - `apply`: `translated_text` musí přesně sedět s `cz_before` z draft
    záznamu A `status` musí být `"done"`.
  - `revert`: `translated_text` musí přesně sedět s `cz_after`
    POSLEDNÍHO historického záznamu pro `idx` (= tím, co se má vracet
    ZE) A `status` musí být `"done"`.
  Neshoda (text NEBO status) → HTTP 409, ŽÁDNÝ zápis (ani do DB, ani do
  JSON souborů),
  odpověď obsahuje krátké vysvětlení ("kapitola se mezitím změnila mimo
  tenhle review - pravděpodobně `answer`/nová revize; zkontroluj
  aktuální text, případně spusť `polish` znovu"). CAS + `threading.Lock`
  výš SPOLU zabraňují DUPLICITNÍMU/soutěžícímu zápisu (dva pokusy o
  zápis stejné operace, ať už retry po chybě, nebo dva rychlé kliky) -
  jakýkoli DALŠÍ pokus o apply/revert STEJNÉHO draft záznamu po úspěšném
  DB commitu selže na CAS (DB už nese `cz_after` ≠ `cz_before`), takže
  nikdy nedojde k druhému zápisu TÉŽE změny. Zápisové pořadí je DB →
  historie → odebrání z draftu (každý JSON soubor zvlášť atomicky
  tmp+`os.replace`).

  **CO CAS NEŘEŠÍ - vědomě přijaté zbytkové riziko** (kolo 2 BLOCKING,
  oprava přehnaného tvrzení z kola 1 - CAS zajišťuje "nikdy dvakrát", ne
  "vždy úplně dokončeno"): pád PŘESNĚ mezi úspěšným DB commitem a
  zápisem do `polish.history.json` (dvě rychlé lokální operace v témže
  volání, ale ne jedna atomická transakce napříč DB+JSON souborem)
  nechá kapitolu ÚSPĚŠNĚ uloženou v DB, ale BEZ historického záznamu -
  revert pro ni přes UI nepůjde (historie o ní neví) a draft záznam
  zůstane navždy CAS-konfliktní (DB se už nikdy nebude shodovat s jeho
  `cz_before`) - jediná cesta ven je `discard` (odebrat z fronty ručně,
  viz endpoint níž). Automatická rekonstrukce historického záznamu
  ZÁMĚRNĚ není součástí týhle spec - server nemá spolehlivý způsob,
  jak odlišit "tohle je moje vlastní nedokončená operace" od "tohle
  změnil `answer`/jiný proces" jen z DB obsahu (stejná dvojznačnost,
  co plný idempotency-ID protokol z kola 1 Codex kritiky řeší, ale za
  cenu složitosti, co pro jednoho uživatele na jednom stroji a
  MILISEKUNDOVÉ okno pádu neobstojí proti přínosu). Riziko je
  zdokumentované, ohraničené (jen tenhle jeden úzký okamžik, ne celý
  request) a viditelné (příští `apply` pokus na stejnou `idx` dostane
  409, ne tichou korupci) - stejný princip jako "ZBÝVAJÍCÍ NEVYŘEŠENÉ
  RIZIKO" already přijaté u `_backup_db_once` obnovy (viz jeho
  docstring v `main.py`).

  **Detekce (ne automatická oprava)** (kolo 3 BLOCKING, zpřesnění -
  Codex kritika v kole 3 správně namítla, že "jen 409 při dalším apply"
  je PASIVNÍ - mezera se odhalí jen NÁHODOU, když se o stejnou `idx`
  někdo znovu pokusí, ne aktivně): `GET /api/polish` PŘI KAŽDÉM volání
  projde draft záznamy a pro každý, kde aktuální DB `translated_text`
  NEODPOVÍDÁ `cz_before` draftu, označí ho `"stale": true` a rozliší
  DVA podpřípady (kolo 4 IMPORTANT - dřív pokrýval jen první, druhý
  zůstával nedetekovaný "tichý pending", co navíc navždy blokuje
  preflight `polish`u):
  - Existuje odpovídající záznam v historii (`idx` sedí A `cz_after`
    sedí s aktuálním DB textem) → commit i historie PROBĚHLY úspěšně,
    jen selhalo POSLEDNÍ odebrání z draftu. Příznak
    `"reason": "already_committed_has_history"` - UI: "tahle kapitola
    už byla uložena (viz historie), zbývá jen odebrat z fronty -
    `discard`". Revert pro ni funguje normálně (historie existuje).
  - NEexistuje odpovídající záznam → `"reason":
    "likely_committed_without_history"` (kolo 3 tvar) - UI: "tahle
    kapitola byla pravděpodobně už uložena, ale chybí záznam v historii
    (revert pro ni nepůjde) - zkontroluj text v knize ručně, pak
    `discard` odstraní tenhle záznam z fronty".

  Žádná automatická rekonstrukce/odebrání - v OBOU případech čeká na
  ruční `discard` (ten teď navíc odemyká preflight `polish`u, co jinak
  neprázdný draft odmítá běžet). Server nemá jak spolehlivě odlišit
  "tohle je moje vlastní nedokončená operace" od "změnil to
  `answer`/jiný proces" jen z DB obsahu (stejný důvod jako v kole 1
  Disagreed), ale AKTIVNÍ detekce při KAŽDÉM načtení stránky (ne jen
  při náhodném retry) dělá obě mezery viditelné hned, ne až za týden.
- `GET /api/polish` - vrátí obsah `polish.draft.json` (pending, se
  `stale`/`likely_committed_without_history` příznakem popsaným výš) +
  posledních N záznamů `polish.history.json` (pro sekci "Historie",
  N/řazení viz sekce `polish.history.json` výš). Volitelný query
  parametr `?idx=N` (kolo 3 IMPORTANT - dřív chybělo): vrátí VŠECHNY
  historické záznamy pro konkrétní `idx`, bez ohledu na globální limit
  N=20 - "posledních 20" v hlavním pohledu je jen DEFAULT rozcestník
  ("co se nedávno dělo"), ne strop na to, co jde revertovat. UI k tomu
  přidá jednoduché pole "najít historii kapitoly č.": zadá se `idx`,
  zavolá se `GET /api/polish?idx=N`, zobrazí se JEJÍ celá historie s
  tlačítky "vrať zpět" - takhle jde revertovat i kapitola rozhodnutá
  dávno před posledními dvaceti položkami. `POST /api/polish/revert`
  samo o sobě limit NEMÁ (vždy čte celý soubor a hledá poslední záznam
  pro `idx`) - limit N=20 je čistě vlastnost `GET`u/UI, ne funkční
  omezení revertu.
**Validace vstupu** (kolo 2 IMPORTANT - dřív nezmíněno, endpointy by bez
tohohle padaly na 500 místo srozumitelného 4xx): `apply`/`revert`/
`discard` NEJDŘÍV ověří tvar požadavku (`idx` je `int`, u `apply` navíc
`text` je `str` - `None`/chybějící/špatný typ → 400 BEZ jakéhokoli
výpočtu, konkordance na `None` by spadla o úroveň níž jako
nesrozumitelná 500), PAK že `idx` existuje v `polish.draft.json` (`apply`)
resp. má aspoň jeden záznam v `polish.history.json` (`revert`) - chybějící
→ 404 ("kapitola už není ve frontě/historii - zkontroluj, jestli mezitím
neproběhla v jiné kartě"). AŽ PO těchhle kontrolách přichází CAS kontrola
výš (409 při konfliktu).

- `POST /api/polish/apply` - payload `{"idx": 1, "text": "..."}` (JEDNA
  kapitola, uloženo přes AJAX při kliknutí - ne jedno velké odeslání na
  konci, ať se needitovaná práce neztratí při zavření okna/pádu
  prohlížeče). Server: validace + CAS kontrola výš, `_backup_db_once`,
  `state.commit_chapter_result` s `translated_text=text` (přesně to, co
  bylo v textovém poli - ne `styled`, ne `cz_before`, cokoli uživatel
  uložil) a `revision_rounds` = hodnota přečtená z AKTUÁLNÍHO DB řádku
  během CAS kontroly (kolo 2 IMPORTANT - NE z draftu; draft je jen
  snapshot z doby `polish`, DB řádek je zdroj pravdy a CAS už ho stejně
  musela načíst, takže žádné extra čtení navíc). Před commitem se
  PŘEPOČÍTAJÍ `mentions` na aktuálním glosáři
  (kolo 1 BLOCKING - `commit_chapter_result` VŽDY smaže a znovu vloží
  `term_mentions` pro `idx`; prázdné/zastaralé `mentions` by tichem
  poškodily konkordanci): načíst `en = state.get_chapter(db, idx)
  ["raw_text"]` (neměnné od `init`), `glossary_rows =
  glossary.all_terms(db)` ČERSTVĚ (ne z draftu - glosář se mohl mezitím
  změnit přes `answer`/`reference`), ALE `rendered_terms` NE čerstvě z
  DB (kolo 18 IMPORTANT, oprava - viz níž proč), nýbrž `draft.
  rendered_terms` (nové pole, viz schéma draftu výš a `_polish_one_
  chapter` popis níž), pak `mentions = concordance.build_mentions(en,
  text, glossary_rows, draft.rendered_terms)` - přesně stejný recept,
  jaký dnes používá `_polish_one_chapter` PŘED vlastním commitem, jen
  nad `text` (uživatelův finální obsah) místo `styled` (Codexův raw
  návrh) a s `rendered_terms` PŘENESENÝM z draftu, ne přečteným znovu.
  Historický záznam, co tenhle apply vytváří (viz níž), nese STEJNOU
  hodnotu `rendered_terms` dál - žádný další výpočet, jen přenos.

  **Proč `rendered_terms` NESMÍ jít z živé DB při apply/revert** (kolo
  18 IMPORTANT - `state.chapter_mentions(db, idx)` čtená TEĎ by dala
  ŠPATNOU odpověď): `rendered_terms` je translatorovo VLASTNÍ hlášení
  formy termínu, co konkordance sama nedohledá povrchem - `build_
  mentions` z NĚJ jen VYBERE ty formy, co se SKUTEČNĚ najdou v
  KONKRÉTNÍM kontrolovaném textu (`_term_mentions` ověřuje `form in
  text`), a do `term_mentions` zapíše jen tenhle vybraný podmnožinu.
  Kdyby `polish-review` četlo `rendered_terms` ZNOVU z `state.chapter_
  mentions(db, idx)` PO prvním apply, dostalo by právě tuhle OKLESANOU
  podmnožinu (co `build_mentions` naposledy skutečně NAŠLO ve `styled`/
  `text`), ne původní translatorův kompletní report - forma, co byla v
  originále, ale ve stylizovaném textu chyběla, by z týhle "živé" sady
  navždy zmizela, i kdyby ji POZDĚJŠÍ `revert` vrátil zpátky do textu,
  kde by patřila. `rendered_terms` je proto NEMĚNNÁ hodnota napříč
  CELÝM draft→apply→revert(→revert revertu→...) řetězcem pro danou
  kapitolu - vznikne JEDNOU v `_polish_one_chapter` (existující výpočet,
  dřív jen lokální proměnná, teď se navíc uloží do draftu), a STEJNÁ
  hodnota se jen PŘENÁŠÍ dál (draft → apply → jeho history entry →
  případný revert čte `rendered_terms` z REVERTOVANÉHO entry, ne z DB →
  jeho vlastní nový entry nese STEJNOU hodnotu dál).
  `notes_json` = `findings` z draft záznamu (nálezy platné pro `styled` -
  ponechávají se jako historický kontext, i když uživatel text upravil)
  + JEDEN nový marker. **Marker `type` závisí na tom, jestli uživatel
  text SKUTEČNĚ stylizoval, nebo jen potvrdil originál** (kolo 7
  IMPORTANT - dřív se vždy použil `type: "polish"`, i když `text ==
  cz_before` přesně, typicky po kliknutí "vrať na originál" a rovnou
  "Uložit" - takový marker by nepravdivě tvrdil, že kapitola BYLA
  stylizována, a `_already_styled` (kolo 5 fix výš) by ji bez `--force`
  navždy přeskakoval, i když fakticky zůstala nezměněná - stejný
  problém, jaký kolo 5 řešilo pro revert, jen jinou cestou ke stejnému
  stavu): pokud `text != cz_before`, marker = `_stylist_marker(cz_before,
  model)`-tvarový nález (`type: "polish"`, beze změny) - kapitola BYLA
  (aspoň zčásti) stylizovaná ruční úpravou/Codexem. Pokud `text ==
  cz_before` PŘESNĚ, marker místo toho `{"source": "stylist", "type":
  "kept_original", "severity": "info", "action": "note", "issue":
  "potvrzeno ponechání originálu přes polish-review (bez věcné změny)",
  ...}` - `_already_styled` ho nesplní (vyžaduje `type == "polish"`),
  takže `polish` může tuhle kapitolu nabídnout znovu bez `--force`,
  přesně jako po revertu. `model`/hash/délka se v OBOU případech počítají
  z `text` (skutečně uloženého), ne ze `styled` - marker se připojuje
  PRÁVĚ JEDNOU, stejné pravidlo jako dnešní `_polish_one_chapter`. Po
  úspěchu (v tomhle pořadí - viz CAS odstavec výš): commit DB → **JEN
  když `text != cz_before`** připoj záznam do `polish.history.json`
  (`cz_before`=originál z draftu, `cz_after`=`text`, `styled_by_codex`=
  Codexův raw návrh, `source="polish-review"`) → odeber `idx` z
  `polish.draft.json`.

  **Apply BEZ věcné změny (`text == cz_before`, `type: "kept_original"`
  marker výš) NEVYTVÁŘÍ historický záznam** (kolo 11 IMPORTANT - dřív by
  i no-op apply vždy zapsal do historie, a tenhle záznam by se stal
  "posledním" pro `idx` - `revert` by pak podle "poslední záznam"
  pravidla (kolo 6 fix) vracel text SÁM NA SEBE napořád, a nikdy by se
  nedostal k PŘEDCHOZÍMU skutečnému kroku, co jediný má smysl vracet).
  Commit DB pořád proběhne (nové `notes`/marker se uloží, i když text
  stejný), jen se PŘESKOČÍ krok "připoj do historie" - revert tak vždy
  najde poslední záznam se SKUTEČNOU změnou textu, žádná speciální
  filtrace na straně revertu není potřeba. Draft záznam se i tak odebere
  normálně (rozhodnutí bylo učiněno, jen bez dopadu na text).
- `POST /api/polish/revert` - payload `{"idx": 1, "to": "previous" |
  "original"}` (`to` volitelné, default `"previous"` - kolo 19
  IMPORTANT, viz zdůvodnění níž). NEJDŘÍV zkontroluje,
  jestli PRO STEJNOU `idx` neexistuje nevyřízený záznam v
  `polish.draft.json` (kolo 8 IMPORTANT - scénář: apply proběhne,
  uživatel spustí `polish --force` na STEJNOU kapitolu, vznikne NOVÝ
  draft s `cz_before` = právě stylizovaný text; revert PŮVODNÍHO apply
  by DB vrátil na verzi PŘED oběma kroky, a ten nový draft by od tý
  chvíle navždy nesouhlasil s DB - CAS by ho sice chránila před
  špatným zápisem, ale `polish` preflight by zůstal navždy blokovaný
  neprázdným draftem, dokud by ho někdo ručně nenašel a nezahodil).
  Existuje-li takový draft záznam → 409 BEZ zápisu ("kapitola má
  nevyřízený draft z novějšího `polish` běhu - nejdřív ho vyřeš (ulož
  nebo zahoď), pak zkus revert znovu").

  **`to: "previous"` vs. `to: "original"`** (kolo 19 IMPORTANT - dřív
  jen jeden krok zpět, viz zdůvodnění): CAS kontrola SE VŽDY dělá proti
  POSLEDNÍMU záznamu (`entries` poslední prvek pro `idx`, stejně jako
  dřív) - ověřuje se, jestli DB mezitím nezměnil NĚKDO JINÝ
  (`answer`/nová revize), bez ohledu na to, KAM se má vracet.
  CÍLOVÝ text (co se zapíše jako nový `translated_text`) se ale liší:
  - `to: "previous"` (default, dřívější a jediné chování): cíl =
    `cz_before` POSLEDNÍHO záznamu - jeden krok zpět.
  - `to: "original"`: cíl = `cz_before` PRVNÍHO záznamu SOUVISLÉHO
    ŘETĚZCE končícího POSLEDNÍM záznamem (kolo 20 IMPORTANT, oprava -
    NENÍ prostě "úplně první záznam pro `idx`", viz zdůvodnění níž).
    Výpočet: od POSLEDNÍHO záznamu jdi zpět (`entries` pro daný `idx`,
    od konce) a POKUD `entries[i-1].cz_after == entries[i].cz_before`,
    pokračuj na `i-1`; jakmile tahle rovnost NESEDÍ (nebo `i` došlo na
    úplný začátek), ZASTAV - `entries[i]` je začátek souvislého řetězce
    a JEHO `cz_before` je cíl. Tenhle záznam je VŽDY z `apply` (nikdy z
    `revert` - revert může vzniknout jen POTÉ, co už nějaký apply v
    TÉTO větvi existuje), takže jeho `cz_before` je zaručeně "čistý"
    pre-stylizační text PRO TENHLE ŘETĚZEC.

    **Proč ne prostě "úplně první záznam pro `idx`"** (kolo 20
    IMPORTANT): historie NENÍ nutně JEDNA souvislá stylizační větev.
    Příklad: `polish` udělá `X → A` (entry1), PAK - MIMO tenhle
    workflow - `answer` požádá o přepočet a `run` vytvoří ÚPLNĚ JINÝ
    překlad `Y` (legitimní, nesouvisející s `A`), PAK `polish` znovu
    udělá `Y → B` (entry2, `cz_before=Y`, NE `A`). Pole `entries` pro
    tenhle `idx` teď obsahuje `[entry1(X→A), entry2(Y→B)]`, ale `entry1.
    cz_after (A)` a `entry2.cz_before (Y)` na sebe VŮBEC NENAVAZUJÍ -
    `A` bylo dávno přepsáno nesouvisejícím `Y` dřív, než druhá stylizace
    vůbec začala. Naivní "vezmi cz_before úplně prvního záznamu" (kolo
    19 původní návrh) by zvolilo `X` jako cíl - ale `X` NENÍ "originál
    PŘED aktuální/nejnovější stylizací", je to zbytek z JINÉ, dávno
    nahrazené epizody; zápis `X` by TICHE zahodil legitimní `Y`
    (mezilehlý překlad, co s `polish` workflow vůbec nesouvisel).
    Walk-back-dokud-navazuje algoritmus výš tenhle případ správně
    zastaví na `entry2` a vrátí `Y`, ne `X`.

    **Zbytkové riziko - shoda TEXTU není důkaz návaznosti (přiznáno,
    MIMO ROZSAH)** (kolo 21 IMPORTANT): walk-back algoritmus výš pozná
    "navazuje" jen porovnáním TEXTU (`starší.cz_after ==
    novější.cz_before`) - to je NUTNÁ, ale ne DOSTATEČNÁ podmínka.
    Teoretický protipříklad: `X → A` (entry1), PAK mimo `polish`
    `answer`/`run` cyklus NÁHODOU (nebo cíleně - odpověď na otázku
    fakticky nic nezmění) vyprodukuje text, co je BYTOVĚ shodný s `A`,
    PAK `polish` znovu udělá `A → B` (entry2, `cz_before` = tahle
    shoda s `A`). Walk-back by tohle vyhodnotil jako NAVAZUJÍCÍ (texty
    sedí) a vrátil `X` jako "originál", i když skutečný stav TĚSNĚ
    PŘED druhou stylizací byl `A`, co se jen náhodou/nesouvisle rovná
    prvnímu `cz_after`. Skutečné řešení by potřebovalo MONOTÓNNÍ
    per-kapitolové číslo generace/verze v DB (inkrementované PŘI
    KAŽDÉM zápisu `translated_text`, nejen v `polish-review`, ale i
    v `run`/`answer` pipeline), uložené v KAŽDÉM historickém záznamu, a
    walk-back by pak vyžadoval návaznost ČÍSLA generace, ne jen textu.
    To by ale znamenalo změnu `state.commit_chapter_result`/schématu
    `chapters` tabulky - sdílené se VŠEMI zapisujícími cestami (`run`,
    `answer`, `polish-review`), ne jen tenhle review workflow - stejná
    třída otázky jako kolo 15 (MIMO ROZSAH týhle spec, zaznamenáno jako
    kandidát pro STEJNÝ doporučený budoucí ping-pong o `2026-09-08`
    lock/verzování). Prakticky: aby se projevil, `answer`/`run` cyklus
    (spuštěný PROTO, že se má kapitola PŘELOŽIT JINAK) by musel
    vyprodukovat BYTOVĚ IDENTICKÝ výsledek jako PŘED sebou - odporuje
    samotnému důvodu, proč se kapitola vůbec requeuje (translate/revise
    pipeline mění text SMYSLUPLNĚ, ne beze změny) - výrazně užší než
    scénář, co walk-back fix už řeší.

  **Proč je tohle potřeba** (kolo 19 IMPORTANT, důvod): `revert` byl
  navržený jako sám o sobě odvolatelný (kolo 5 - "klikni vrať zpět
  znovu = vrátí revert") - to je žádoucí bezpečnostní síť PROTI omylu,
  ale má vedlejší efekt: po DVOU skutečných `apply` (`X → A → B`,
  typicky přes `polish --force` na už jednou přijatou kapitolu, viz
  scénář výš) by `to: "previous"` opakovaně jen PŘEPÍNAL mezi
  POSLEDNÍMI dvěma stavy (`B → A`, další klik `A → B`, další `B → A`...)
  a na `X` (skutečný originál) by se UŽ NIKDY nešlo dostat jen
  opakovaným klikáním "vrať zpět" - to by přímo odporovalo vlastnímu
  cíli dokumentu ("vrať na verzi PŘED stylizací"), pokud proběhly VÍC
  než jedna stylizace. `to: "original"` tenhle případ řeší přímo, beze
  změny CAS mechanismu (pořád jen proti POSLEDNÍMU záznamu, žádná
  "vyber libovolnou historickou verzi" komplikace) - UI (viz níž)
  nabídne obě tlačítka jen když existují ALESPOŇ 2 záznamy pro `idx`
  (u přesně 1 záznamu dělají obě varianty totéž).

  **No-op revert - CÍLOVÝ text == aktuální DB text - se VŮBEC
  nezapisuje** (kolo 22 IMPORTANT - dřív chybělo, vedlo by k reálnému
  zaseknutí): po CAS ověření (DB odpovídá poslednímu záznamu) se
  PŘED zálohou/commitem porovná CÍLOVÝ text (viz výš, podle `to`) s
  AKTUÁLNÍM DB textem (= tím, co CAS zrovna ověřila). Jsou-li STEJNÉ,
  endpoint vrátí 200 s `{"noop": true}` a NEPROVEDE vůbec nic - žádný
  `_backup_db_once`, žádný `commit_chapter_result`, ŽÁDNÝ nový záznam v
  historii. Bez tohohle by mohl vzniknout no-op historický krok
  (`cz_before == cz_after`), co se sám stane "posledním" - a protože
  no-op krok samotný nijak nemění text, "vrať zpět" (`to: "previous"`)
  spuštěné Z NĚJ by zase jen zapsalo DALŠÍ no-op krok se STEJNÝM cílem,
  navždy dokola, bez šance dostat se zpátky na skutečně odlišnou
  starší verzi (konkrétní scénář: `X → A` apply, `vrať zpět` udělá
  `A → X` - řetězec má teď délku 2, `to: "original"` by pak podle kola
  20 walk-backu znovu zamířilo na `X`, což se PŘESNĚ rovná aktuálnímu
  stavu - bez tyhle no-op kontroly by to zapsalo `X → X`, a odtamtud by
  UŽ nešlo přes UI kliknutí dostat zpátky na `A`). UI navíc (viz níž)
  tlačítko rovnou NENABÍDNE, pokud jeho cíl už odpovídá aktuálnímu
  textu - server-side no-op kontrola je ale to, co skutečně garantuje
  bezpečnost (UI kontrola je jen pohodlí, ne jediná ochrana).

  Zapíše CÍLOVÝ text jako nový `translated_text` (`_backup_db_once` +
  `commit_chapter_result` stejně jako výš). `mentions` se přepočítají
  STEJNÝM receptem jako u apply, nad CÍLOVÝM textem, ale s
  `rendered_terms` PŘEVZATÝM z odpovídajícího historického záznamu
  (kolo 18 IMPORTANT - NE z živé DB, viz zdůvodnění u apply výš; kolo 18
  fix navíc zaručuje, že `rendered_terms` je STEJNÁ hodnota napříč
  CELÝM řetězcem pro `idx`, takže nezáleží, jestli se bere z posledního
  nebo prvního záznamu - jsou identické).
  `notes_json` pro revert: NEpřebírá nálezy z historického záznamu (ty
  platí pro JINOU verzi textu) - přepočítá se ČERSTVĚ deterministická
  konkordance NAD CÍLOVÝM textem (kolo 21 IMPORTANT, zpřesnění
  pojmenování - dřív psáno jako `check_chapter(en, cz_before, ...)`,
  což je NEJEDNOZNAČNÉ: "cz_before" mohlo znamenat buď schémový název
  pole NOVÉHO historického záznamu = TEXT, CO SE OPOUŠTÍ /* ŠPATNĚ */,
  nebo hovorově "obnovovaný text" = TEXT, CO SE UKLÁDÁ /* SPRÁVNĚ */.
  Findings/notes musí popisovat text, co SKUTEČNĚ jde do knihy, ne ten,
  co se právě nahrazuje): `concordance.check_chapter(en, <CÍLOVÝ text -
  viz "Zapíše CÍLOVÝ text..." výš, `to: "previous"` → `cz_before`
  posledního záznamu, `to: "original"` → `cz_before` začátku souvislého
  řetězce>, glossary_rows, rendered_terms)` (STEJNÉ převzaté
  `rendered_terms`, ne živé DB čtení; kritik/meaning-check se NEspouští
  znovu - placená
  LLM volání jen kvůli revertu na text, co už jednou prošel, by byla
  zbytečná) + nový nález typu `{"source": "stylist", "type": "revert",
  "severity": "info", "action": "note", "issue": "vráceno na verzi před
  <'poslední stylizací' pro to=previous / 'JAKOUKOLI stylizací' pro
  to=original> (historie idx=N, applied_at=...)"}` - text nálezu odráží,
  KTERÝ cíl (`to`) byl použit. Po úspěchu: connej nový
  záznam do `polish.history.json` - VŠECHNA povinná pole (viz tabulka
  výš), ne jen `source`/`cz_before`/`cz_after` (kolo 12 IMPORTANT,
  doplnění - dřív by revert bez přesné definice vytvořil buď nevalidní
  záznam, nebo si "vymyslel" hodnotu): `idx`=stejné, `applied_at`=teď
  (UTC+`Z`), `cz_before`=to, co se právě vrátilo - VŽDY `cz_after`
  POSLEDNÍHO záznamu (= to, co CAS zrovna ověřila proti živé DB,
  bez ohledu na `to`), `cz_after`=CÍLOVÝ text (`to: "previous"` →
  `cz_before` posledního záznamu; `to: "original"` → `cz_before`
  PRVNÍHO záznamu, viz výš), `styled_by_codex`=`""` (revert nemá žádný
  Codexův návrh - prázdný řetězec, ne `null`, ať pole zůstane typu `str`
  podle tabulky výš), `title`=`title` z POSLEDNÍHO historického záznamu
  (kapitola se nepřejmenovává, všechny záznamy pro `idx` mají stejný
  `title`), `findings`=PŘESNĚ ten seznam (čerstvá konkordance + revert
  marker), co jde i do `notes_json` výš (žádný druhý výpočet navíc),
  `rendered_terms`=STEJNÁ hodnota (kolo 18 fix zaručuje identickou
  hodnotu napříč celým řetězcem, viz výš), `source="revert"`.

  **`_already_styled` musí umět rozlišit "stylizováno" od "vráceno
  zpět"** (kolo 5 IMPORTANT - dřív přehlédnuto): stávající `main.py`
  (`_already_styled`, viz `_polish_rejected`/preflight `_cmd_polish`)
  testuje `any(f.get("source") == "stylist" for f in findings)` - JEN
  `source`, ne `type`. Revert marker výš má `source: "stylist"` (stejně
  jako `_stylist_marker` z apply), takže po revertu by `_already_styled`
  vrátil `True` navždy - kapitola vrácená na předstylizační text by se
  bez `--force` už NIKDY znovu nenabídla k `polish`u, i když je to
  přesně ten stav (nezměněný, ne-stylizovaný text), na který `--force`
  gate cílí. Fix: `_already_styled` se mění na `any(f.get("source") ==
  "stylist" and f.get("type") == "polish" for f in findings)` - marker
  z ÚSPĚŠNÉ apply se SKUTEČNOU změnou textu má `type: "polish"`
  (`_stylist_marker`, beze změny), revert marker má `type: "revert"`
  (výš), apply BEZ věcné změny (`text == cz_before`, viz `apply`
  endpoint popis níž) má `type: "kept_original"` - JEN ten první
  `_already_styled` splňuje, přesně podle záměru (revert i "potvrzený
  originál" = "chovej se, jako by kapitola ještě nebyla stylizována").
- `POST /api/polish/discard` - payload `{"idx": 1}` (kolo 1 IMPORTANT,
  nová): odebere `idx` z `polish.draft.json` BEZ zápisu do DB/historie -
  pro dvě situace: (1) uživatel se rozhodl kapitolu tentokrát vůbec
  neřešit a nechce ji vidět ve frontě dokola (na rozdíl od "nechat na
  příště" prostým nezavřením prohlížeče - `discard` je EXPLICITNÍ "tohle
  nechci review"), (2) úklid po CAS konfliktu výš (položka, co už
  neodpovídá aktuální DB, se dá z fronty odebrat bez dalšího zásahu).
  Vrací 200 i když `idx` v draftu nebyl (idempotentní no-op).

  **Zahodit NENÍ trvalé vyloučení** (kolo 5 IMPORTANT, zúžení tvrzení -
  dřív znělo jako "kapitolu už nikdy neuvidíš", což `discard` nesplňuje):
  `discard` maže JEN aktuální návrh z `polish.draft.json`. Nikam se
  netrvale nezapisuje, že tahle KONKRÉTNÍ kapitola/text byl zahozen -
  spustí-li se `polish` znovu nad STEJNOU (nezměněnou) kapitolou, Codex
  velmi pravděpodobně navrhne PODOBNÝ text znovu a draft záznam se
  objeví nanovo. To je VĚDOMĚ přijatý kompromis (trvalá evidence
  "tohle nechci navrhovat znovu" by potřebovala samostatný perzistentní
  seznam klíčovaný obsahem/hashem kapitoly, se svými vlastními otázkami
  - kdy ho čistit, co s `init --reset` - a pro osobní nástroj, kde
  uživatel `polish` spouští ručně a vědomě, tahle složitost nestojí za
  přínos). `discard` řeší přesně DVĚ věci: (1) "tuhle položku nechci
  řešit HNED TEĎ, odstraň ji z fronty" (bez trvalého závazku), (2)
  úklid CAS-konfliktních/stale položek popsaných výš.
- Žádný "uložením končí" protokol jako `review` - `polish-review` se
  ukončí jen zavřením okna/Ctrl-C, návratový kód vždy 0 (žádný CLI krok po
  něm nezávisí na tom, jestli něco bylo rozhodnuto).
- Server poslouchá VÝHRADNĚ na `host="127.0.0.1"` (kolo 1 NIT) - stejně
  jako `review`, endpoint co přijímá libovolný text do DB nemá důvod
  rozšiřovat útokovou plochu na síť.

### UI (`src/review_ui/static/polish.html`, nová)

Tabulka: kapitola (idx, title), nálezy (seznam, JEN k přečtení - typ,
závažnost, popis).

**Text před/po** (kolo 5 IMPORTANT - dřív jen jedno editovatelné pole,
"vrať na originál" ho tiše PŘEPISOVALO, takže originál nešel porovnat s
návrhem ani s rozpracovanou ruční úpravou zároveň - přímo proti
hlavnímu cíli dokumentu, "uživatel vidí text před/po"): DVĚ oddělené
plochy vedle sebe. VLEVO read-only blok s `cz_before` - NIKDY se
nepřepisuje, zůstává na obrazovce po celou dobu jako trvalá reference
pro porovnání. VPRAVO editovatelné textové pole, výchozí obsah =
`styled` - `cz_before` i `styled` se do stránky natáhnou JEDNOU při
načtení (`GET /api/polish`) a drží se v paměti prohlížeče (data atribut/
JS proměnná u řádku), takže dvě pomocná tlačítka NAD editovatelným
polem ("vrať na originál" přepíše JEN pravé pole obsahem `cz_before`,
"vrať na Codex" JEN pravé pole obsahem `styled`) fungují opakovaně bez
ztráty possibility znovu se podívat na levý read-only blok.

Tlačítko "Uložit tuhle kapitolu" (AJAX POST `/api/polish/apply`, po
úspěchu řádek zmizí z "čeká na review" seznamu) a tlačítko "Zahodit"
(AJAX POST `/api/polish/discard` - odebere kapitolu z fronty bez zápisu
do DB, s potvrzovacím dialogem v prohlížeči, ať se nedá kliknout
omylem; viz "Zahodit NENÍ trvalé vyloučení" v sekci `discard` výš pro
přesný rozsah tlačítka). Konflikt (409 z apply/revert - kapitola se
mezitím změnila jinde) se zobrazí jako chybová hláška u řádku, řádek
ZŮSTANE ve frontě (uživatel může zkontrolovat aktuální stav a případně
kapitolu zahodit ručně). Samostatná sekce "Historie" - poslední
rozhodnuté kapitoly. Tlačítko "vrať zpět" se zobrazuje JEN u
NEJNOVĚJŠÍHO záznamu pro danou `idx` (kolo 6 IMPORTANT - dřív
nejednoznačné: `?idx=N` zobrazovalo VŠECHNY záznamy kapitoly každý s
vlastním tlačítkem, ale `POST /api/polish/revert` vždy vrací na stav
PŘED NEJNOVĚJŠÍM záznamem, bez ohledu na to, u kterého řádku se
kliklo - tlačítko u starší položky by tak dělalo něco jiného, než
naznačuje. Starší záznamy (v `?idx=N` pohledu i jinde) se zobrazují
JEN jako čtecí audit trail, bez tlačítka - "vrať zpět" odpovídá přesně
tomu, co endpoint umí: vrátit POSLEDNÍ krok, ne cestování v čase na
libovolnou starší verzi). Obsahuje-li SOUVISLÝ ŘETĚZEC (kolo 20 -
spočítaný STEJNÝM walk-back algoritmem jako `to: "original"` na
serveru, viz `revert` endpoint níž - NE prostý počet VŠECH záznamů pro
`idx`, protože historie může mít neregidně mezery od `answer`/`run`
epizod mimo tenhle workflow) ALESPOŇ 2 záznamy, vedle "vrať zpět"
(`to: "previous"`) se zobrazí i DRUHÉ tlačítko "vrať na PŮVODNÍ verzi"
(`to: "original"`, kolo 19 IMPORTANT - viz zdůvodnění u `revert`
endpointu výš: opakované "vrať zpět" by po dvou a víc skutečných
stylizacích JEDNÉ souvislé větve jen přepínalo mezi posledními dvěma
stavy, nikdy by se nedostalo k pravému originálu tý větve). Má-li
souvislý řetězec délku 1 (ať už je CELKOVÝ počet záznamů pro `idx`
jakýkoli), zobrazí se jen JEDNO tlačítko (obě varianty dělají totéž -
"originál" TÉHLE větve == "předchozí").

**Ani jedno tlačítko se nezobrazí, pokud by bylo no-op** (kolo 22
IMPORTANT - doplňuje server-side no-op ochranu výš): `GET /api/polish`
u KAŽDÉ kapitoly s historií spočítá, jestli `to: "previous"` cíl a/nebo
`to: "original"` cíl (STEJNÝ walk-back výpočet jako endpoint) odpovídá
AKTUÁLNÍMU `translated_text` v DB - pokud ano, odpovídající tlačítko se
v UI vůbec NEUKÁŽE (typicky nastane hned po revertu, kdy "vrať zpět"
by teď vracelo na text, co je STEJNÝ jako to, co se PRÁVĚ vrátilo).
Tohle je JEN pohodlí/prevence matoucího kliku - skutečná ochrana proti
no-op zápisu je server-side kontrola u endpointu, ne tahle UI logika
(kdyby se UI a server rozešly, endpoint pořád odmítne no-op zápis).

## Bezpečnost

`STYLIST_ACCEPT_FS_RISK` gate beze změny (pořád jediná/závazná brána v
`stylist.polish()`). NOVÝ důsledek k vědomému přijetí (uživatel to už
odsouhlasil v týhle konverzaci, zapsáno pro budoucí čtenáře specu): na
rozdíl od dnešního `polish-reports/*.json` (default redigovaný,
`STYLIST_REPORT_REJECTED_TEXT` opt-in), `polish.draft.json` a
`polish.history.json` **VŽDY** nesou plný Codexův text + nálezy, bez
ohledu na `STYLIST_REPORT_REJECTED_TEXT` - to je vlastní smysl týhle
featury (bez plného textu není co review). Oba soubory leží v `data/`
(uživatelova synchronizovaná složka) - stejné riziko šíření potenciálně
exfiltrovaného obsahu, jaké `STYLIST_REPORT_REJECTED_TEXT` u agregátního
reportu záměrně drží za samostatným opt-inem. Tady žádný samostatný
opt-in NENÍ - funkce je nepoužitelná bez plného textu, takže spuštění
`polish` (za `STYLIST_ACCEPT_FS_RISK`) implicitně znamená přijetí i
tohohle.

`polish.history.json` roste bez limitu (žádná rotace/mazání v tomhle
plánu) - jde o vědomý kompromis (jednoduchost) vs. neomezený růst
citlivého obsahu na disku; retence je na uživateli (ruční smazání staré
historie, ví, že tím přijde o možnost revertu starších kapitol).

## Testování (nástin, plán doupřesní)

- `_polish_one_chapter` vrací draft dict místo commitu - testy z
  `2026-09-08` specu (mock `stylist.polish`/kritik/konkordance) se
  přepíší na nové návratové tvary.
- `_cmd_polish`: preflight odmítne s nevyřízeným draftem; prázdný draft
  (nic k review) se nezapisuje; `polish.draft.json` obsahuje jen
  `drafted` kapitoly, ne `unchanged`/`failed`.
- `polish_server.py`: `GET /api/polish` tvar; `POST /api/polish/apply`
  zapíše PŘESNĚ zaslaný text (ne `styled`), zálohuje jen JEDNOU za běh
  serveru, přesune záznam draft→history; `POST /api/polish/revert`
  obnoví `cz_before` z posledního historického záznamu a připojí nový.
- Integrace: `polish` → `polish-review apply` → DB má text z pole, ne
  Codexův raw výstup, když se lišily.
- CAS konflikt: DB text pro `idx` se mezi draftem a apply/revert změní
  (simulovat přímým UPDATE v testovací DB) → endpoint vrátí 409, DB i oba
  JSON soubory zůstanou nezměněné.
- `apply`/`revert` přepočítají `term_mentions` nad aktuálním glosářem
  (ne nad tím, co platil při `polish`) - test se změněným glosářem mezi
  draftem a apply ověří, že `commit_chapter_result` dostane mentions
  odpovídající AKTUÁLNÍMU stavu.
- `rendered_terms` (kolo 18): apply i revert POUŽÍVAJÍ hodnotu z
  draftu/reverted entry, NEčtou ji znovu z `state.chapter_mentions` -
  test se dvěma navazujícími operacemi (apply → revert), kde DB mezi
  nimi obsahuje OKLESANOU sadu mentions, ověří, že revert i tak obnoví
  PŮVODNÍ rendered-only mention ve `styled`/`cz_before` textu.
- `discard`: odebere `idx` z draftu, nesahá na DB/historii; no-op pro
  neexistující `idx` vrací 200.
- `init --reset` (kolo 9-10 - opraveno, dřív popisovalo mazání draftu):
  přejmenuje OBA existující soubory (`polish.draft.json`,
  `polish.history.json`) na timestampované kopie - NIC se nemaže; testy
  selhání DRUHÉHO přejmenování (ověří, že se PRVNÍ vrátí zpět) I selhání
  následného `state.reset_book` (ověří, že se OBĚ přejmenování vrátí
  zpět) - v obou případech DB zůstane nedotčená a soubory na disku
  přesně tak, jako by `init --reset` vůbec neproběhl.
- `polish-review` je v `_MUTATING` a drží `state.run_lock` po celou dobu
  běhu serveru (test: druhá instance/`run`/`answer` souběžně dostane
  `LockError`).
- `_cmd_polish` zapisuje `polish.draft.json` PO KAŽDÉ kapitole, ne až na
  konci (test: simulovat výjimku po první kapitole dávky se dvěma, ověřit,
  že soubor obsahuje první kapitolu).

## Vztah k `2026-09-08-stylist-agent-design.md`

Tenhle dokument NEPŘEPISUJE historii konsensu z 38 kol (co je stále
platné: bezpečnostní model kolem `codex exec`, strukturální kontrola,
tři kontrolní sítě, redakce). MĚNÍ jen jedno konkrétní rozhodnutí z tamní
sekce "Rozhodnutí" - "Granulární přijetí / opravná smyčka... ODLOŽENO za
v1" - na základě reálných dat z prvního ostrého běhu (přesně to, co v1
report subsystém měl umožnit změřit). Řešení tady NENÍ ta odložená
"opravná smyčka" (kritik nabídne opravu, systém ji aplikuje) - je to
jednodušší: člověk dostane editovatelné pole a nálezy jako kontext,
aplikaci dělá sám.
