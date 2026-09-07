# Těžba terminologie z profesionálních překladů - design

Datum: 2026-09-07
Stav: k oponentuře
Navazuje na: `2026-09-06-book-translator-design.md`

## Kontext a cíl

Turn Coat je jedenáctý díl Dresden Files. Prvních deset dílů vyšlo česky
v profesionálním překladu. Čtenář, který je přečetl, zná zavedenou terminologii
a jména; překlad jedenáctky, který si vymyslí vlastní, je pro něj horší, i kdyby
byl sám o sobě dobrý. **Návaznost na zavedenou terminologii je hlavní důvod,
proč tenhle nástroj vzniká.**

Scout po `scan` navrhl 121 povrchů (54 postav, 59 termínů, 19 míst - po odečtení
víceznačných). Bez referencí je na všech odpovídá člověk ručně nebo se hádá.
S referencemi je většina dohledatelná v textu, který už existuje.

**Cíl:** před fází `review` předvyplnit návod tím, co je doložitelné
z profesionálních překladů, a u každé položky ukázat důkaz.

**Nesmí se stát:** aby se do glosáře dostal termín, který si model vymyslel
a v žádném českém textu není. Model smí navrhovat, rozhoduje korpus.

## Zdrojová data

`<Reference>/EN/*.epub` a `<Reference>/CZ/*.epub`, deset dílů, párované číslem
dílu v názvu souboru. Ověřeno: všech 20 souborů se načte stávajícím
`ingest.load_book`; EN korpus ~1 200 000 slov, CZ ~972 000 slov.

**Kapitoly na sebe nesedí** (díl 1: EN 27 dokumentů, CZ 5; díl 2: EN 1 dokument).
Je to rozdíl ve vnitřním členění EPUBů, ne v obsahu. Návrh proto na zarovnání
kapitol nespoléhá; pracuje s knihou jako s jedním textem.

## Rozsah

### V rozsahu
- Načtení referenčního korpusu (EN i CZ) přes stávající `ingest`, párování dílů
- Deterministické zjištění, které anglické povrchy překladatelé ponechali
- Návrh českých tvarů modelem s **povinným ověřením proti korpusu**
- Zápis do `guide.draft.json` včetně důkazu u každé položky
- Souhrnný report do `data/reference_report.md`
- Seskupení položek v review UI podle síly důkazu

### Mimo rozsah
- Poziční zarovnání textů (stupeň 2) - návrh nechává čisté místo, nestaví to
- Automatické psaní do glosáře mimo obvyklou cestu přes `review`
- Těžba stylu, vypravěčského hlasu nebo vztahů (tyká/vyká) z referencí
- Použití referencí za běhu `run` (překladatel dostává glosář, ne korpus)

## Zásadní rozhodnutí

### 1. Nic neobchází review

Původní varianta zapisovala silné nálezy rovnou do glosáře jako `approved`.
Zamítnuto: schovalo by to před člověkem právě ta rozhodnutí, která se protáhnou
celou knihou, a zavedlo by druhou cestu zápisu do glosáře.

**Zvoleno:** `reference` čte a zapisuje **jen `guide.draft.json`**. Na databázi
nesahá vůbec. Glosář se plní beze změny stávající cestou `review` → `guide.json`
→ `glossary.seed_from_guide`. O jednu cestu k datům a o jedno riziko
nekonzistence míň.

Síla důkazu tedy neurčuje, co člověka obejde (nic ho neobchází), ale jak je
položka v UI zvýrazněná a jak pečlivě si ji má projít.

### 2. Model navrhuje, korpus rozhoduje

Model dostane seznam anglických termínů a vrátí návrh českého tvaru. Návrh sám
o sobě nemá váhu - vždy se spočítá, kolikrát a v kolika dílech se navržený tvar
v CZ korpusu opravdu vyskytuje. Neověřený návrh se **nezahazuje**, ale putuje do
UI viditelně označený jako nepodložený.

Důvod: model si terminologii pamatovat může, ale i nemusí, a vymyšlený termín
vypadá stejně sebejistě jako správný. Korpus je levný a nelže.

### 3. Falešné shody u obecných slov

