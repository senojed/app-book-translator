# Těžba terminologie z profesionálních překladů - design

Datum: 2026-09-07
Stav: po kole 11 oponentury (fresh-eyes review + zjednodušení)
Navazuje na: `2026-09-06-book-translator-design.md`

## Kontext a cíl

Turn Coat je jedenáctý díl Dresden Files. Prvních deset dílů vyšlo česky
v profesionálním překladu. Čtenář, který je přečetl, zná zavedenou terminologii;
překlad jedenáctky, který si vymyslí vlastní, je pro něj horší, i kdyby byl sám
o sobě dobrý. **Návaznost na zavedenou terminologii je hlavní důvod, proč tenhle
nástroj vzniká.**

**Cíl:** před fází `review` předvyplnit návod tím, co je **doložitelné**
z profesionálních překladů, a u každé položky ukázat důkaz.

**Invariant:** žádná hodnota, kterou navrhl model a korpus ji nedoložil, se
**nepředvyplní automaticky**. Člověk může ručně napsat cokoli - to je jeho
právo a nástroj mu v tom nebrání; jen mu nic nepodstrčí.

## Zdrojová data

`<Reference>/EN/*.epub` a `<Reference>/CZ/*.epub`, deset dílů, párované číslem
dílu v názvu souboru. Ověřeno: všech 20 souborů se načte stávajícím
`ingest.load_book`; EN korpus ~1 200 000 slov, CZ ~972 000 slov. Vnitřní členění
EPUBů se mezi jazyky liší, takže **kapitoly na sebe nesedí**; pracuje se s dílem
jako s jedním textem.

## Krok 0: normalizace draftu (jednorázově, před těžbou)

Draft od scouta má vadná data, která se ukázala až při návrhu těžby:

| Vada | Počet | Příklad |
|---|---|---|
| výčty místo jednoho povrchu | 11 | `White Court / Red Court / Vampire Courts` |
| duplicitní entity | 15 | `Morgan` i `Donald Morgan`, `Thomas` i `Thomas Raith` |

Dřívější verze specu kolem těchto vad stavěla tři podsystémy: editor složených
položek ve formuláři, přemapování `must_decide` a validaci kolizí při ukládání.
To je nepřiměřené - **levnější je odstranit příčinu než obsluhovat následek**.
Navíc se ukázalo, že validace kolizí by formulář rovnou zablokovala: reálný
draft má 15 kolizí a UI nemá na kanonická jména editaci ani mazání.

**Zvoleno:** samostatný jednorázový krok, výsledkem je opravený
`guide.draft.json`. Není to součást těžby a nespouští se opakovaně.

- pomocný skript vypíše kandidáty na sloučení (kanonické jméno jedné položky je
  aliasem jiné) a výčty rozdělené podle `/` a `" or "` (normalizovaně,
  bez ohledu na velikost písmen a mezery)
- **rozhoduje člověk**, skript nic nemění sám
- sloučení: zůstane delší kanonický tvar, aliasy se sjednotí, poznámky spojí
- výčet: rozdělí se na samostatné položky, `suggested_cz` se rozdělí týmž
  oddělovačem a spáruje pozičně, nesedí-li počty, zůstane prázdné
- `must_decide` se složeným `scope_key` (v draftu dvě:
  `naagloshii/skinwalker`, `Shagnasty/skinwalker`) se přepíše na zvolenou
  variantu ručně
- výsledek se uloží jako nový `guide.draft.json`, původní se zazálohuje

Prompt scouta se zároveň opravuje (jedna položka = jeden povrch, synonyma do
`aliases`), aby další knihy tenhle krok nepotřebovaly.

**Po tomto kroku platí:** každá položka draftu je jeden povrch a žádné kanonické
jméno není aliasem jiné položky. Těžba, formulář ani glosář pak nemusí řešit
výčty, kolize ani přemapování otázek.

## Stupně řešení

Pouštějí se v pořadí a **každý pracuje jen s tím, co předchozí nevyřešil**:

| Stupeň | Co dělá | Cena |
|---|---|---|
| 0 | přesné hledání anglického povrchu v CZ textu | zdarma, bez API |
| 1 | návrh modelem + ověření v korpusu | ~$0.15, počáteční odhad, neměřeno |
| 2 | poziční zarovnání textů | nestaví se |

