# Těžba terminologie z profesionálních překladů - design

Datum: 2026-09-07
Stav: po kole 7 oponentury (Codex + Claude)
Navazuje na: `2026-09-06-book-translator-design.md`

## Kontext a cíl

Turn Coat je jedenáctý díl Dresden Files. Prvních deset dílů vyšlo česky
v profesionálním překladu. Čtenář, který je přečetl, zná zavedenou terminologii
a jména; překlad jedenáctky, který si vymyslí vlastní, je pro něj horší, i kdyby
byl sám o sobě dobrý. **Návaznost na zavedenou terminologii je hlavní důvod,
proč tenhle nástroj vzniká.**

Scout po `scan` navrhl 132 povrchů (54 postav, 59 termínů, 19 míst); 11 z nich
jsou výčty, které se rozdělí na samostatné položky (viz rozhodnutí 5). Bez
referencí na všech odpovídá člověk ručně nebo se hádá.

**Cíl:** před fází `review` předvyplnit návod tím, co je **doložitelné**
z profesionálních překladů, a u každé položky ukázat důkaz.

**Invariant, který nesmí padnout:** do glosáře se nesmí dostat termín, který si
model vymyslel a není doložený v žádném českém textu. Invariant je vynucen
mechanicky (prázdné pole plus vynucená volba u postav), ne kázní uživatele.

## Zdrojová data

`<Reference>/EN/*.epub` a `<Reference>/CZ/*.epub`, deset dílů, párované číslem
dílu v názvu souboru. Ověřeno: všech 20 souborů se načte stávajícím
`ingest.load_book`; EN korpus ~1 200 000 slov, CZ ~972 000 slov. Vnitřní členění
EPUBů se mezi jazyky liší (díl 1: EN 27 dokumentů, CZ 5; díl 2: EN 1 dokument),
takže **kapitoly na sebe nesedí**. Návrh na zarovnání kapitol nespoléhá a pracuje
s dílem jako s jedním textem.

## Rozsah

### V rozsahu
- Načtení referenčního korpusu (EN i CZ) přes stávající `ingest`, párování dílů
- Deterministické zjištění, které anglické povrchy překladatelé ponechali
- Návrh českých tvarů modelem s **povinným ověřením proti korpusu**, včetně
  testu souvýskytu přes EN stranu
- Uložení výsledku do `data/reference.json` a jeho slití do podkladu pro UI
- Souhrnný report do `data/reference_report.md`
- Seskupení položek v review UI podle síly důkazu

### Mimo rozsah
- Poziční zarovnání textů (stupeň 2) - návrh nechává čisté místo, nestaví to
- Zápis do glosáře mimo obvyklou cestu přes `review`
- Těžba stylu, vypravěčského hlasu nebo vztahů (tyká/vyká) z referencí
- Použití referencí za běhu `run` (překladatel dostává glosář, ne korpus)
- Plnohodnotná morfologie češtiny - používá se prefixové porovnání
  (viz rozhodnutí 4), ne lemmatizace

## Zásadní rozhodnutí

### 1. Výsledek těžby žije ve vlastním souboru, ne v draftu

Původní varianta obohacovala `guide.draft.json`. Zamítnuto: `main.py:105` volá
`save_draft(GUIDE_DRAFT_PATH, result)` a přepíše draft **celý**, takže opakovaný
`scan` by těžbu tiše smazal.

**Zvoleno:** těžba zapisuje `data/reference.json` (nový soubor, `scan` na něj
nesahá). Podklad pro UI vzniká slitím tří zdrojů:
`guide.json` (člověk) > `reference.json` (těžba) > `guide.draft.json` (scout).

Opakovaný běh **neakumuluje předchozí výstup** (soubor se nahradí podle pravidel
v `write_reference`). Není to idempotence v silném smyslu - model může příště
navrhnout něco jiného.

### 2. Nic neobchází review a neověřené nemá hodnotu

`reference` needituje glosář. Glosář se plní beze změny cestou `review` →
`guide.json` → `glossary.seed_from_guide`.

Samotné zvýraznění barvou návrh nezastaví: validace kontroluje jen neprázdnost
pole, takže vyplněná vymyšlenina by se uložením dostala do glosáře.

**Zvoleno:**
- U tříd `proposed` a `not_attested` zůstává `cz` **prázdné**. Návrh se ukazuje
  jen jako text vedle pole a člověk ho musí opsat nebo napsat vlastní.
- **U postav to nestačí.** Validace dovoluje prázdné `cz`, když `render == keep`,
  UI má `keep` jako výchozí hodnotu a `seed_from_guide` pak vloží do glosáře
  anglické jméno. Nedoložená postava by tak prošla i s prázdným polem. Proto se
  u postav s třídou `proposed` / `not_attested` `render` **nepředvyplňuje**
  a UI vyžaduje aktivní volbu; bez ní validace neprojde.

### 3. Model navrhuje, ale globální výskyt není důkaz vazby

Původní znění tvrdilo „rozhoduje korpus". Příliš silné: `Rada` je běžné české
slovo a jeho četnost o vazbě na *White Council* nevypovídá nic.

**Dvě opatření:**