Pokus ukázal konkrétní past: hledání `stole` bez ohledu na velikost písmen
našlo 79 výskytů v 10/10 dílech - jenže to je český lokativ slova *stůl*
(*na stole*), ne ponechaný anglický termín.

**Pravidlo:** povrch začínající velkým písmenem (vlastní jméno) se hledá
case-insensitive. Povrch začínající malým písmenem (obecné slovo, např.
`warlock`, `threshold`) se hledá **case-sensitive** a musí mít alespoň 4 znaky.
Jednoznakové a dvouznakové povrchy se nehledají vůbec.

## Stupně řešení

Pouštějí se v pořadí, každý pracuje jen s tím, co předchozí nevyřešil.

**Stupeň 0 - ponecháno anglicky (zdarma, bez API).**
Anglický povrch se hledá v CZ korpusu podle pravidel z rozhodnutí 3. Nalezen
dostatečně často → překladatelé ho ponechali → `cz = anglický povrch`,
u postav `render = keep`.

**Stupeň 1 - návrh modelem + ověření (~$0.10-0.20).**
Nevyřešené povrchy jdou po dávkách (~30) agentovi `lexicographer`. Vrátí
`{term_en, cz}`. Každý návrh se ověří v CZ korpusu. Ověřený → předvyplní se
s důkazem; neověřený → předvyplní se s příznakem `unverified`.

**Stupeň 2 - poziční zarovnání (nestaví se).**
Až se ukáže, že stupeň 1 nestačí. Návrh drží seam: `reference_mine.resolve()`
bere seznam nevyřešených povrchů a vrací nálezy, takže další stupeň je další
funkce se stejným tvarem vstupu a výstupu.

## Klasifikace nálezu

| Třída | Podmínka | Chování v UI |
|---|---|---|
| `confirmed` | ≥ `REFERENCE_MIN_HITS` výskytů ve ≥ `REFERENCE_MIN_BOOKS` dílech | vyplněno, sbaleno |
| `weak` | nalezeno, ale pod prahem | vyplněno, rozbaleno, s důkazem |
| `unverified` | model navrhl, korpus nepotvrdil | vyplněno, zvýrazněno jinou barvou |
| `unresolved` | ani model nenavrhl | prázdné, jako dosud |

Výchozí prahy v `config.py`: `REFERENCE_MIN_HITS = 5`, `REFERENCE_MIN_BOOKS = 2`.
Prahy neurčují, co obejde člověka - jen míru zvýraznění.

## Moduly a hranice

| Modul | Zná | Nezná |
|---|---|---|
| `src/reference.py` | EPUBy přes `ingest`, počítání výskytů v textu | LLM, DB, `guide` |
| `src/agents/lexicographer.py` | prompt → klient → parsování | korpus, DB, soubory |
| `src/reference_mine.py` | drátuje korpus + agenta + draft | DB |
| `main.py` (`reference`) | parsuj, zavolej, vypiš | vše ostatní |

Hranice odpovídají zbytku projektu: agent je bezstavová funkce, korpus je čistá
logika nad textem, orchestrace je jedno místo.

### `src/reference.py`
- `Corpus` = `dataclass(cz: dict[int, str], en: dict[int, str])` - text celého
  dílu jako jeden řetězec, klíč = číslo dílu
- `load_corpus(root: str) -> Corpus` - najde `EN/` a `CZ/`, spáruje podle čísla
  v názvu souboru (`^(\d+)` u CZ, `#(\d+)` nebo `Book (\d+)` u EN). Nespárované
  soubory přeskočí a nahlásí.
- `save_cache(corpus, path)` / `load_cache(path) -> Corpus | None` - načtení
  20 EPUBů trvá ~30 s, cache do `data/reference_corpus.json`
- `count(corpus, surface, side="cz") -> Evidence` -
  `Evidence = dataclass(hits: int, books: list[int])`, respektuje pravidlo
  o velikosti písmen z rozhodnutí 3

### `src/agents/lexicographer.py`
- `SYSTEM_PROMPT` - "jsi znalec české edice této série, vrať zavedené české
  tvary; když termín neznáš, vrať null, nehádej"