Do stupně 1 jde jen to, co stupeň 0 nedoložil **jako přímý důkaz ponechání**
(pozor: obecné slovo doložené stupněm 0 zůstává způsobilé - viz rozhodnutí 3).

Stupeň 2 se nestaví, ale `resolve()` bere seznam nevyřešených povrchů a vrací
nálezy, takže další stupeň je další funkce se stejným tvarem vstupu i výstupu.

## Zásadní rozhodnutí

### 1. Výsledek těžby žije ve vlastním souboru

`main.py:105` volá `save_draft(GUIDE_DRAFT_PATH, result)` a přepíše draft
**celý**, takže opakovaný `scan` by těžbu v draftu tiše smazal.

Těžba proto zapisuje `data/reference.json`. Podklad pro UI vzniká slitím tří
zdrojů: `guide.json` (člověk) > `reference.json` (těžba) > `guide.draft.json`.

### 2. Nic neobchází review a neověřené se nepředvyplňuje

`reference` needituje glosář; ten se plní beze změny cestou `review` →
`guide.json` → `glossary.seed_from_guide`.

Zvýraznění barvou nestačí: validace kontroluje jen neprázdnost pole, takže
vyplněná vymyšlenina by se uložením dostala do glosáře.

- U `proposed` a `not_attested` zůstává `cz` **prázdné**; návrh se ukazuje jen
  jako text vedle pole.
- **U postav to nestačí.** Validace dovoluje prázdné `cz` při `render == keep`,
  UI má `keep` jako výchozí (`index.html:111`) a `seed_from_guide` pak vloží
  anglické jméno. Proto se u postav bez doloženého primárního tvaru `render`
  nepředvyplňuje, roletka má prázdnou volbu `-- vyber --` a validace neprojde
  bez aktivní volby. Testuje se **serializovaný payload**, ne vzhled.

### 3. Stupeň 0: co je a co není důkaz ponechání

