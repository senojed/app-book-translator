# Ruční review stylistického průchodu - design

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

Cíl: **žádná kapitola se nezapíše do DB bez lidského schválení.** Uživatel
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
- `STYLIST_REPORT_REJECTED_TEXT`/`polish-reports/*.json` (agregátní
  metrika reject rate) - zůstává BEZE ZMĚNY jako doplňkový nástroj vedle
  tohohle workflow, ne jeho součást.

## Architektura

Tři kroky místo dnešního jednoho:

```
python main.py polish           # Codex + kontroly, ŽÁDNÝ zápis do DB
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
      "findings": [ /* VŽDY plné - concordance + critic + meaning-check nálezy */ ]
    }
  ]
}
```

**Preflight `polish`:** pokud `data/polish.draft.json` existuje a NENÍ
prázdný, `_cmd_polish` odmítne běžet ("N kapitol čeká na review, spusť
`python main.py polish-review` nejdřív") - žádné tiché přepsání/sloučení
nevyřízené dávky.

### `data/polish.history.json`

Append-only archiv VŠECH už rozhodnutých kapitol (od tohohle workflow dál -
historii nemá zpětně, jen co vznikne od teď). Slouží jako podklad pro
per-kapitolové "vrať zpět", ne jako duplicitní DB.

```json
{
  "entries": [
    {
      "idx": 1,
      "applied_at": "2026-09-11T22:05:00+02:00",
      "cz_before": "...",
      "cz_after": "...",
      "styled_by_codex": "...",
      "findings": [ /* nálezy platné v době rozhodnutí */ ],
      "source": "polish-review" | "revert"
    }
  ]
}
```

**Revert:** review UI u archivovaných kapitol nabídne "vrať na verzi před
stylizací" - najde POSLEDNÍ (nejnovější) záznam pro dané `idx`, jeho
`cz_before` zapíše jako nový `translated_text`, a připojí NOVÝ záznam do
historie (`source: "revert"`, `cz_before` = to, co se právě vrátilo,
`cz_after` = obnovený text). Díky tomu je revert sám o sobě odvolatelný
(klikni "vrať zpět" znovu = vrátí revert).

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
`reason_types`, `findings`) nebo `{"outcome": "unchanged"}` /
`{"outcome": "failed", "error": ...}` (ty dvě varianty stejné jako dnes,
jen nejdou do `polish.draft.json`, jen do `polish-reports/*.json`).

### `_cmd_polish` (refaktor)

Stejný preflight (FS-risk gate, model, `_resolve_codex_cmd`) + NOVÝ
preflight (nevyřízený draft = odmítni). Loop přes `chapters_by_status(db,
("done",))` (`--only`/`--force`... `--force` teď znamená "i kapitoly, co
mají v `notes` marker z dřívějšího PŘIJETÍ tímhle workflow" - stejná
sémantika jako dnes). Sbírá draft záznamy, na konci zapíše
`polish.draft.json` (přeskočí zápis, když je prázdný - žádné "nic ke
kontrole" soubory). `polish-reports/*.json` metrika (agregátní počty)
zůstává BEZE ZMĚNY - pořád užitečná i bez auto-commitu (kolik kapitol vůbec
prošlo strukturální kontrolou a mělo by smysl review).

**Záloha DB** (`_snapshot_db`/`_backup_db_once`) se z `_cmd_polish`
ODSTRAŇUJE - `polish` už nezapisuje nic do `chapters`, není co zálohovat
kvůli tomuhle kroku. Přesouvá se do `polish-review` apply endpointu (viz
níž) - PŘESNĚ TAM, kde teď skutečný zápis vzniká.

### `polish-review` (nový příkaz + `src/review_ui/polish_server.py`)

FastAPI + uvicorn, stejný vzor jako `src/review_ui/server.py` (`review`).
Na rozdíl od `review` (jedno uložení = konec) tenhle server běží, dokud ho
uživatel nezavře - může rozhodnout jen NĚKTERÉ kapitoly a zbytek nechat na
příště (zůstanou v `polish.draft.json`).

- `GET /api/polish` - vrátí obsah `polish.draft.json` (pending) +
  posledních N záznamů `polish.history.json` (pro revert sekci).
- `POST /api/polish/apply` - payload `{"idx": 1, "text": "..."}` (JEDNA
  kapitola, uloženo přes AJAX při kliknutí - ne jedno velké odeslání na
  konci, ať se needitovaná práce neztratí při zavření okna/pádu
  prohlížeče). Server: `_backup_db_once` (zálohuje CELOU DB, jen JEDNOU
  za běh serveru, před PRVNÍM zápisem - stejný mechanismus/zdůvodnění jako
  dnešní `_backup_db_once`, jen volaný odsud), `state.commit_chapter_result`
  s `translated_text=text` (přesně to, co bylo v textovém poli - ne
  `styled`, ne `cz_before`, cokoli uživatel uložil), `notes_json` = nálezy
  + marker (marker teď hashuje/měří `text`, ne Codexův raw `styled` -
  audit odráží, co SKUTEČNĚ do knihy šlo). Po úspěchu: odeber `idx` z
  `polish.draft.json`, připoj záznam do `polish.history.json`
  (`cz_before`=originál z draftu, `cz_after`=`text`, `styled_by_codex`=
  Codexův raw návrh, `source="polish-review"`).
- `POST /api/polish/revert` - payload `{"idx": 1}`. Najde poslední
  `polish.history.json` záznam pro `idx`, zapíše jeho `cz_before` jako nový
  `translated_text` (`_backup_db_once` + `commit_chapter_result` stejně
  jako výš), připojí nový historický záznam (`source="revert"`).
- Žádný "uložením končí" protokol jako `review` - `polish-review` se
  ukončí jen zavřením okna/Ctrl-C, návratový kód vždy 0 (žádný CLI krok po
  něm nezávisí na tom, jestli něco bylo rozhodnuto).

### UI (`src/review_ui/static/polish.html`, nová)

Tabulka: kapitola (idx, title), nálezy (seznam, JEN k přečtení - typ,
závažnost, popis), textové pole (výchozí obsah = `styled`), dvě pomocná
tlačítka NAD polem ("vrať na originál" vyplní `cz_before`, "vrať na Codex"
vyplní `styled` zpátky - obojí jen mění obsah pole, nic neukládá), tlačítko
"Uložit tuhle kapitolu" (AJAX POST `/api/polish/apply`, po úspěchu řádek
zmizí z "čeká na review" seznamu). Samostatná sekce "Historie" - poslední
rozhodnuté kapitoly, u každé tlačítko "vrať zpět" (`/api/polish/revert`).

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