- `propose(terms: list[dict], client, *, model, max_tokens) -> list[dict]` -
  vstup `{term_en, type, note}`, výstup `{term_en, cz | None}`. Neparsovatelný
  výstup → `ValueError` (volající dávku přeskočí, běh nekončí)

### `src/reference_mine.py`
- `resolve(corpus, surfaces: list[dict], client_factory, cfg) -> list[Finding]`
  kde `Finding = {surface, kind, cz, klasifikace, hits, books, source}`,
  `source ∈ {kept, proposed}`
- `apply_to_draft(draft: dict, findings: list) -> dict` - předvyplní `cz`
  (u postav i `render`), do `note` připíše důkaz, přidá `reference` blok
  s klasifikací pro UI
- `write_report(findings, path)` - `data/reference_report.md`

## Chyby

Těžba je **volitelný krok**, ne podmínka běhu. Klasifikace se tomu podřizuje:

| Situace | Reakce |
|---|---|
| chybí složka referencí / prázdná | `FatalRunError`, exit 1, draft beze změny |
| jednotlivý EPUB se nenačte | přeskoč, nahlas, pokračuj s ostatními |
| nespárovaný díl (chybí EN nebo CZ) | přeskoč, nahlas |
| dávka termínů selže (rozbitý JSON) | přeskoč dávku, nahlas, pokračuj další |
| `FatalRunError` z klienta (auth, cost guard) | ukonči příkaz, draft beze změny |

Draft se zapisuje **až na konci**, jedním atomickým zápisem (`guide.save_draft`
už dělá temp + `os.replace`). Pád uprostřed nenechá napůl obohacený návod.

Stávající draft se nepřepisuje ztrátově: `apply_to_draft` doplňuje `cz` jen tam,
kde je prázdné, a `note` rozšiřuje, nenahrazuje.

## Review UI

`GET /api/guide` vrací navíc u položek blok `reference`
(`{klasifikace, hits, books, source}`). Formulář podle něj:

- sekce **Potvrzeno referencemi** nahoře, sbalená, s počtem položek
- `weak` a `unverified` rozbalené, `unverified` odlišené barvou
- u každé položky řádek důkazu: „12× v dílech 3, 5, 7"
- pole zůstávají editovatelná - ruka člověka vyhrává nad referencemi vždy

Validace se nemění. Chybějící blok `reference` (draft bez těžby) UI nesmí
rozbít - sekce se pak prostě nezobrazí.

## CLI

```
python main.py reference [--dir CESTA] [--refresh-cache]
```

Mutující příkaz (drží zámek, lifecycle `create_run` / `finish_run` jako `scan`),
`interactive=False` u cost guardu - je to dávková operace bez dohledu.
Výchozí cesta v `config.py` (`REFERENCE_DIR`). Pouští se mezi `scan` a `review`;
`scan` musí proběhnout dřív, jinak není co obohacovat (chybí draft → chyba
s vysvětlením).

## Testy

1. **Korpus (bez API):** párování dílů podle názvu, přeskočení nespárovaných,
   case-sensitive pravidlo (`stole` se jako termín nenajde, `Mab` ano),
   minimální délka, cache round-trip.
2. **Agent (fake klient):** sestavení dávky, parsování odpovědi, `null` jako
   „neznám", rozbitá dávka → `ValueError`.
3. **Orchestrace (fake klient, mini korpus):** klasifikace do čtyř tříd,
   neověřený návrh se nezahodí ale označí, prázdné `cz` se doplní a neprázdné
   ne, report se zapíše.
4. **UI:** draft s blokem `reference` i bez něj, oba se vykreslí; POST validace
   se nemění.

## Otevřené otázky k ověření prvním během

- Kolik ze 121 povrchů vyřeší stupeň 0 a kolik stupeň 1?
- Jak často model navrhne tvar, který korpus nepotvrdí? (Vysoké číslo = model
  českou edici nezná a stupeň 2 bude nutný.)
- Sedí prahy 5 výskytů / 2 díly, nebo je většina nálezů těsně pod nimi?
- Jsou falešné shody i jinde než u obecných slov s malým písmenem?