Past ověřená měřením: `stole` má v referencích 79 výskytů v 10/10 dílech - je to
ale český lokativ slova *stůl*, ne ponechaný termín. `stole` v draftu scouta
skutečně je (ve významu „štóla").

**Pravidla:**
- **velké počáteční písmeno** (vlastní jméno): hledá se case-insensitive, ale
  **`confirmed` vyžaduje alespoň jeden výskyt shodný i ve velikosti písmen**.
  Bez toho by anglický povrch mohl „potvrdit" nesouvisející české slovo.
- **malé počáteční písmeno** (obecné slovo): shoda je **jen důkaz pro člověka**,
  nikdy `confirmed`, **`cz` se nepředvyplňuje** a položka **zůstává způsobilá
  pro stupeň 1**. Dřívější verze ji označila za `weak`, předvyplnila a ze
  stupně 1 vyřadila - tedy nejhorší možná kombinace.
- 1-2 znaky se nehledají vůbec
- povrch kratší než 5 znaků musí mít výskyt **mimo začátek věty** (chrání před
  jmény, která jsou zároveň českými slovy). Začátek věty = pozice 0 dokumentu,
  první nebílý znak po `.`/`!`/`?`/`…` s bílým znakem, nebo znak po oddělovači
  dokumentů (`\n\x00\n`).
- dotaz escapován (`re.escape`), hranice slova přes `(?<!\w)` / `(?!\w)`
  s `re.UNICODE`, aby pomlčka a apostrof zůstaly součástí dotazu
  (`Listens-to-Wind`, `Za-Lord`)

**Aliasy:** hledá se primární povrch i každý alias, důkaz se vede po
jednotlivých tvarech. Výskyty jsou **sjednocení rozsahů**, ne součet
(`Dresden` uvnitř `Harry Dresden` se nesmí započítat dvakrát). Prahy pro
`confirmed` se počítají **výhradně z primárního tvaru**; doložený jen alias →
`primary_attested = false`, **žádné předvyplnění**, jen zobrazený důkaz.
Výskyt `Dresden` nedokládá tvar `Harry Dresden` - překlad může příjmení
ponechat a křestní jméno počeštit.

### 4. Stupeň 1: model navrhuje, korpus omezuje, nic se nepředvyplňuje

`confirmed` smí vzniknout **jen ze stupně 0**. Globální výskyt navrženého
českého tvaru důkazem vazby není: `Rada` je běžné české slovo.

**Doložení navrženého tvaru = přesná shoda celého slova** (case-insensitive,
tytéž hranice slova jako ve stupni 0). Skloňování se **netoleruje** a je to
vědomé rozhodnutí: stupeň 1 nikdy nic nepředvyplňuje, takže tolerance
skloňování kupuje málo, zatímco stojí morfologii, kterou tři pokusy nedokázaly
napsat správně (`max(4, len-2)` nenašel `bílá`/`bílé`; `max(3, len-2)` dal
u `práh` 54 tvarů včetně `práce` a `právo`; varianta s koncovkami propadla na
`plášť`/`pláště`). `not_attested` proto znamená **„v tomto přesném tvaru
nedoloženo"** a je to výslovně **slabý** signál.

**Predikát souvýskytu.** `E` = spárované díly, kde je anglický povrch (nebo
alias) na **EN** straně; `C` = díly, kde je navržený český tvar na CZ straně.

```
proposed  <=>  |E| > 0  a  |E ∩ C| >= max(1, ceil(REFERENCE_COOCCUR_RATIO * |E|))
```

Jinak `not_attested`. Prázdné `E` (termín je nový až v jedenáctce) →
`not_attested`.

`books_with_en(corpus, surfaces)` používá **stejná pravidla jako stupeň 0, ale
na EN straně**: case-insensitive, tytéž hranice slova, **bez** pravidla
o začátku věty (anglický text, nehrozí kolize s českým slovem) a bez délkových
omezení nad 2 znaky.

### 5. Identita při kolizi povrchu s aliasem

`glossary._seed_one` páruje nový povrch i přes **aliasy** existujícího řádku
a pak přepíše `canonical_en`, `cz` i `type`. Je to latentní chyba stávajícího
kódu; normalizace draftu (krok 0) odstraní 15 kolizí, které by ji spouštěly,
ale guard zůstává jako pojistka pro data, která do `guide.json` doputují jinudy.

**Guard:** řádek nalezený **jen přes alias** se nesmí přepsat, liší-li se
příchozí `canonical_en`. `seed_from_guide` vrací **seznam konfliktů**
(`[{incoming, existing_term_id, existing_canonical}]`), který CLI vypíše;
nic se přitom nepřepíše. Dnes funkce nevrací nic, což by „nahlášení konfliktu"
znemožnilo.

Ve formuláři se kolize řeší jen **varováním**, ne blokujícím chybou. Reálný
draft jich má 15 a UI nemá na kanonická jména editaci ani mazání - blokující
validace by znemožnila uložit cokoli.

## Klasifikace nálezu

| Třída | Vzniká z | Podmínka | Předvyplní `cz` | UI |
|---|---|---|---|---|
| `confirmed` | stupeň 0 | primární povrch doložen včetně shody velikosti písmen, >= `MIN_HITS` výskytů ve >= `MIN_BOOKS` dílech, velké počáteční písmeno, >= 3 znaky | ano | sbaleno |
| `weak` | stupeň 0 | primární povrch doložen, ale pod prahem | ano | rozbaleno s důkazem |
| `evidence_only` | stupeň 0 | doložen jen alias, nebo obecné slovo s malým písmenem | **ne** | důkaz zobrazen, položka jde do stupně 1 |
| `proposed` | stupeň 1 | model navrhl, tvar přesně doložen, souvýskyt sedí | **ne** | návrh vedle prázdného pole |
| `not_attested` | stupeň 1 | model navrhl, tvar v tomto tvaru nedoložen nebo souvýskyt nesedí | **ne** | návrh vedle pole, označený jako slabý signál |
| `unresolved` | - | model nenavrhl nic, nebo povrch pod 3 znaky | ne | prázdné |

Prahy jsou **počáteční odhady bez měření**; první běh je má potvrdit nebo
posunout. Práh rozhoduje jen o rozdílu `confirmed` / `weak`.

## Selhání je atomické

Dřívější verze měla `stale` příznak, čtyři stavy `coverage`, obnovu nálezů po
položkách a `--limit`. Na 132 položek a ~$0.15 za celý běh je to nepřiměřené.

**Zvoleno:** selže-li cokoli (rozbitá dávka, síťová chyba, neúplná odpověď),
**předchozí `reference.json` zůstane nedotčený**, CLI vypíše co selhalo a běh
se prostě spustí znovu. Žádné míchání starých a nových nálezů, žádné
`--limit`, žádný stavový automat.

Výjimka: `FatalRunError` (auth, cost guard) ukončí příkaz stejně.

## Moduly a hranice

| Modul | Zná | Nezná |
|---|---|---|
| `src/textnorm.py` | normalizace řetězce (bez závislostí) | vše ostatní |
| `src/reference.py` | EPUBy přes `ingest`, hledání, `textnorm` | LLM, DB, `guide`, `concordance` |
| `src/agents/lexicographer.py` | prompt → klient → parsování | korpus, DB, soubory |
| `src/reference_mine.py` | drátuje korpus + agenta + `reference.json` | DB, glosář |
| `src/guide.py` (rozšíření) | slití tří zdrojů pro UI | LLM, korpus |
| `main.py` (`reference`) | parsuj, zavolej, vypiš | vše ostatní |

`concordance` zůstává **beze změny** a `reference.py` ho nepoužívá:
`form_key("Bílá rada") == form_key("Bída rana")` a `Za-Lord` nenajde ani v textu,
kde stojí doslova (tokenizace `\w+` ho rozseká na pomlčce). Pro drift v jedné
kapitole to stačí, pro doložení v milionovém korpusu ne.

`textnorm.normalize_key()` (NFC, `casefold`, zúžení bílých znaků) slouží
**jen k identitě položek, nikdy k hledání** - casefold by velikost písmen
zahodil. Hledá se v surovém textu po NFC. `guide.normalize()`
(`strip().lower()`) zůstává beze změny kvůli `relationship_key`.

### `src/reference.py`

```python
@dataclass
class Evidence:
    hits: int              # sjednocení rozsahů
    books: list[int]
    per_form: dict         # {tvar: {"hits": int, "books": list[int],
                           #         "case_exact": bool}}
    matched_forms: list[str]   # tvary, které zabraly (může jich být víc)

@dataclass
class Corpus:
    cz: dict[int, str]
    en: dict[int, str]
    manifest: dict         # {relativní cesta: [velikost, mtime]}
    source_root: str
```

- `load_corpus(root) -> Corpus` - páruje podle čísla (`^(\d+)` u CZ, `#(\d+)`
  nebo `Book (\d+)` u EN). Duplicitní číslo dílu na téže straně → `ValueError`.
  **Selže-li jedna strana dvojice, vypadne celý díl** (obě strany), a teprve
  potom se kontroluje minimum `REFERENCE_MIN_CORPUS_BOOKS` (3); pod ním
  `ValueError`.
- `count_en_surface(corpus, surface, side="cz") -> Evidence`
- `count_cz_form(corpus, form) -> Evidence` - přesná shoda celého slova
- `books_with_en(corpus, surfaces) -> set[int]` - viz rozhodnutí 4
- `build_manifest(root) -> dict` - jen `os.stat`, EPUBy se neparsují
- `save_cache` / `load_cache(path, root)` - nese `schema_version`,
  `source_root` a manifest; neshoda → staví se znovu

### `src/agents/lexicographer.py`

- `SYSTEM_PROMPT` - „jsi znalec české edice této série; vrať zavedený český tvar;
  **když termín neznáš, vrať null - nehádej**".
- `propose(items, client, *, model, max_tokens) -> dict[str, str | None]` -
  vstup `[{id, term_en, kind, note}]`, výstup mapa `id -> cz | None`.
- **Identita je `id = "{section}/{normalize_key(klíč)}"`**; stejné jméno může
  být v `places` i `terms`.
- **Obálka odpovědi je objekt:** `{"proposals": [{"id": ..., "cz": ...}]}`;
  `parsing.extract_json` umí vytáhnout jen objekt, ne seznam.
- **Validace:** duplicitní `id` → `ValueError`; cizí `id` se ignoruje a nahlásí;
  `cz` musí být `str` nebo `null`; **chybějící `id` v jinak platné odpovědi →
  `ValueError`** (model položku vynechal, výsledek je neúplný a běh selže
  atomicky - viz Selhání).
- **Chyby:** `OutputTruncated` → jeden pokus s dvojnásobným `max_tokens`.
  Poté, stejně jako u neparsovatelné odpovědi, `ValueError` z validace
  a síťových či limitních výjimek (`APIConnectionError`, `RateLimitError`,
  5xx po vyčerpání SDK retry) → **běh selže atomicky**. Jen `FatalRunError`
  se propaguje jako fatální.

### `src/reference_mine.py`

```python
Finding = TypedDict("Finding", {
    "id": str,
    "section": str,            # characters | places | terms
    "surface": str,
    "cz": str | None,
    "classification": str,     # confirmed | weak | evidence_only
                               #   | proposed | not_attested | unresolved
    "primary_attested": bool,
    "navrh": str | None,
    "hits": int,
    "books": list[int],
    "per_form": dict,
    "cooccurrence": list[int],
    "matched_forms": list[str],
    "matched_cz": str | None,
    "source": str,             # kept | proposed
})
```

- `resolve(corpus, surfaces, client_factory, cfg) -> list[Finding]`
- `write_reference(findings, path, run_id, fingerprint, source_root)` - atomicky
  (temp + `os.replace`), **nahrazuje soubor celý**. Žádné slévání s předchozím -
  selhání je atomické, takže se sem dostane jen kompletní výsledek.

### Schéma `data/reference.json`

```json
{
  "schema_version": 1,
  "run_id": 7,
  "source_root": "C:/.../Turn Coat/Reference",
  "fingerprint": {
    "draft": "sha1 klíčů, aliasů a poznámek z guide.draft.json",
    "corpus": "sha1 manifestu",
    "thresholds": "sha1 hodnot MIN_HITS, MIN_BOOKS, MIN_CORPUS_BOOKS, COOCCUR_RATIO"
  },
  "findings": [ { "...Finding..." } ]
}
```

Otisk draftu zahrnuje i **poznámky**, protože se posílají lexikografovi a mění
jeho návrh. Otisk prahů jen z hodnot, které ovlivňují důkaz - ne z cest, modelu
ani velikosti dávky. `source_root` je **skutečně použitý kořen**, ne hodnota
z konfigurace; jinak by `reference --dir CESTA` zůstal `review` neznámý.

`load_reference(path) -> dict | None`:
- soubor neexistuje → `None`
- nečitelný JSON, neznámá `schema_version`, **nebo porušení schématu** (špatné
  typy, duplicitní `id`, neznámá sekce či třída, chybějící povinné pole) →
  `None` + varování. Poškozený soubor nesmí shodit `review`.

### Rozšíření `src/guide.py`

`merge_draft_and_guide` dnes zahazuje draftové `cz` a `render` (`guide.py:93`
čte `g.get("cz") or ""`, `:111` jen `suggested_cz`), takže by se vytěžená
hodnota do UI nedostala.

**Změna:** `merge_sources(draft, guide, reference=None) -> dict`, přednost
`guide` > `reference` > `draft`. U položky blok `reference` s klasifikací,
důkazem, návrhem a jedním příznakem `fresh`.

- **`fresh`** je jeden příznak, ne tři: pravdivý, jen když sedí otisk draftu,
  korpusu i prahů. `unknown` (nedostupný `source_root`) se chová jako
  nepravdivý.
- Při `fresh == false` se reference **k předvyplnění nepoužije vůbec** - ani
  `cz`, ani `render`, ani číselné důkazy; zobrazí se jen poznámka, že existuje
  nález z jiného běhu.
- **Čerstvost omezuje výhradně hodnoty z `reference`.** Lidská rozhodnutí
  z `guide.json` platí vždy; priorita `guide > reference > draft` zůstává.
- **Vazba důkazu na hodnotu:** liší-li se zobrazované `cz` od `matched_cz`,
  číselný důkaz se vynechá. Klasifikace a návrh se zobrazují vždy.
- Korpusový otisk se počítá `reference.build_manifest(source_root)`, kde
  `source_root` pochází **ze souboru `reference.json`**. Porovnávat otisk proti
  manifestu v cache nestačí - to jsou dva historické údaje.

`merge_draft_and_guide` zůstane tenkým obalem (`reference=None`).

## Chyby

| Situace | Reakce |
|---|---|
| chybí složka referencí / prázdná | `FatalRunError`, exit 1, soubor beze změny |
| méně než 3 spárované díly (po vyřazení vadných) | `ValueError` → `FatalRunError` |
| duplicitní číslo dílu na jedné straně | `ValueError` → `FatalRunError` |
| jedna strana dvojice se nenačte | vypadne celý díl, nahlas, pokračuj |
| jakékoli selhání dávky nebo neúplná odpověď | **atomické selhání běhu**, předchozí soubor zůstane |
| `FatalRunError` z klienta | ukonči, soubor beze změny |
| chybí `guide.draft.json` | `FatalRunError` s výzvou spustit `scan` |
| poškozený `reference.json` při `review` | ignoruj, varuj, pokračuj bez referencí |

Moduly vyhazují `ValueError`; převod na `FatalRunError` dělá `_cmd_reference`,
aby neodchycená výjimka neobešla diagnostiku CLI.

**Co příkaz zapisuje do DB:** jen `runs` (`create_run` / `finish_run`)
a `llm_calls` (přes `PipelineLLMClient`). Tabulek `chapters`, `glossary`,
`questions`, `term_mentions` a `drift_reports` se **nedotkne**.

## Review UI

`build_app(draft_path, guide_path, on_saved, *, reference_path=None)` -
`reference_path` je **keyword-only**; třetí poziční parametr je dnes `on_saved`
(`server.py:108`). Totéž `run_review_server`. `_cmd_review` předá
`config.REFERENCE_PATH`; kořen korpusu si UI vezme ze `source_root` v souboru.

- `GET /api/guide` volá `merge_sources(draft, guide, load_reference(path))`
- **POST v tomto pořadí:** `_check_must_decide_answered` → `apply_must_decide`
  → `validate` → odstraň bloky `reference` → `save_guide`.
  První krok nesmí zmizet ani se posunout: `apply_must_decide` (`server.py:43`)
  prázdné odpovědi **přeskočí** a na konci seznam vymaže, takže by je pozdější
  `validate` neviděla. Dnešní kód to má správně (`:122` před `:125`).
- bloky `reference` se před uložením odstraní; `guide.json` zůstává čistě
  lidský model (dnes `server.py:129` ukládá celý payload)

Formulář:
- **Potvrzeno referencemi** (`confirmed`) nahoře, sbalené, s počtem
- `weak` rozbalené s důkazem
- `evidence_only`, `proposed`, `not_attested` s **prázdným polem**; u prvního
  se ukáže nalezený důkaz, u dalších dvou návrh modelu
- `not_attested` označené jako slabý signál („v tomto tvaru nedoloženo",
  ne „model se plete")
- nečerstvé viditelně odlišené
- kolize povrchu s aliasem jiné položky → **varování**, ne chyba
- pole zůstávají editovatelná - ruka člověka vyhrává vždy

Chybějící blok `reference` nesmí UI rozbít.

## CLI a konfigurace

```
python main.py reference [--dir CESTA] [--refresh-cache]
```

Příkaz patří do `_MUTATING`, lifecycle `create_run` / `finish_run` jako `scan`,
cost guard `interactive=False`. Pořadí: `scan` → *(normalizace draftu)* →
`reference` → `review`. Souhrn se vypíše na konzoli (počty tříd, cena, co
selhalo); samostatný `reference_report.md` se nestaví - duplikoval by to, co
ukazuje formulář.

| Klíč | Výchozí | K čemu |
|---|---|---|
| `REFERENCE_DIR` | `""` (nutno `--dir`) | kořen se složkami `EN/` a `CZ/` |
| `REFERENCE_PATH` | `data/reference.json` | výsledek těžby |
| `REFERENCE_CACHE_PATH` | `data/reference_corpus.json` | předžvýkaný korpus |
| `MODEL_LEXICOGRAPHER` | `claude-sonnet-5` | model pro návrhy |
| `MAX_TOKENS_LEXICOGRAPHER` | `4000` | krátké odpovědi |
| `REFERENCE_BATCH_SIZE` | `30` | termínů na volání |
| `REFERENCE_MIN_HITS` | `5` | práh pro `confirmed` (odhad) |
| `REFERENCE_MIN_BOOKS` | `2` | práh pro `confirmed` (odhad) |
| `REFERENCE_MIN_CORPUS_BOOKS` | `3` | pod tím se `confirmed` netvrdí |
| `REFERENCE_COOCCUR_RATIO` | `0.5` | podíl dílů pro souvýskyt (odhad) |

Ceny za `MODEL_LEXICOGRAPHER` musí být v `PRICE_*_PER_MTOK`, jinak cost guard
skončí `FatalRunError`.

## Testy

1. **Normalizace (`textnorm`):** NFC, `casefold`, bílé znaky; `guide.normalize`
   beze změny (klíče vztahů se nesmí posunout).
2. **Hledání stupně 0:** `stole` (malé písmeno) → `evidence_only`, **žádné
   předvyplnění**, položka jde do stupně 1; `Mab` (3 znaky, velké písmeno) smí
   být `confirmed`; povrch doložený jen shodou bez ohledu na velikost písmen
   **nesmí** být `confirmed`; sjednocení rozsahů u `Harry Dresden`/`Dresden`;
   alias-only → `primary_attested = false` a žádné předvyplnění; pravidlo
   o začátku věty včetně hranice dokumentů; `Za-Lord` a `Listens-to-Wind`
   s pomlčkou.
3. **Hledání stupně 1:** přesná shoda celého slova; `Bílá rada` **nenajde**
   `Bílé radě` (a je to v pořádku, `not_attested` je slabý signál);
   `Bílá rada` nenajde `Bída rana`.
4. **Souvýskyt:** hraniční testy (přesně na poměru, těsně pod, prázdné `E`);
   `books_with_en` používá EN stranu bez pravidla o začátku věty.
5. **Korpus:** párování dílů, odmítnutí duplicitního čísla, **vyřazení celého
   dílu při selhání jedné strany** a kontrola minima až potom, cache
   round-trip a invalidace při změně velikosti/mtime/kořene.
6. **Agent:** dávkování, obálka `{"proposals":[...]}`, párování přes `id`,
   duplicitní `id` → `ValueError`, cizí `id` se ignoruje, **chybějící `id` →
   `ValueError`**, explicitní `null` → `unresolved`.
7. **Atomické selhání:** selhaná dávka → předchozí `reference.json`
   **nedotčený**, exit ≠ 0, souhrn vypíše co selhalo.
8. **Slití:** přednost `guide` > `reference` > `draft`; číselný důkaz se vynechá
   při neshodě `cz`/`matched_cz`; `fresh == false` → nepředvyplní se nic
   **z reference**, ale lidská rozhodnutí zůstanou; nedostupný `source_root` →
   `fresh` nepravdivý; poškozený `reference.json` UI neshodí.
9. **Glosář:** `seed_from_guide` vrací seznam konfliktů; řádek nalezený jen
   přes alias se nepřepíše, liší-li se `canonical_en`.
10. **End-to-end:** `reference.json` → `GET /api/guide` → POST → `guide.json` →
    `glossary.seed_from_guide`. Musí prokázat, že metadata přežijí slití, že se
    `evidence_only`/`proposed`/`not_attested` **nemůže** dostat do glosáře bez
    ručního vypsání, že postava bez doložení neprojde bez aktivní volby
    `render`, a že `guide.json` po POSTu neobsahuje blok `reference`.

## Otevřené otázky k ověření prvním během

- Kolik povrchů vyřeší stupeň 0 a kolik stupeň 1?
- Jak často skončí návrh jako `not_attested`? Vysoké číslo může znamenat i to,
  že přesná shoda je příliš přísná a skloňování by se tolerovat mělo - to je
  hlavní věc, kterou má první běh změřit.
- Sedí prahy 5 výskytů / 2 díly?
- Kolik návrhů projde výskytem, ale spadne na souvýskytu?