- Třída `confirmed` smí vzniknout **jen ze stupně 0** - anglický povrch doslova
  v českém textu je přímý důkaz, že ho překladatel ponechal.
- Návrh modelu se testuje na **souvýskyt** přes EN stranu korpusu.

**Přesný predikát souvýskytu.** `E` = množina spárovaných dílů, kde je anglický
povrch (nebo alias) na EN straně; `C` = množina dílů, kde je navržený český tvar
na CZ straně.

```
souvyskyt = E ∩ C
proposed  ⇔  |E| > 0  a  |souvyskyt| >= max(1, ceil(REFERENCE_COOCCUR_RATIO * |E|))
```

Jinak `not_attested`. Prázdné `E` (termín je nový až v jedenáctce) →
`not_attested`; korpus k němu nemá co říct.

**`not_attested` není vyvrácení.** Čeština skloňuje: zavedený termín se
v navrženém tvaru vyskytovat nemusí, přestože v textu běžně je. Třída proto
znamená „v tomhle tvaru nedoloženo", ne „model se plete".

**Zrušené rozhodnutí z kola 3.** Spec chtěl na doložení použít existující
`concordance.find_form_occurrences`. Ověřením se ukázalo, že to nejde:

```
form_key("Bílá rada") == form_key("Bída rana")   → True
find_form_occurrences("Byl to Za-Lord.", "Za-Lord") → []
```

Kmen zkracuje „bílá" i „bída" na `bí` a „rada" i „rana" na `ra`, takže dvě
nesouvisející spojení jsou pro něj totožná; tokenizace přes `\w+` navíc rozseká
`Za-Lord` na pomlčce a termín nenajde ani tam, kde stojí doslova. Pro hlídání
driftu v jedné kapitole to stačí (falešný poplach jen vyvolá otázku), pro
doložení termínu v milionovém korpusu ne. `concordance` proto zůstává **beze
změny** a `reference.py` má vlastní matcher - viz rozhodnutí 4.

### 4. Pravidla hledání a falešné shody

