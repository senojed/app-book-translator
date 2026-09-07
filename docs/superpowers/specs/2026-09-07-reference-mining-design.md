# Těžba terminologie z profesionálních překladů - design

Datum: 2026-09-07
Stav: po kole 21 oponentury
Navazuje na: `2026-09-06-book-translator-design.md`

## Kontext a cíl

Turn Coat je jedenáctý díl Dresden Files. Prvních deset dílů vyšlo česky
v profesionálním překladu. Čtenář, který je přečetl, zná zavedenou terminologii;
překlad jedenáctky, který si vymyslí vlastní, je pro něj horší, i kdyby byl sám
o sobě dobrý. **Návaznost na zavedenou terminologii je hlavní důvod, proč tenhle
nástroj vzniká.**

**Cíl:** před fází `review` předvyplnit návod tím, co je **doložitelné**
z profesionálních překladů, a u každé položky ukázat důkaz.

**Invariant:** **odhad se nikdy nesmí tvářit jako důkaz.** Každá předvyplněná
hodnota nese viditelnou provenienci a hodnota bez doložení se nesmí ocitnout
v poli, které vypadá jako doložené. Člověk může ručně napsat cokoli - to je
jeho právo.

Dřívější znění („nedoložená hodnota se nikdy nepředvyplní") bylo **v rozporu
s tím, co nástroj už dnes dělá**: `guide.py:92` a `:111` předvyplňují `render`
ze scoutova `suggested` a `cz` ze `suggested_cz`, tedy modelové odhady bez
jakéhokoli doložení. Invariant psaný jen pro těžbu ten rozpor zakrýval.
Rozdíl mezi scoutovým návrhem a návrhem lexikografa je jen v tom, že druhý se
tváří jako podložený referencemi. **U glosářových polí** (`cz` a `render`
u postav, míst a termínů) se proto **nepředvyplňuje ani jeden** - oba se
ukazují vedle prázdného pole. Vztahy a styl mají jiný režim, viz Review UI →
Rozsah pravidla.

**Rozhodnuto uživatelem:** u glosářových polí se předvyplňuje **jen to, co je
doloženo referencemi**. Scoutův odhad se ukáže vedle prázdného pole jako text
s tlačítkem „použít návrh" - přijetí je tak jeden vědomý úkon místo sta třiceti
nevědomých. Podrobnosti v sekci Review UI.

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
| `must_decide` klíč neodkazuje na žádnou položku ve své sekci | 9 | `Warden`, `the Nevernever`, `Mouse (pes)`, `grasshopper_nickname` |
| vztah s lomítkem ve jméně | 4 | `Harry` + `Will/Georgia` (dva různí lidé) |
| povrch s poznámkou v závorce | 6 | `Warden(s)`, `the Merlin (title)`, `Stroger's (hospital)` |
| homonymum napříč sekcemi | 1 | `Demonreach` je postava **i** místo |
| neidentifikující alias | 9 | `sir`, `kid`, `apprentice`, `Captain`, `Bob` |
| vztah odkazující zkráceným jménem | 2 | `Ebenezar` vs `Ebenezar McCoy`, `Lara` vs `Lara Raith` |

Celkem ~39 řádků. Pořád jednorázová práce, ale spec o ní musí mluvit přesně -
dřívější znění počítalo jen s prvními dvěma řádky tabulky.

Dřívější verze specu kolem těchto vad stavěla tři podsystémy: editor složených
položek ve formuláři, přemapování `must_decide` a validaci kolizí při ukládání.
To je nepřiměřené - **levnější je odstranit příčinu než obsluhovat následek**.
Navíc se ukázalo, že validace kolizí by formulář rovnou zablokovala: reálný
draft má 15 kolizí a UI nemá na kanonická jména editaci ani mazání.

**Zvoleno:** samostatný jednorázový krok, výsledkem je opravený
`guide.draft.json`. Není to součást těžby a nespouští se opakovaně.

- **skript je report-only.** Vypíše kandidáty na sloučení (kanonické jméno jedné
  položky je aliasem jiné) a výčty rozdělené podle `/` a samostatného `" or "`
  (case-insensitive, po zúžení bílých znaků). Nic nemění a nic se ho neptá -
  interaktivní nástroj ani soubor s deklarativními rozhodnutími se nestaví,
  je to jednorázová operace na ~39 řádcích.
- **skript kontroluje všechny postpodmínky**, ne jen kolize a lomítka - jinak
  by report tvrdil „hotovo" u draftu, který podmínky nesplňuje.
- **rozhoduje člověk** a upraví `guide.draft.json` ručně (nebo s pomocí
  asistenta); skript slouží jen jako seznam míst, kam se podívat
- záloha původního draftu: `data/guide.draft.pre-reference.json`
- sloučení: zůstane delší kanonický tvar, aliasy se sjednotí, poznámky spojí
- výčet: rozdělí se na samostatné položky, `suggested_cz` se rozdělí týmž
  oddělovačem a spáruje pozičně, nesedí-li počty, zůstane prázdné
- **každý `scope_key` u `must_decide` musí po normalizaci ukazovat právě na
  jednu položku ve své sekci.** Devět jich dnes neukazuje nikam
  (`Warden`, `the Nevernever`, `Za-Lord's Militia`, `grasshopper_nickname`,
  `Mouse (pes)`, `Shagnasty/skinwalker`, ...). `apply_must_decide` při
  nenalezení klíče **založí nový řádek**, takže by z nich vznikly duplicitní
  nebo špatně zařazené položky. Pro každý takový klíč se ručně zvolí jedno ze
  tří: opravit klíč na existující položku, povýšit otázku na samostatnou
  položku, nebo otázku smazat.
- **vztahy musí mít v obou koncích jedno jméno.** Čtyři dnes nemají
  (`Billy/Will`, `Gatekeeper/Rashid`, `Rashid/Gatekeeper`, `Will/Georgia`);
  první tři jsou duplicitní zápisy téže dvojice, `Will/Georgia` jsou dva různí
  lidé a patří rozdělit na dva vztahy. Bez toho je zaškrtnutí „vztahy
  zkontrolovány" bezobsažné - a jména vztahů nejdou ve formuláři editovat.
- **alias, který potřebuje vlastní překlad, není alias.** `Injun Joe` je dnes
  alias `Listens-to-Wind` a zároveň má vlastní otázku na překlad. Glosářový
  řádek má ale **jedno `cz` pro kanonický tvar i všechny aliasy**, takže
  přezdívka s vlastním překladem se do něj nevejde. Takové položky se povýší na
  samostatné (a jejich povrch se z aliasů odebere, aby nespustil guard proti
  kolizi).
- výsledek se uloží jako nový `guide.draft.json`, původní se zazálohuje

Prompt scouta se zároveň opravuje (jedna položka = jeden povrch, synonyma do
`aliases`), aby další knihy tenhle krok nepotřebovaly.

**Postpodmínky (skript je všechny kontroluje a test je vynucuje):**

1. každá položka je **jeden povrch** - žádné `/`, `" or "`, ani poznámka
   v závorce. `Warden(s)` → `Warden`; `the Merlin (title)` → `the Merlin`;
   `evocation words (Forzare, ...)` se rozdělí nebo smaže. Povrch s poznámkou
   přesné hledání nikdy nenajde.
2. žádné kanonické jméno není aliasem jiné položky
3. každý `must_decide.scope_key` ukazuje právě na jednu položku ve své sekci
4. oba konce každého vztahu jsou **kanonická jména** existujících postav;
   dvojice lišící se jen zkráceným tvarem (`Harry|Lara` vs `Harry|Lara Raith`)
   se sloučí a vztahové `scope_key` se přemapují
5. **žádné homonymum napříč sekcemi.** `Demonreach` je dnes postava i místo;
   glosář má identitu **globální** (`_seed_one` hledá povrch přes celou
   tabulku), takže sekčně oddělené `id` před kolizí nechrání a druhý seed by
   první tiše přepsal. Buď je to jedna entita (nechat v jedné sekci), nebo dvě
   různé a musí se přejmenovat.
6. aliasy jsou **identifikující**. Skript označí za podezřelý každý alias,
   který splňuje aspoň jedno: začíná malým písmenem; má ≤ 3 znaky; je v krátkém
   seznamu oslovení a rolí (`sir`, `captain`, `kid`, `apprentice`, `boss`,
   `boy`, `girl`, `master`, `mister`, `miss`). Rozhoduje člověk - skript jen
   vypíše seznam. Test vynucuje, že v normalizovaném draftu **žádný označený
   alias nezůstal**. Bez mechanického predikátu by postpodmínka nešla ověřit.

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
- 1-2 znaky se ve stupni 0 **nehledají vůbec** (žádný důkaz), do stupně 1 ale
  jdou normálně - model může zavedený tvar znát i u dvouznakového jména.
  Klasifikace se pak řídí běžnou precedencí.
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

**Predikát souvýskytu.** `E` = spárované díly, kde je **primární** anglický
povrch na **EN** straně (aliasy se do `E` nezapočítávají, viz níže); `C` = díly, kde je navržený český tvar na CZ straně.

```
proposed  <=>  |E| > 0  a  |E ∩ C| >= max(1, ceil(REFERENCE_COOCCUR_RATIO * |E|))
```

Jinak `not_attested`. Prázdné `E` (termín je nový až v jedenáctce) →
`not_attested`.

`books_with_en(corpus, surface)` používá **stejná pravidla jako stupeň 0, ale
na EN straně**: case-insensitive, tytéž hranice slova, **bez** pravidla
o začátku věty (anglický text, nehrozí kolize s českým slovem) a **bez
jakéhokoli délkového omezení** - i jedno- a dvouznakový povrch se hledá.
Délkové omezení má jen stupeň 0 (ochrana před českými homonymy v CZ textu);
kdyby ho měl i `books_with_en`, bylo by `E` u krátkých povrchů vždy prázdné
a nikdy by se nestaly `proposed`.

**Jen primární povrch, ne aliasy.** Alias typu `sir` nebo `kid` by `E` rozšířil
skoro na celý korpus a klasifikaci `proposed` znehodnotil. Krok 0 sice takové
aliasy odebírá, ale predikát na tom nemá stát - primární povrch je jednoznačný
vždy. Aliasy zůstávají užitečné pro **důkaz** ve stupni 0, kde nikdy samy
nepředvyplňují.

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
| `evidence_only` | stupeň 0 | doložen jen alias; nebo obecné slovo s malým písmenem; nebo vlastní jméno nalezené **jen** shodou bez ohledu na velikost písmen (byť nad prahem) | **ne** | důkaz zobrazen, položka jde do stupně 1 |
| `proposed` | stupeň 1 | model navrhl, tvar přesně doložen, souvýskyt sedí | **ne** | návrh vedle prázdného pole |
| `not_attested` | stupeň 1 | model navrhl, tvar v tomto tvaru nedoložen nebo souvýskyt nesedí | **ne** | návrh vedle pole, označený jako slabý signál |
| `unresolved` | - | stupeň 0 nic nedoložil **a** model nenavrhl nic | ne | prázdné |

**Precedence klasifikace.** Nález má jednu třídu, ale drží důkazy z obou
stupňů. Bez explicitního pořadí by `evidence_only` nikdy nepřežilo úplný běh,
protože stupeň 1 klasifikaci přepíše - a přitom ji formulář i testy berou jako
konečnou. Pořadí:

Nejdřív definice: povrch je **způsobilý** (`confirm_eligible`), má-li velké
počáteční písmeno, délku ≥ 3 znaky a **existuje-li alespoň jeden jediný výskyt,
který splňuje všechny podmínky současně**: je shodný i ve velikosti písmen
a (u povrchů kratších než 5 znaků) není na začátku věty.

**Podmínky musí splnit tentýž výskyt, ne každá jiný.** Jinak by u `Mab` stačil
jeden správně psaný výskyt na začátku věty plus nesouvisející `mab` uprostřed -
každá podmínka splněná jiným místem, dohromady falešné potvrzení. Obecné slovo
s malým písmenem způsobilé není nikdy.

1. **způsobilý** primární povrch doložen a nad prahy → `confirmed`
2. **způsobilý** primární povrch doložen, ale pod prahy → `weak`
3. model vrátil návrh → `proposed` / `not_attested` podle souvýskytu
4. existuje jakýkoli důkaz ze stupně 0 (nezpůsobilý povrch, jen alias, nebo
   obecné slovo) → `evidence_only`
5. jinak → `unresolved`

**Kroky 1 a 2 se týkají jen způsobilých povrchů.** Bez toho by `stole`
(79 výskytů, malé písmeno) spadlo do `weak`, `weak` předvyplňuje - a byla by zpět
přesně ta chyba, kvůli které tenhle aparát existuje.

Nezpůsobilý povrch se tedy **nikdy nestane `confirmed` ani `weak`**. Jde do
stupně 1 a skončí jako `proposed` / `not_attested` podle návrhu modelu, nebo
jako `evidence_only`, vrátí-li model `null` a stupeň 0 něco našel.

Důkazy ze stupně 0 (`hits`, `books`, `per_form`, `matched_forms`) se **drží vždy**,
bez ohledu na výslednou třídu; stupeň 1 je nepřepisuje, jen přidává vlastní.
`evidence_only` je tedy konečná třída pro položku, kde stupeň 0 něco našel
a model vrátil `null`.

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

`textnorm.normalize_key()` slouží **jen k identitě položek, nikdy k hledání**.
Přesně: NFC → `casefold()` → každá sekvence bílých znaků na jednu ASCII mezeru
→ `strip()` - casefold by velikost písmen
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
  nebo `Book (\d+)` u EN). Text dílu vznikne spojením **jen `Chapter.raw_text`**
  (bez `Chapter.title`, ty bývají jen „Chapter 1" a zkreslily by počty)
  oddělovačem `"
\x00
"`. Soubor bez rozpoznatelného čísla se přeskočí
  s varováním; chybou je jen **duplicitní** rozpoznané číslo na téže straně →
  `ValueError`.
  **Selže-li jedna strana dvojice, vypadne celý díl** (obě strany), a teprve
  potom se kontroluje minimum `REFERENCE_MIN_CORPUS_BOOKS` (3); pod ním
  `ValueError`.
- `count_en_surface(corpus, surface, side="cz") -> Evidence`
- `count_cz_form(corpus, form) -> Evidence` - přesná shoda celého slova
- `books_with_en(corpus, surface) -> set[int]` - **jeden primární povrch**,
  ne seznam; viz rozhodnutí 4
- `build_manifest(root) -> dict` - `{relativní cesta: [velikost, st_mtime_ns]}`,
  jen `os.stat`, EPUBy se neparsují. `st_mtime_ns` (ne desetinné `st_mtime`)
  kvůli stabilitě porovnání napříč souborovými systémy.
- `save_cache` / `load_cache(path, root)` - nese `schema_version`,
  `source_root` a manifest; neshoda → staví se znovu

### `src/agents/lexicographer.py`

- `SYSTEM_PROMPT` - „jsi znalec české edice této série; vrať zavedený český tvar;
  **když termín neznáš, vrať null - nehádej**".
- `propose(items, client, *, model, max_tokens) -> dict[str, str | None]` -
  vstup `[{id, term_en, kind, note}]`, výstup mapa `id -> cz | None`.
- **Identita je `id = "{section}/{normalize_key(klíč)}"`**. Sekce je v klíči
  kvůli stabilitě a čitelnosti, **ne** proto, že by homonyma napříč sekcemi byla
  povolená - krok 0 je zakazuje (postpodmínka 5), protože glosář má identitu
  globální.
- **Obálka odpovědi je objekt:** `{"proposals": [{"id": ..., "cz": ...}]}`.
  (Ne proto, že by `extract_json` seznam neuměl - ověřeno, `json.loads` vrátí
  i top-level seznam. Objekt je zvolený proto, že regexový fallback při
  ukecaném modelu hledá `\{.*\}`, takže seznam by se z textu s okolním
  povídáním nevytáhl.)
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
    "source": str,             # kept (confirmed/weak/evidence_only)
                               #   | proposed (proposed/not_attested)
                               #   | none (unresolved)
})
```

- `resolve(corpus, items, client_factory, cfg) -> list[Finding]`, kde
  `items: list[SurfaceItem]` a

  ```python
  SurfaceItem = TypedDict("SurfaceItem", {
      "id": str,          # "{section}/{normalize_key(klíč)}"
      "section": str,     # characters | places | terms
      "surface": str,     # primární povrch
      "aliases": list[str],
      "note": str,        # posílá se lexikografovi, ovlivňuje návrh
  })
  ```

  Pouhý „seznam povrchů" nestačí: nález i lexikograf potřebují `id`, sekci,
  aliasy i poznámku. Sestavení `items` z draftu je věc volajícího
  (`_cmd_reference`), ne `resolve`.
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

**Původ hodnoty musí být explicitní**, jinak frontend neví, co zamknout a co
umí vrátit zpět. Každá položka nese:

```json
"provenance": "human" | "reference" | "none",
"scout_suggestion": "..." | null,
"lexicographer_suggestion": "..." | null
```

`provenance` popisuje **zobrazenou hodnotu** (`human` = z `guide.json`,
`reference` = doloženo těžbou, `none` = pole je prázdné). Oba návrhy se drží
**odděleně a současně** - položka může mít scoutův i lexikografův návrh a
formulář nabídne oba, každý s vlastním tlačítkem.

- **`fresh`** je jeden příznak, ne tři: pravdivý, jen když sedí otisk draftu,
  korpusu i prahů. `unknown` (nedostupný `source_root`) se chová jako
  nepravdivý.
- Při `fresh == false` se reference **k předvyplnění nepoužije vůbec** - ani
  `cz`, ani `render`, ani číselné důkazy; zobrazí se jen poznámka, že existuje
  nález z jiného běhu.
- **Čerstvost omezuje výhradně hodnoty z `reference`.** Lidská rozhodnutí
  z `guide.json` platí vždy; priorita `guide > reference > draft` zůstává.
- **Vazba důkazu na hodnotu** platí **jen pro třídy s předvyplněnou hodnotou**
  (`confirmed`, `weak`): liší-li se zobrazované `cz` od `matched_cz`, číselný
  důkaz se vynechá. U `evidence_only` je `cz` prázdné **záměrně** a jeho důkaz
  se zobrazuje vždy - jinak by třída, jejímž jediným obsahem je důkaz, neměla
  co ukázat. Klasifikace a návrh se zobrazují vždy, **s výjimkou nečerstvé
  reference**, kde se nezobrazuje nic než poznámka.
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
- **před uložením se odstraní všechna průběžná metadata, ne jen bloky
  `reference`:** `provenance`, `scout_suggestion`, `lexicographer_suggestion`
  a příznak `relationships_reviewed`. Ukládá se **allowlist**: u postav
  `name_en`, `aliases`, `render`, `cz`, `note`; u míst a termínů
  `name_en`/`term_en`, `aliases`, `cz`, `note`; u vztahů `a`, `b`, `address`;
  plus `style` a `rules`. `note` nese kontext od scouta a **`_seed_one` ho
  ukládá do glosáře** (`glossary.py:139`) - vynechat ho z allowlistu by ten
  kontext ztratilo. Cokoli jiného se
  zahodí. Dnes `server.py:129` ukládá celý payload, takže by v `guide.json`
  zůstala i pomocná pole formuláře.
- **zaškrtnutí „vztahy zkontrolovány"** jede v payloadu jako
  `relationships_reviewed: bool`; validace odmítne uložení, je-li `false`
  nebo chybí a sekce vztahů není prázdná; do `guide.json` se nezapisuje.

### Chování polí podle původu hodnoty

Zásada: **odhad se nepředvyplňuje, důkaz ano - a každá akce je vratná.**
Původní hodnota se nikdy neztratí.

**Rozsah pravidla.** Platí pro hodnoty, které se stanou **závazným glosářovým
termínem**: `cz` a `render` u postav, míst a termínů. Ostatní sekce mají jiné
zacházení, protože pro ně těžba žádný důkaz neposkytuje (jsou mimo její rozsah):

| Sekce | Zacházení |
|---|---|
| postavy, místa, termíny | pravidlo platí - viz tabulka níže |
| **vztahy** (tyká/vyká) | scoutův návrh **předvyplněn**, ale sekce vyžaduje jedno zaškrtnutí „zkontrolováno" před uložením |
| **styl** (jeden blok textu) | předvyplněn scoutem, bez ceremonie - člověk ho stejně přečte celý |
| `must_decide` textové | prázdné pole, návrh pod ním (už dnes) |
| `must_decide` vztahové | roletka s prázdnou volbou `-- vyber --`, návrh vedle jako text |

Vztahy jsou vyšší sázka, než se zdá - špatné vykání se táhne celou knihou.
Vynutit 34 roletek by ale bylo nepřiměřené k binární volbě, kterou lze
přehlédnout v tabulce. Jedno zaškrtnutí za sekci je vědomý úkon a stojí jeden
klik.

**Oprava nepravdivého tvrzení:** dřívější znění specu tvrdilo, že formulář už
vzor „prázdné pole + návrh vedle" používá u `must_decide`. Platí to jen pro
textové otázky; vztahové se dnes předvyplňují ze `md.default`
(`index.html:80-88`) a `guide.py:127` předvyplňuje `address` ze scoutova
`suggested`. Obojí se mění podle tabulky výše.

| Původ | Pole | Ovládání |
|---|---|---|
| doloženo referencemi (`confirmed`, `weak`) | **předvyplněno**, ve výchozím stavu **zamčené**, vedle důkaz („112× v 8 dílech") | „změnit předvyplněné" odemkne; po změně se objeví „vrátit zpět předvyplněné" |
| jen scoutův odhad | **prázdné**, návrh vedle jako text | „použít návrh" vyplní; poté se tlačítko změní na „zpět", které pole zase vyprázdní |
| návrh lexikografa (`proposed`, `not_attested`) | **prázdné**, návrh vedle, výrazněji odlišený | totéž co u scouta |
| nic (`unresolved`) | prázdné | - |

- **„přijmout všechny scoutovy návrhy"** jedním tlačítkem nahoře. Kdo nechce
  klikat po jednom, udělá jedno vědomé rozhodnutí místo sta třiceti nevědomých.
  **Nepřepíše ručně vyplněná ani referencemi doložená pole** a „zpět" vrátí
  **jen ta pole, která tahle akce sama změnila** - jinak by hromadná akce
  porušila zásadu, že se původní hodnota nikdy neztratí.
- Návrh se **nikdy nedává do editovatelného pole** - po přepsání by zmizel
  a nešlo by porovnat, co navrhl model a co říká referenční překlad.
- Zamčení polí doložených referencemi chrání před nechtěným přepsáním; změna
  hodnoty podložené profesionálním překladem má být vědomý úkon.
- Tentýž vzor formulář používá u **textových** `must_decide` (návrh pod
  prázdným polem), zavedený ze stejného důvodu - scout tam navrhoval věty typu
  `"keep Nevernever"`, které by předvyplněné zanesly do glosáře nesmysl.
  Vztahové `must_decide` se dnes předvyplňují a mění se podle tabulky výše.

Formulář dál:
- **Potvrzeno referencemi** (`confirmed`) nahoře, sbalené, s počtem
- `weak` rozbalené s důkazem
- `not_attested` označené jako slabý signál („v tomto tvaru nedoloženo",
  ne „model se plete")
- nečerstvé viditelně odlišené
- kolize povrchu s aliasem jiné položky → **varování**, ne chyba

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
   předvyplnění**, položka jde do stupně 1; **kombinovaný regresní test
   způsobilosti** - povrch, kde jeden výskyt má správnou velikost písmen na
   začátku věty a jiný výskyt je uprostřed věty ale špatnou velikostí, **není
   způsobilý**; povrch s jedním výskytem splňujícím obojí naráz způsobilý je; `Mab` (3 znaky, velké písmeno) smí
   být `confirmed`; povrch doložený jen shodou bez ohledu na velikost písmen
   **nesmí** být `confirmed`; sjednocení rozsahů u `Harry Dresden`/`Dresden`;
   alias-only → `primary_attested = false` a žádné předvyplnění; pravidlo
   o začátku věty včetně hranice dokumentů; `Za-Lord` a `Listens-to-Wind`
   s pomlčkou.
3. **Hledání stupně 1:** přesná shoda celého slova; `Bílá rada` **nenajde**
   `Bílé radě` (a je to v pořádku, `not_attested` je slabý signál);
   `Bílá rada` nenajde `Bída rana`.
4. **Souvýskyt:** hraniční testy (přesně na poměru, těsně pod, prázdné `E`);
   `books_with_en` používá EN stranu bez pravidla o začátku věty a **aliasy
   `E` neovlivňují** - položka s aliasem `sir` musí dát stejné `E` jako bez něj.
   **Dvouznakový povrch musí dát neprázdné `E`**, je-li v EN textu - délkové
   omezení platí jen pro stupeň 0.
5. **Korpus:** párování dílů, odmítnutí duplicitního čísla, **vyřazení celého
   dílu při selhání jedné strany** a kontrola minima až potom, cache
   round-trip a invalidace při změně velikosti/mtime/kořene.
6. **Agent:** dávkování, obálka `{"proposals":[...]}`, párování přes `id`,
   duplicitní `id` → `ValueError`, cizí `id` se ignoruje, **chybějící `id` →
   `ValueError`**, explicitní `null` → `unresolved` **jen když není důkaz ze stupně 0**, jinak zůstává `evidence_only`.
7. **Atomické selhání:** selhaná dávka → předchozí `reference.json`
   **nedotčený**, exit ≠ 0, souhrn vypíše co selhalo.
8. **Normalizace draftu (krok 0):** test vynucuje **všech šest postpodmínek**
   proti **skutečnému** normalizovanému draftu - (1) žádný výčet ani poznámka
   v závorce, (2) žádné kanonické jméno není aliasem jiné položky,
   (3) každý `must_decide.scope_key` ukazuje právě na jednu položku ve své
   sekci, (4) oba konce každého vztahu jsou kanonická jména a zkrácené dvojice
   jsou sloučené, (5) žádné homonymum napříč sekcemi, (6) žádný
   neidentifikující alias.
9. **Zachování `note`:** poznámka od scouta přežije cestu
   `draft` → `GET` → `POST` → `guide.json` → `glossary.seed_from_guide`
   a skončí v glosářovém řádku.
10. **Chování polí:** rozsah pravidla (vztahy a styl se předvyplňují, sekce
   vztahů vyžaduje zaškrtnutí „zkontrolováno"; vztahové `must_decide` mají
   prázdnou volbu); `provenance` a oba návrhy odděleně v payloadu z `GET`;
   „přijmout všechny" nepřepíše ručně vyplněné ani doložené pole a „zpět" vrátí
   jen jím změněná; hodnota doložená referencemi je předvyplněná a zamčená,
   „změnit" ji odemkne, „vrátit zpět" obnoví původní; scoutův odhad pole
   nevyplní, „použít návrh" ano a „zpět" ho zase vyprázdní; „přijmout všechny"
   je vratné; **testuje se serializovaný payload**, ne vzhled - nepoužitý návrh
   se do payloadu nesmí dostat.
11. **Slití:** přednost `guide` > `reference` > `draft`; číselný důkaz se vynechá
   při neshodě `cz`/`matched_cz`; `fresh == false` → nepředvyplní se nic
   **z reference**, ale lidská rozhodnutí zůstanou; nedostupný `source_root` →
   `fresh` nepravdivý; poškozený `reference.json` UI neshodí.
12. **Glosář:** `seed_from_guide` vrací seznam konfliktů; řádek nalezený jen
   přes alias se nepřepíše, liší-li se `canonical_en`.
13. **End-to-end:** `reference.json` → `GET /api/guide` → POST → `guide.json` →
    `glossary.seed_from_guide`. Musí prokázat, že metadata přežijí slití, že se
    `evidence_only`/`proposed`/`not_attested` **nemůže** dostat do glosáře bez
    **výslovného přijetí člověkem** (tlačítko „použít návrh") nebo ručního
    vypsání, že postava bez doložení neprojde bez aktivní volby
    `render`, a že `guide.json` po POSTu neobsahuje blok `reference`.

## Otevřené otázky k ověření prvním během

- Kolik povrchů vyřeší stupeň 0 a kolik stupeň 1?
- Jak často skončí návrh jako `not_attested`? Vysoké číslo může znamenat i to,
  že přesná shoda je příliš přísná a skloňování by se tolerovat mělo - to je
  hlavní věc, kterou má první běh změřit.
- Sedí prahy 5 výskytů / 2 díly?
- Kolik návrhů projde výskytem, ale spadne na souvýskytu?