Pokus ukázal past: `stole` má v referencích 79 výskytů v 10/10 dílech - je to
ale český lokativ slova *stůl* (*na stole*), ne ponechaný anglický termín.
Povrch `stole` v draftu scouta skutečně je (ve významu „štóla").

**Case-sensitivita to neřeší** a starší verze specu se v tom mýlila: české „na
stole" je malými písmeny, takže case-sensitive dotaz ho najde stejně. Jediná
spolehlivá obrana je nedůvěřovat automatu u obecných slov.

**`normalize_key` slouží jen k identitě, nikdy k hledání.** Starší verze specu
chtěla normalizovat text i dotaz přes `normalize_key()` a pak v něm hledat
case-sensitive - jenže ta funkce `casefold()` provádí vždy, takže velikost
písmen už v normalizovaném textu není. Rozpor se ruší: hledá se v **surovém
textu** (jen NFC), `normalize_key` se používá výhradně na klíče položek.

**Dva oddělené kontrakty hledání** (`reference.py`, vlastní implementace):

*Stupeň 0 - přesné hledání anglického povrchu v CZ textu:*
- surový text po NFC, **velikost písmen zachována**
- dotaz escapován (`re.escape`), hranice slova přes `(?<!\w)` / `(?!\w)`
  s `re.UNICODE`, aby pomlčka a apostrof uvnitř povrchu zůstaly součástí dotazu
  (`Listens-to-Wind`, `Za-Lord` se najdou jako celek)
- **velké počáteční písmeno** (vlastní jméno): case-insensitive, `confirmed`
  povoleno od 3 znaků výš
- **malé počáteční písmeno** (obecné slovo): case-sensitive a **nikdy
  nedosáhne `confirmed`** - nejvýš `weak`. Case-sensitivita je slabý filtr,
  ne záruka.
- 1-2 znaky se nehledají vůbec (`hits = 0` → `unresolved`)

*Stupeň 1 - doložení navrženého českého tvaru (snese skloňování):*

**Spec algoritmus nepředepisuje, předepisuje přejímací kritéria.** Tři pokusy
napsat pravidlo od stolu selhaly: `max(4, len-2)` nespáruje ani `bílá`/`bílé`;
`max(3, len-2)` dává na skutečném korpusu (270 000 slov) u `práh` 54 tvarů
včetně `práce`, `právo`, `prázdný`; varianta s uzavřenou množinou koncovek
propadá na `plášť`/`pláště`, protože předpoklad „prefix = kmen" u řady slov
neplatí. Volba algoritmu proto patří do implementačního plánu, kde se dá měřit.

Povinná kritéria:

| Musí spárovat | Nesmí spárovat |
|---|---|
| `bílá` ↔ `bílé`, `bílou` | `bílá` / `bída` |
| `rada` ↔ `radě`, `radu`, `radou` | `rada` / `radost`, `raději` |
| `plášť` ↔ `pláště`, `pláštěm` | `práh` / `práce`, `právo`, `prázdný` |
| `Bílá rada` ↔ `Bílé radě` | `Bílá rada` / `Bída rana` |

- víceslovný tvar musí sedět jako souvislá posloupnost slov
- implementace **musí změřit** počet tvarů, které pravidlo zachytí pro vzorek
  termínů na skutečném korpusu, a číslo uvést; pravidlo, které u čtyřpísmenného
  dotazu vrátí desítky nesouvisejících tvarů, je nepřijatelné
- **konzervativní pravidlo se preferuje před velkorysým.** Důsledek chyby je
  omezený - stupeň 1 nikdy nic nepředvyplní, jen přeřadí mezi `proposed`
  a `not_attested`. Falešné `not_attested` stojí člověka jeden pohled, falešné
  `proposed` stojí důvěryhodnost celého nástroje.
- Oboustranné zkracování (jako `concordance.stem`) je zakázané - právě ono
  slévá `Bílá rada` s `Bída rana`. Regresní test na tuhle dvojici je povinný.
- Povrch kratší než 5 znaků musí mít alespoň jeden výskyt **mimo začátek věty**.
  Začátek věty = pozice 0 dokumentu, první nebílý znak po `.`/`!`/`?`/`…`
  následovaném bílým znakem, nebo první znak po oddělovači dokumentů. Chrání
  před jmény, která jsou zároveň českými slovy (`Bob` na začátku věty vs.
  luštěnina). Díly se skládají z dokumentů s explicitním oddělovačem
  (`\n\x00\n`), aby začátky kapitol nepropadly jako „uprostřed věty".

### 5. Aliasy rozšiřují dotaz, ale nenahrazují primární tvar

Scout u `Harry Dresden` uvádí `Dresden`, `Harry`, `Hoss`. Hledání jen primárního
povrchu by u překladu, který používá zkrácenou podobu, našlo málo výskytů.

**Pravidla:**
- Hledá se primární povrch **i každý alias**, ale důkaz se vede **po jednotlivých
  tvarech** (`per_form: {tvar: Evidence}`).
- Celkové výskyty jsou **sjednocení rozsahů** v textu, ne součet - `Dresden`
  uvnitř `Harry Dresden` se nesmí započítat dvakrát.
- Způsobilost ke `confirmed` (velikost písmene, délka, pravidlo o začátku věty)
  se posuzuje **u každého tvaru zvlášť**; krátký alias tak neobejde omezení
  primárního povrchu.
- **`confirmed` vyžaduje doložení primárního povrchu a prahy se počítají
  výhradně z `per_form[primární]`.** Jeden výskyt primárního tvaru a sto výskytů
  aliasu tedy `confirmed` nedá. Je-li doložen jen alias, třída je `weak`
  a v důkazu je uvedeno, který tvar zabral (`matched_en`). Aliasy jsou doplňkový
  důkaz pro člověka, ne podklad pro automatické potvrzení.
- **Alias-only nález nepředvyplní `cz` ani `render`** - slouží jen jako
  zobrazený důkaz. Výskyt `Dresden` nedokládá tvar `Harry Dresden`: překlad může
  příjmení ponechat a křestní jméno počeštit. Nic se tím neztrácí, protože
  `weak` položka je ve formuláři rozbalená i s důkazem („976× v 10 dílech")
  a člověk ji doplní za dvě vteřiny. Cena za nepředvyplnění je nulová, cena za
  špatné předvyplnění je chybný termín protažený celou knihou.

**Složené položky se před těžbou rozdělí.** Draft obsahuje 11 položek, které
nejsou jedním povrchem, ale výčtem variant: `White Court / Red Court / Vampire
Courts`, `veil/veiling spell`, `Will/Billy`, `naagloshii/skinwalker` a další.
Přesné hledání takový řetězec nikdy nenajde, takže by všechny skončily jako
`not_attested`, ačkoli samotný `skinwalker` má v referencích 58 výskytů.

**Výčet není alias.** `White Court / Red Court / Vampire Courts` jsou tři různé
dvory a každý potřebuje vlastní překlad; `Flickum bicus / Forzare / Aparturum`
jsou tři různá zaklínadla. Slít je do jedné položky s jedním `cz` je věcná chyba.

**Automatické rozdělování se ruší** (zvažováno v kolech 5 a 6, zamítnuto).
Rozdělit klíč nestačí: složené položky mají i složené `suggested_cz`, aliasy
a někdy na ně míří `must_decide.scope_key`; `apply_must_decide` by původní
klíč vkládal zpět; a bylo by nutné migrovat i existující `guide.json`. K tomu
přistupuje kolize s glosářem - `Billy Borden` má v draftu aliasy
`['Billy', 'Will', 'Will Borden']` a `glossary._seed_one` páruje přes aliasy,
takže rozdělené `Will` a `Billy` by podle pořadí přepsaly jeho řádek. To je
nepřiměřené strojvedení kvůli 11 položkám.

**Zvoleno: rozdělí je člověk ve formuláři.**
- těžba složenou položku pozná (obsahuje `/` nebo `" or "`), dá jí třídu
  `compound`, **přeskočí ji** a nic pro ni nenavrhuje
- formulář ji ukáže ve vlastní sekci „Rozdělit ručně" s předvyplněnými poli
  pro jednotlivé varianty; člověk potvrdí nebo upraví
- POST složenou položku nahradí samostatnými položkami a původní řetězec
  zahodí, takže se do `guide.json` ani do glosáře nikdy nedostane
- žádná automatická migrace `suggested_cz`, aliasů ani `must_decide`

Prompt scouta se opravuje (jedna položka = jeden povrch, synonyma do `aliases`),
ale detekce zůstane - starší drafty se nepřegenerovávají.

Zároveň se opravuje prompt scouta: jedna položka = jeden povrch, synonyma patří
do `aliases`. Kanonizace zůstává i tak - starší drafty se nepřegenerovávají.

**Identita položek se před těžbou validuje.** `scan_book` prázdné ani duplicitní
položky nekontroluje (dedup je jen v `scan_chunks`), takže `id` z draftu není
zaručeně unikátní. Prázdný klíč se přeskočí a nahlásí; duplicitní
`(section, klíč)` se deterministicky sloučí (sjednotí se aliasy a poznámky)
a nahlásí. Bez toho by k položce nešlo jednoznačně přiřadit návrh ani nález.

## Klasifikace nálezu

| Třída | Vzniká z | Podmínka | `cz` předvyplněno | UI |
|---|---|---|---|---|
| `confirmed` | stupeň 0 | primární povrch doložen, ≥ `REFERENCE_MIN_HITS` výskytů ve ≥ `REFERENCE_MIN_BOOKS` dílech, velké počáteční písmeno, ≥ 3 znaky | ano | sbaleno |
| `weak` | stupeň 0 | doloženo, ale pod prahem / jen alias / obecné slovo | ano | rozbaleno s důkazem |
| `proposed` | stupeň 1 | model navrhl, tvar na CZ straně doložen a souvýskyt sedí | **ne** | návrh vedle pole |
| `not_attested` | stupeň 1 | model navrhl, ale tvar nedoložen nebo souvýskyt nesedí | **ne** | návrh vedle pole, označený jako nedoložený |
| `unresolved` | - | model nenavrhl nic, nebo povrch pod 3 znaky | ne | prázdné |
| `stale` (příznak) | předchozí běh | dávka v tomhle běhu selhala, převzat starší nález | dle převzaté třídy | označeno jako starší |

Prahy jsou **počáteční odhady bez měření**; první běh je má potvrdit nebo posunout.
Práh rozhoduje jen o rozdílu `confirmed` / `weak`, tedy o míře zvýraznění -
neobchází člověka nic.

## Moduly a hranice

| Modul | Zná | Nezná |
|---|---|---|
| `src/textnorm.py` | normalizace řetězce (bez závislostí) | vše ostatní |
| `src/reference.py` | EPUBy přes `ingest`, vlastní matcher, `textnorm` | LLM, DB, `guide`, `concordance` |
| `src/agents/lexicographer.py` | prompt → klient → parsování | korpus, DB, soubory |
| `src/reference_mine.py` | drátuje korpus + agenta + `reference.json` | DB, glosář |
| `src/guide.py` (rozšíření) | slití tří zdrojů pro UI | LLM, korpus |
| `main.py` (`reference`) | parsuj, zavolej, vypiš | vše ostatní |

Starší verze tabulky si protiřečila: `reference.py` neměl znát `guide`, a přesto
volat `guide.normalize_key()`. Normalizace je obecná textová operace, proto
`src/textnorm.py` bez závislostí, odkud ji berou `guide`, `reference` i `review_ui`.

### `src/textnorm.py`

`normalize_key(s) -> str` - NFC, `casefold()`, zúžení bílých znaků, `strip()`.
Stávající `guide.normalize()` (`strip().lower()`) zůstává beze změny kvůli
`relationship_key`, aby se nezměnily už existující klíče vztahů.

### `src/reference.py`

```python
@dataclass
class Evidence:
    hits: int              # výskytů (sjednocení rozsahů, bez dvojího započtení)
    books: list[int]
    matched_en: str        # anglický tvar, který zabral (primární nebo alias)
    confirm_eligible: bool # splňuje pravidla pro confirmed (délka, velikost písmene)

@dataclass
class Corpus:
    cz: dict[int, str]
    en: dict[int, str]
    manifest: dict         # cesty, velikosti, mtime - pro fingerprint a cache
```

- `load_corpus(root) -> Corpus` - páruje podle čísla (`^(\d+)` u CZ, `#(\d+)`
  nebo `Book (\d+)` u EN). Duplicitní číslo dílu na téže straně → `ValueError`
  (tiché přepsání klíče by zkreslilo důkaz). Nespárovaný díl se přeskočí
  a nahlásí. Méně než `REFERENCE_MIN_CORPUS_BOOKS` (3) spárovaných dílů →
  `ValueError`.
- `count_en_surface(corpus, surface) -> Evidence` - přesné hledání anglického
  povrchu v CZ textu (kontrakt „stupeň 0" z rozhodnutí 4).
- `count_cz_form(corpus, form) -> Evidence` - prefixové hledání českého tvaru
  v CZ textu (kontrakt „stupeň 1"). **Vlastní implementace**, ne
  `concordance.find_form_occurrences` - viz rozhodnutí 3.
- `books_with_en(corpus, surfaces) -> set[int]` - díly, kde je povrch na EN straně.
- `save_cache` / `load_cache(path, root)` - cache nese `schema_version`,
  normalizovaný `root` a manifest `(cesta, velikost, mtime)`. Neshoda v čemkoli →
  staví se znovu. Načtení 20 EPUBů trvá ~30 s.

### `src/agents/lexicographer.py`

- `SYSTEM_PROMPT` - „jsi znalec české edice této série; vrať zavedený český tvar;
  **když termín neznáš, vrať null - nehádej**".
- `propose(items, client, *, model, max_tokens) -> dict[str, str | None]` -
  vstup `[{id, term_en, kind, note}]`, výstup mapa `id -> cz | None`.
- **Identita je `id = "{section}/{normalizovaný klíč}"`**, ne `term_en`: stejné
  jméno může být v `places` i `terms` a přes `term_en` by je nešlo rozlišit.
- **Obálka odpovědi je objekt:** `{"proposals": [{"id": ..., "cz": ...}]}`.
  Sdílený `parsing.extract_json` umí regexem `\{.*\}` vytáhnout jen objekt.
- **Validace:** duplicitní `id` → `ValueError`; `id`, které nebylo v dotazu →
  ignoruje se a nahlásí; `cz` musí být `str` nebo `null`, jinak `ValueError`.
- **Chybějící `id` v odpovědi není totéž co `cz: null`.** Explicitní `null`
  znamená „model termín nezná" → `unresolved`. Chybějící položka znamená, že
  model na ni zapomněl → **selhání té položky**: převezme se předchozí nález
  jako `stale`. Bez tohoto rozlišení by zapomenutá položka přepsala dřívější
  platný nález.
- **Chyby:** `OutputTruncated` → jeden pokus s dvojnásobným `max_tokens`, pak
  dávka `failed`. Neparsovatelná odpověď i `ValueError` z validace → dávka
  `failed`, běh pokračuje další dávkou. Síťové a limitní výjimky, které
  `AnthropicClient` na `FatalRunError` nepřevádí (`APIConnectionError`,
  `RateLimitError`, 5xx po vyčerpání SDK retry), se chovají stejně → dávka
  `failed`. Jen `FatalRunError` ukončí celý příkaz.

### `src/reference_mine.py`

```python
Finding = TypedDict("Finding", {
    "id": str,              # "{section}/{normalizovaný klíč}"
    "section": str,         # characters | places | terms
    "surface": str,         # povrch, jak ho napsal scout
    "cz": str | None,       # None u proposed/not_attested/unresolved
    "klasifikace": str,     # confirmed | weak | proposed | not_attested | unresolved
    "navrh": str | None,    # co navrhl model (i když se nepředvyplní)
    "hits": int,
    "books": list[int],
    "per_form": dict,       # tvar -> {hits, books}
    "cooccurrence": list[int],
    "matched_en": str | None,   # anglický tvar, který zabral
    "matched_cz": str | None,   # český tvar, ke kterému se důkaz vztahuje
    "stale": bool,
    "source": str,          # kept | proposed
})

ResolveResult = TypedDict("ResolveResult", {
    "findings": list[Finding],
    "attempted": list[str],      # id poslaná modelu
    "failed": list[str],         # id v selhaných dávkách
    "not_attempted": list[str],  # id vynechaná kvůli --limit
})
```

- `resolve(corpus, surfaces, client_factory, cfg) -> ResolveResult`
- `write_reference(result, path, run_id, fingerprint)` - `data/reference.json`,
  atomicky (temp + `os.replace`). **Stavový automat pro každé `id` v aktuálním
  draftu** (starší verze pokrývala jen položky poslané modelu a na nálezy
  stupně 0 zapomínala):

  | Stav položky v tomhle běhu | Zápis |
  |---|---|
  | vyřešena stupněm 0 | nový nález nahradí starý |
  | poslána modelu, odpověď platná | nový nález nahradí starý |
  | poslána modelu, dávka `failed` | převezme se předchozí nález s `stale: true` |
  | chybí v jinak platné odpovědi | totéž - `stale: true` |
  | nezkoušena kvůli `--limit` | převezme se předchozí nález beze změny |
  | bez předchůdce v kterémkoli z těchto případů | `unresolved` |
  | `id` už není v draftu | **odstraní se** |

  Bez toho by `--limit N` smazal položky mimo limit a přechodná chyba dávky by
  zahodila dříve platné nálezy.
- `write_report(final_payload, path, run_id)` - zapisuje se **až po** datech
  a generuje se z **finálního slitého payloadu**, ne z `ResolveResult`. Jinak by
  report tvrdil `unresolved` tam, kde se ve skutečnosti převzal starší nález.
  Report je **odvoditelný artefakt, ne transakční partner dat**: pád mezi dvěma
  `os.replace` nutně vyrobí „data nová, report starý", takže atomicita přes dva
  soubory by byla lež. Report nese `run_id`; neshoda znamená „zastaralý, spusť
  znovu", ne poškozený stav.

### Schéma `data/reference.json`

```json
{
  "schema_version": 1,
  "run_id": 7,
  "fingerprint": {
    "draft": "sha1 klíčů a aliasů z guide.draft.json",
    "corpus": "sha1 manifestu korpusu",
    "thresholds": "sha1 hodnot REFERENCE_* z config"
  },
  "coverage": {
    "attempted": ["terms/white council"],
    "failed": ["terms/warlock"],
    "missing_response": ["terms/threshold"],
    "skipped_by_limit": ["terms/nevernever"]
  },
  "findings": [ { ...Finding... } ]
}
```

`coverage` odlišuje čtyři různé důvody, proč položka nemá nález: zkoušeno
a model řekl „neznám" (`attempted`, výsledek `unresolved`), dávka technicky
selhala (`failed`), model položku v odpovědi vynechal (`missing_response`),
nebo se nezkoušela kvůli `--limit`. Bez toho rozlišení by se částečný běh tvářil
jako úplný a technické selhání jako odpověď modelu.

**Bez předchůdce** (položka selhala a v předchozím souboru nález nemá) je
výsledek `unresolved`, ale zůstává v `coverage.failed` - UI pak neříká „nic se
nenašlo", nýbrž „nepodařilo se zjistit".

`load_reference(path) -> dict | None`:
- soubor neexistuje → `None` (běh bez těžby je legitimní)
- nečitelný JSON, neznámá `schema_version`, **nebo porušení schématu** (špatné
  typy, duplicitní `id`, neznámá sekce, chybějící povinné pole) → `None`
  + varování na stdout. Validuje se celý dokument, ne jen hlavička - syntakticky
  platný soubor se špatnými typy by jinak spadl až v `merge_sources` nebo v UI.
- fingerprint se **nekontroluje při načtení**, ale předává se do UI, které podle
  něj rozhodne (viz níže)

### Rozšíření `src/guide.py`

`merge_draft_and_guide(draft, guide)` dnes zahazuje draftové `cz` a `render`
(`guide.py:93` čte `g.get("cz") or ""`, `:111` jen `suggested_cz`), takže by se
vytěžená hodnota do UI vůbec nedostala.

**Změna:** `merge_sources(draft, guide, reference=None) -> dict`, přednost
`guide` > `reference` > `draft`. U položky navíc blok:

```json
"reference": {"klasifikace": "...", "hits": 0, "books": [], "per_form": {},
              "matched_en": "...", "matched_cz": "...", "navrh": "...",
              "cooccurrence": [], "stale": false,
              "draft_fresh": true, "corpus_fresh": true, "thresholds_fresh": true}
```

- **Tři samostatné příznaky čerstvosti:** `draft_fresh`, `corpus_fresh`,
  `thresholds_fresh`. Čerstvost omezuje **výhradně hodnoty a důkazy pocházející
  z `reference`** - uložená lidská rozhodnutí z `guide.json` platí vždy
  a priorita `guide > reference > draft` zůstává. Předvyplnění z reference
  (`cz` i `render`) i číselné důkazy se použijí **jen když sedí všechny tři**; jinak se zobrazí pouze poznámka, že existuje
  nález z jiného běhu. Skrýt čísla a hodnotu ponechat by nestačilo: opakovaný
  `scan` může změnit aliasy při zachovaném hlavním klíči, takže by ve formuláři
  zůstala hodnota opřená o už neplatný důkaz. `run_id` čerstvost neprokazuje.
- **Odkud se otisky berou při `review`:** draft a prahy jsou levné (čtení JSONu
  a `config`). Korpusový otisk se sestaví **znovu z disku** (`os.stat` nad
  soubory v `REFERENCE_DIR` - cesty, velikosti, mtime); EPUBy se neparsují,
  takže je to levné. Porovnávat otisk v `reference.json` proti manifestu
  uloženému v cache nestačí - to jsou dva historické údaje a pozdější změnu
  EPUBů neodhalí. Není-li složka dostupná, je `corpus_fresh` **`unknown`**
  a chová se jako `false`.

  `merge_sources` proto dostává i cestu ke korpusu:
  `merge_sources(draft, guide, reference=None, *, reference_dir=None)`,
  a `build_app` / `run_review_server` ji předávají dál.
- **Vazba důkazu na hodnotu** platí jen pro `confirmed` a `weak` (tedy tam, kde
  je `cz` předvyplněné): liší-li se zobrazované `cz` od `matched_cz`, číselný
  důkaz se vynechá. Klasifikace a `navrh` se zobrazují vždy - u `proposed` /
  `not_attested` je `cz` prázdné záměrně a podmínka by tam metadata vždy zahodila.

`merge_draft_and_guide` zůstane tenkým obalem (`reference=None`), aby stávající
testy a volání platily.

### Guard v `glossary.seed_from_guide` (oprava latentní chyby)

`_seed_one` dnes páruje nový povrch i přes **aliasy** existujícího řádku a pak
přepíše `canonical_en`, `cz` i `type`. Na skutečných datech to je past:
`Billy Borden` má aliasy `['Billy', 'Will', 'Will Borden']`, takže seed položky
`Billy` by mu přepsal kanonický tvar. Není to chyba zavedená tímhle návrhem,
ale existující chování, které rozdělené položky snadno spustí.

**Guard:** řádek nalezený **jen přes alias** (ne přes `canonical_en`) se nesmí
přepsat, liší-li se příchozí `canonical_en` od uloženého. Místo přepsání se
příchozí povrch přidá k aliasům a nahlásí se konflikt. Povinný end-to-end test.

## Chyby

Těžba je **volitelný krok**, ne podmínka běhu.

| Situace | Reakce |
|---|---|
| chybí složka referencí / prázdná | `FatalRunError`, exit 1, `reference.json` beze změny |
| méně než 3 spárované díly | `ValueError` → `_cmd_reference` převede na `FatalRunError` |
| duplicitní číslo dílu na jedné straně | `ValueError` → `FatalRunError` |
| jednotlivý EPUB se nenačte | přeskoč, nahlas, pokračuj |
| nespárovaný díl | přeskoč, nahlas |
| dávka selže (rozbitý JSON, truncated) | dávka → `failed`, převezme se předchozí nález, běh pokračuje |
| `FatalRunError` z klienta (auth, cost guard) | ukonči, `reference.json` beze změny |
| chybí `guide.draft.json` | `FatalRunError` s vysvětlením, že má běžet `scan` |
| poškozený `reference.json` při `review` | ignoruj, varuj, pokračuj bez referencí |

`reference.py` a `reference_mine.py` vyhazují `ValueError`; převod na
`FatalRunError` dělá `_cmd_reference`, aby neodchycená výjimka neobešla
diagnostiku CLI. Pokryto testem, že se při chybě zachová předchozí soubor.

**Co příkaz zapisuje do DB:** jen `runs` (`create_run` / `finish_run`) a
`llm_calls` (přes `PipelineLLMClient`). Tabulek `chapters`, `glossary`,
`questions`, `term_mentions` a `drift_reports` se **nedotkne**.

## Review UI

Dnešní `build_app(draft_path, guide_path, on_saved)` a
`run_review_server(draft_path, guide_path)` třetí zdroj nemají a `main.py:123`
je volá po staru - výsledek těžby by se do UI nikdy nedostal.

**Změny:**
- obě signatury dostanou **keyword-only** `reference_path`:
  `build_app(draft_path, guide_path, on_saved, *, reference_path=None)`.
  Poziční vložení nepřipadá v úvahu - třetí poziční parametr je dnes `on_saved`
  (`server.py:108`) a nová cesta by se za něj vydávala.
- `GET /api/guide` volá `guide.merge_sources(draft, guide, load_reference(path))`
- `_cmd_review` předá `config.REFERENCE_PATH`
- **POST metadata odstraní.** Dnes `server.py:129` ukládá celý payload včetně
  bloků `reference`; ty by zůstaly v `guide.json` mezi lidskými rozhodnutími a
  po dalším běhu těžby zastaraly. Server je před uložením odstraní.
- **Postavy bez doložení vyžadují aktivní volbu `render`** (viz rozhodnutí 2).
  Nestačí odmítnout na serveru: dnešní `index.html:111` má
  `select(..., c.render || "keep")`, takže by uživatel viděl „ponechat", ale
  v payloadu by nic nebylo, a musel by volbu přepnout tam a zpět. Roletka proto
  dostane prázdnou položku `-- vyber --`, fallback `|| "keep"` se ruší a testuje
  se **serializovaný payload**, ne jen vzhled stránky.

Formulář:
- sekce **Potvrzeno referencemi** (`confirmed`) nahoře, sbalená, s počtem
- `weak` rozbalené, s důkazem („12× v dílech 3, 5, 7")
- `proposed` a `not_attested` s **prázdným polem** a návrhem vedle;
  `not_attested` označené jako v referencích nedoložené
- `stale` a `fresh: false` viditelně odlišené
- pole zůstávají editovatelná - ruka člověka vyhrává vždy

Chybějící blok `reference` (běh bez těžby) nesmí UI rozbít.

## CLI a konfigurace

```
python main.py reference [--dir CESTA] [--refresh-cache] [--limit N]
```

- `--dir` přebije `config.REFERENCE_DIR`; `--refresh-cache` postaví korpus znovu;
  `--limit N` omezí **jen stupeň 1** (počet povrchů poslaných modelu). Stupeň 0
  je zdarma a deterministický, omezovat ho nemá důvod a vyrobilo by to nekompletní data.
- Příkaz patří do `_MUTATING` (drží zámek), lifecycle `create_run` / `finish_run`
  jako `scan`, cost guard `interactive=False`.
- Pořadí: `scan` → `reference` → `review`.

Nové klíče v `config.py`:

| Klíč | Výchozí | K čemu |
|---|---|---|
| `REFERENCE_DIR` | `""` (nutno `--dir`) | kořen se složkami `EN/` a `CZ/` |
| `REFERENCE_PATH` | `data/reference.json` | výsledek těžby |
| `REFERENCE_CACHE_PATH` | `data/reference_corpus.json` | předžvýkaný korpus |
| `REFERENCE_REPORT_PATH` | `data/reference_report.md` | souhrn pro člověka |
| `MODEL_LEXICOGRAPHER` | `claude-sonnet-5` | model pro návrhy |
| `MAX_TOKENS_LEXICOGRAPHER` | `4000` | krátké odpovědi, žádná próza |
| `REFERENCE_BATCH_SIZE` | `30` | termínů na volání |
| `REFERENCE_MIN_HITS` | `5` | práh pro `confirmed` (odhad) |
| `REFERENCE_MIN_BOOKS` | `2` | práh pro `confirmed` (odhad) |
| `REFERENCE_MIN_CORPUS_BOOKS` | `3` | pod tím se `confirmed` netvrdí |
| `REFERENCE_COOCCUR_RATIO` | `0.5` | podíl dílů pro souvýskyt (odhad) |

Ceny za `MODEL_LEXICOGRAPHER` musí být v `PRICE_*_PER_MTOK`, jinak cost guard
skončí `FatalRunError` - stávající chování `PipelineLLMClient`.

## Testy

1. **Normalizace (`textnorm`):** NFC, `casefold`, bílé znaky; `guide.normalize`
   zůstává beze změny (klíče vztahů se nesmí posunout).
2. **Matcher (kritické):** celá tabulka přejímacích kritérií z rozhodnutí 4 -
   musí spárovat `bílá`/`bílé`, `rada`/`radě`, `plášť`/`pláště`,
   `Bílá rada`/`Bílé radě`; nesmí spárovat `bílá`/`bída`, `rada`/`radost`,
   `práh`/`práce`, `Bílá rada`/`Bída rana`. `Za-Lord` a `Listens-to-Wind` se
   najdou i s pomlčkou, velikost písmen se v surovém textu zachovává.
   Součástí je **měření** počtu zachycených tvarů na skutečném korpusu.
3. **Složené položky:** `White Court / Red Court / Vampire Courts` dostane třídu
   `compound`, těžba ji přeskočí a nic pro ni nenavrhne; formulář ji ukáže
   v sekci „Rozdělit ručně" s předvyplněnými variantami; POST ji nahradí
   samostatnými položkami a složený řetězec se do `guide.json` nedostane.
   Test kolize s glosářem: seed položky `Billy` **nesmí** přepsat
   `canonical_en` řádku `Billy Borden` nalezeného jen přes alias.
4. **Korpus:** párování dílů, odmítnutí duplicitního čísla i malého korpusu,
   `stole` skončí nejvýš `weak` i při stovkách výskytů, `Mab` (3 znaky, velké
   písmeno) smí být `confirmed`, sjednocení rozsahů u překryvu
   `Harry Dresden`/`Dresden` (žádné dvojí započtení), doložený jen alias →
   `weak` s `matched_en`, pravidlo o začátku věty včetně hranice dokumentů,
   escapování metaznaků, pomlčka uvnitř povrchu, cache round-trip a invalidace.
5. **Agent (fake klient):** dávkování, obálka `{"proposals":[...]}`, párování
   přes `id` (stejný `term_en` ve dvou sekcích se nesplete), duplicitní `id` →
   `ValueError`, cizí `id` se ignoruje,
   `OutputTruncated` → jeden pokus s dvojnásobkem, pak `failed`,
   chybějící `id` → `stale` (ne `unresolved`), explicitní `null` → `unresolved`,
   síťová výjimka → `failed`.
6. **Orchestrace (fake klient, mini korpus):** pět tříd, `proposed`/`not_attested`
   nechávají `cz` prázdné, hraniční testy souvýskytu (přesně na poměru, těsně
   pod, prázdné `E`), skloňovaný tvar prefixové porovnání najde (nespadne do
   `not_attested`), selhaná dávka převezme předchozí nález s `stale`,
   `--limit` nesmaže položky mimo limit a zapíše se do `coverage`, zmizelý
   povrch se odstraní, prahy se počítají jen z primárního tvaru (jeden výskyt
   primárního + sto u aliasu → `weak`), report vzniká z finálního payloadu.
7. **Slití (`merge_sources`):** přednost `guide` > `reference` > `draft`;
   číselný důkaz se vynechá při neshodě `cz`/`matched_cz`, klasifikace a `navrh`
   zůstanou; `fresh: false` při změněném fingerprintu; volání bez reference se
   chová jako dnes; **kterýkoli z `draft_fresh`/`corpus_fresh`/`thresholds_fresh`
   nepravdivý → nepředvyplní se vůbec nic**; chybějící cache → `corpus_fresh`
   je `unknown` a chová se jako `false`; alias-only nález nepředvyplní `cz` ani `render`, jen zobrazí důkaz; poškozený nebo
   schématu neodpovídající `reference.json` UI neshodí.
8. **End-to-end invariant:** `reference.json` → `GET /api/guide` → POST →
   `guide.json` → `glossary.seed_from_guide`. Musí prokázat, že metadata přežijí
   slití, že se `proposed`/`not_attested` **nemůže** dostat do glosáře bez
   ručního vypsání, že **postava bez doložení neprojde bez aktivní volby
   `render`**, a že `guide.json` po POSTu neobsahuje žádný blok `reference`.

## Otevřené otázky k ověření prvním během

- Kolik povrchů (132 po rozdělení výčtů ještě víc) vyřeší stupeň 0 a kolik stupeň 1?
- Jak často skončí návrh jako `not_attested`? Vysoké číslo = model českou edici
  nezná a stupeň 2 bude nutný.
- Sedí prahy 5 výskytů / 2 díly, nebo je většina nálezů těsně pod nimi?
- Kolik návrhů projde výskytem, ale spadne na souvýskytu? Měří užitečnost filtru.
- Jak často prefixové porovnání zachrání skloňovaný tvar, který by přesné
  hledání označilo za nedoložený? A kolik falešných shod naopak vyrobí?
