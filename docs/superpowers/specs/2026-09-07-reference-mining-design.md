# Těžba terminologie z profesionálních překladů - design

Datum: 2026-09-07
Stav: po kole 9 oponentury (Codex + Claude)
Navazuje na: `2026-09-06-book-translator-design.md`

## Kontext a cíl

Turn Coat je jedenáctý díl Dresden Files. Prvních deset dílů vyšlo česky
v profesionálním překladu. Čtenář, který je přečetl, zná zavedenou terminologii;
překlad jedenáctky, který si vymyslí vlastní, je pro něj horší, i kdyby byl sám
o sobě dobrý. **Návaznost na zavedenou terminologii je hlavní důvod, proč tenhle
nástroj vzniká.**

Scout po `scan` navrhl 132 povrchů (54 postav, 59 termínů, 19 míst). Bez
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
- Načtení referenčního korpusu přes stávající `ingest`, párování dílů
- Deterministické zjištění, které anglické povrchy překladatelé ponechali
- Návrh českých tvarů modelem s **povinným ověřením proti korpusu** včetně
  testu souvýskytu přes EN stranu
- Uložení do `data/reference.json` a slití do podkladu pro UI
- Report do `data/reference_report.md`
- Seskupení položek v review UI podle síly důkazu
- Guard proti přepsání glosářového řádku nalezeného jen přes alias

### Mimo rozsah
- Poziční zarovnání textů (stupeň 2) - nechává se čisté místo, nestaví se
- Zápis do glosáře mimo obvyklou cestu přes `review`
- Automatické rozdělování složených položek (viz rozhodnutí 5)
- Těžba stylu, vypravěčského hlasu nebo vztahů z referencí
- Použití referencí za běhu `run` (překladatel dostává glosář, ne korpus)

## Zásadní rozhodnutí

### 1. Výsledek těžby žije ve vlastním souboru

`main.py:105` volá `save_draft(GUIDE_DRAFT_PATH, result)` a přepíše draft
**celý**, takže opakovaný `scan` by těžbu v draftu tiše smazal.

Těžba proto zapisuje `data/reference.json`. Podklad pro UI vzniká slitím tří
zdrojů: `guide.json` (člověk) > `reference.json` (těžba) > `guide.draft.json`
(scout).

Opakovaný běh **neakumuluje předchozí výstup**; není to idempotence v silném
smyslu, protože model může příště navrhnout něco jiného.

### 2. Nic neobchází review a neověřené nemá hodnotu

`reference` needituje glosář. Glosář se plní beze změny cestou `review` →
`guide.json` → `glossary.seed_from_guide`.

Zvýraznění barvou návrh nezastaví: validace kontroluje jen neprázdnost pole,
takže vyplněná vymyšlenina by se uložením dostala do glosáře.

- U tříd `proposed` a `not_attested` zůstává `cz` **prázdné**; návrh se ukazuje
  jen jako text vedle pole.
- **Alias-only nález nepředvyplní `cz` ani `render`.** Výskyt `Dresden`
  nedokládá tvar `Harry Dresden` - překlad může příjmení ponechat a křestní
  jméno počeštit. Nic se tím neztrácí: položka je ve formuláři rozbalená
  i s důkazem („976× v 10 dílech") a člověk ji doplní za dvě vteřiny.
- **U postav to nestačí.** Validace dovoluje prázdné `cz` při `render == keep`,
  UI má `keep` jako výchozí (`index.html:111`) a `seed_from_guide` pak vloží
  anglické jméno. Proto se u postav bez doloženého primárního tvaru `render`
  nepředvyplňuje, roletka má prázdnou volbu `-- vyber --` a validace neprojde
  bez aktivní volby. Testuje se **serializovaný payload**, ne vzhled.

### 3. Model navrhuje, korpus omezuje

`confirmed` smí vzniknout **jen ze stupně 0** - anglický povrch doslova
v českém textu je přímý důkaz, že ho překladatel ponechal. Globální výskyt
navrženého českého tvaru důkaz vazby není: `Rada` je běžné české slovo.

**Predikát souvýskytu.** `E` = spárované díly, kde je anglický povrch (nebo
alias) na EN straně; `C` = díly, kde je navržený český tvar na CZ straně.

```
souvyskyt = E ∩ C
proposed  <=>  |E| > 0  a  |souvyskyt| >= max(1, ceil(REFERENCE_COOCCUR_RATIO * |E|))
```

Jinak `not_attested`. Prázdné `E` (termín je nový až v jedenáctce) →
`not_attested`.

**`not_attested` není vyvrácení**, jen „v tomhle tvaru nedoloženo". Čeština
skloňuje a zavedený termín se v navrženém tvaru vyskytovat nemusí.

### 4. Hledání: dva kontrakty, algoritmus se v designu nepředepisuje

Past ověřená měřením: `stole` má v referencích 79 výskytů v 10/10 dílech - je to
ale český lokativ slova *stůl*, ne ponechaný termín. `stole` v draftu scouta
skutečně je (ve významu „štóla"). Case-sensitivita to neřeší, protože české „na
stole" je taky malými písmeny.

**`textnorm.normalize_key()` (NFC, `casefold`, zúžení bílých znaků) slouží jen
k identitě položek, nikdy k hledání** - casefold by velikost písmen zahodil.
Hledá se v surovém textu po NFC.

**Kontrakt A - anglický povrch v CZ textu (stupeň 0), přesné hledání:**
- velikost písmen zachována; dotaz escapován (`re.escape`); hranice slova přes
  `(?<!\w)` / `(?!\w)` s `re.UNICODE`, aby pomlčka a apostrof uvnitř povrchu
  zůstaly součástí dotazu (`Listens-to-Wind`, `Za-Lord`)
- **velké počáteční písmeno** (vlastní jméno): case-insensitive, `confirmed`
  povoleno od 3 znaků výš
- **malé počáteční písmeno** (obecné slovo): case-sensitive a **nikdy
  nedosáhne `confirmed`** - nejvýš `weak`
- 1-2 znaky se nehledají vůbec
- povrch kratší než 5 znaků musí mít výskyt **mimo začátek věty**. Začátek věty
  = pozice 0 dokumentu, první nebílý znak po `.`/`!`/`?`/`…` s bílým znakem,
  nebo znak po oddělovači dokumentů. Díly se skládají z dokumentů s explicitním
  oddělovačem (`\n\x00\n`).

**Kontrakt B - navržený český tvar v CZ textu (stupeň 1), snese skloňování:**

**Spec algoritmus nepředepisuje.** Tři pokusy napsat pravidlo od stolu selhaly
a všechny tři byly vyvráceny měřením:

| Pokus | Selhání |
|---|---|
| prefix `max(4, len-2)` | nespáruje ani `bílá`/`bílé` |
| prefix `max(3, len-2)` | `práh` → 54 tvarů (`práce`, `právo`, `prázdný`) |
| prefix + uzavřená množina koncovek | propadá na `plášť`/`pláště` |

Volba algoritmu patří do implementačního plánu, kde se dá měřit. Design
předepisuje **přejímací kritéria**:

| Musí spárovat | Nesmí spárovat |
|---|---|
| `bílá` ↔ `bílé`, `bílou` | `bílá` / `bída` |
| `rada` ↔ `radě`, `radu`, `radou` | `rada` / `radost`, `raději` |
| `plášť` ↔ `pláště`, `pláštěm` | `práh` / `práce`, `právo`, `prázdný` |
| `Bílá rada` ↔ `Bílé radě` | `Bílá rada` / `Bída rana` |

- víceslovný tvar musí sedět jako souvislá posloupnost slov
- oboustranné zkracování (jako `concordance.stem`) je zakázané - právě ono
  slévá `Bílá rada` s `Bída rana`
- **Měřitelná akceptace:** eval fixture v testech, >=40 ručně anotovaných dvojic
  (>=20 skloňovacích, >=20 zavádějících). Práh: **100 % na množině „nesmí
  spárovat", >=90 % na množině „musí spárovat"**. Navíc povinný checkpoint před
  integrací: pro 20 vzorových dotazů se vypíší všechny zachycené tvary
  ze skutečného korpusu a projdou očima.
- **Konzervativní pravidlo se preferuje.** Důsledek chyby je omezený - stupeň 1
  nikdy nic nepředvyplní, jen přeřadí mezi `proposed` a `not_attested`. Falešné
  `not_attested` stojí jeden pohled, falešné `proposed` stojí důvěryhodnost.

### 5. Aliasy rozšiřují dotaz; složené položky rozděluje člověk

**Aliasy:**
- hledá se primární povrch i každý alias, důkaz se vede **po jednotlivých
  tvarech** (`per_form`)
- výskyty jsou **sjednocení rozsahů**, ne součet - `Dresden` uvnitř
  `Harry Dresden` se nesmí započítat dvakrát
- způsobilost ke `confirmed` se posuzuje u každého tvaru zvlášť; krátký alias
  neobejde omezení primárního povrchu
- **prahy pro `confirmed` se počítají výhradně z `per_form[primární]`.** Jeden
  výskyt primárního tvaru a sto u aliasu `confirmed` nedá.
- `Finding.primary_attested` říká, jestli byl doložen primární povrch.
  **Předvyplnění `cz`/`render` se řídí jím, ne třídou.**

**Identita položek se před těžbou validuje.** `scan_book` prázdné ani
duplicitní položky nekontroluje (dedup je jen v `scan_chunks`), takže `id`
z draftu není zaručeně unikátní a dvě položky by dostaly týž klíč - návrh ani
nález by pak nešlo jednoznačně přiřadit. Před stavbou `id`:
- položka s prázdným klíčem se **přeskočí** a nahlásí
- duplicitní `(section, normalize_key(klíč))` se **deterministicky sloučí**:
  sjednotí se aliasy, poznámky se spojí `"; "`, první výskyt určí pořadí
- sloučení se nahlásí, aby bylo dohledatelné

(Rozhodnutí z kola 4; konsolidační přepis v kole 8 ho vypustil.)

**Složené položky (11 v aktuálním draftu):** `White Court / Red Court / Vampire
Courts`, `Flickum bicus / Forzare / Aparturum`, `Will/Billy`, `veil/veiling
spell`, `naagloshii/skinwalker` a další.

**Automatické rozdělování se ruší** (zvažováno v kolech 5 a 6, zamítnuto
v kole 7). Rozdělit klíč nestačí: položky mají i složené `suggested_cz`, aliasy,
míří na ně `must_decide.scope_key`, `apply_must_decide` by klíč vkládal zpět,
a bylo by nutné migrovat existující `guide.json`. Navíc `White Court / Red Court
/ Vampire Courts` nejsou aliasy jedné entity, ale tři různé dvory - automat
nemá jak poznat výčet od synonym.

**Jediný tok:**
1. těžba položku pozná (obsahuje `/` nebo `" or "`), dá jí třídu `compound`,
   **přeskočí ji** a nic pro ni nenavrhuje
2. formulář ji ukáže v sekci „Rozdělit ručně" s předvyplněnými poli pro
   jednotlivé varianty; člověk potvrdí, upraví nebo variantu smaže
3. POST **nejdřív** složené položky rozbalí na samostatné, teprve **potom**
   spustí `apply_must_decide`
4. `must_decide` se složeným `scope_key` (v draftu jsou dvě:
   `naagloshii/skinwalker` a `Shagnasty/skinwalker`) se přemapuje na **variantu,
   kterou člověk výslovně určí**. Odvodit ji z rozděleného textu nejde: ponechá-li
   člověk u `naagloshii/skinwalker` oba řádky, odpověď patří jen jednomu z nich.
   Formulář proto u každé takové otázky nabídne roletku s variantami a payload
   nese cílové `id`; nechá-li člověk všechny varianty smazat, otázka se zahodí
5. validace odmítne payload, v němž po rozbalení zůstal jakýkoli klíč
   obsahující `/` nebo `" or "`

Prompt scouta se opravuje (jedna položka = jeden povrch, synonyma do `aliases`),
detekce ale zůstává - starší drafty se nepřegenerovávají.

### 6. Identita při kolizi povrchu s existujícím aliasem

`glossary._seed_one` páruje nový povrch i přes **aliasy** existujícího řádku
a pak přepíše `canonical_en`, `cz` i `type`. Na reálných datech je to past:
`Billy Borden` má v draftu aliasy `['Billy', 'Will', 'Will Borden']`, takže
ruční rozdělení `Will/Billy` vyrobí položku `Billy`, která by mu přepsala
kanonický tvar.

Guard „nepřepiš, přidej k aliasům" nestačí - `Billy` už alias je, takže by to
byl no-op a **výslovné rozhodnutí člověka by zmizelo beze stopy**.

**Zvoleno: žádné tiché slučování ani tiché přepsání.** Kolize povrchu nové
položky s aliasem jiné položky je **chyba validace** se srozumitelnou hláškou:
„`Billy` je už alias položky `Billy Borden` - je to táž postava (smaž tuhle
položku), nebo jiná (přejmenuj)?" Rozhodne člověk ve formuláři.

Guard v `seed_from_guide` zůstává jako druhá pojistka pro data, která do
`guide.json` doputovala jinudy: řádek nalezený **jen přes alias** se nesmí
přepsat, liší-li se příchozí `canonical_en`; místo přepsání se nahlásí konflikt.
Je to oprava latentní chyby stávajícího kódu, ne nová funkce.

## Klasifikace nálezu

| Třída | Vzniká z | Podmínka | Předvyplní `cz` | UI |
|---|---|---|---|---|
| `confirmed` | stupeň 0 | primární povrch doložen, >= `MIN_HITS` výskytů ve >= `MIN_BOOKS` dílech, velké počáteční písmeno, >= 3 znaky | ano | sbaleno |
| `weak` | stupeň 0 | pod prahem nebo obecné slovo, **ale `primary_attested`** | ano | rozbaleno s důkazem |
| `weak` | stupeň 0 | doložen jen alias (`primary_attested = false`) | **ne** | rozbaleno, důkaz uvádí `matched_en` |
| `proposed` | stupeň 1 | model navrhl, tvar doložen, souvýskyt sedí | **ne** | návrh vedle prázdného pole |
| `not_attested` | stupeň 1 | model navrhl, tvar nedoložen nebo souvýskyt nesedí | **ne** | návrh vedle pole, označený jako nedoložený |
| `compound` | detekce | povrch obsahuje `/` nebo `" or "` | **ne** | sekce „Rozdělit ručně" |
| `unresolved` | - | model nenavrhl nic, nebo povrch pod 3 znaky | ne | prázdné |

`stale` je **příznak**, ne třída: nález převzatý z předchozího běhu, protože
dávka selhala. Zobrazuje se podle převzaté třídy, ale označený jako starší.

Prahy jsou **počáteční odhady bez měření**; první běh je má potvrdit nebo
posunout. Práh rozhoduje jen o rozdílu `confirmed` / `weak`.

## Moduly a hranice

| Modul | Zná | Nezná |
|---|---|---|
| `src/textnorm.py` | normalizace řetězce (bez závislostí) | vše ostatní |
| `src/reference.py` | EPUBy přes `ingest`, vlastní matcher, `textnorm` | LLM, DB, `guide`, `concordance` |
| `src/agents/lexicographer.py` | prompt → klient → parsování | korpus, DB, soubory |
| `src/reference_mine.py` | drátuje korpus + agenta + `reference.json` | DB, glosář |
| `src/guide.py` (rozšíření) | slití tří zdrojů pro UI | LLM, korpus |
| `main.py` (`reference`) | parsuj, zavolej, vypiš | vše ostatní |

`concordance` zůstává **beze změny** a `reference.py` ho nepoužívá - jeho
`find_form_occurrences` koliduje (`form_key("Bílá rada") == form_key("Bída rana")`)
a nenajde `Za-Lord` ani v textu, kde stojí doslova. Pro drift v jedné kapitole
to stačí, pro doložení v milionovém korpusu ne.

### `src/reference.py`

```python
@dataclass
class Evidence:
    hits: int              # sjednocení rozsahů, bez dvojího započtení
    books: list[int]
    matched_en: str        # tvar, který zabral (primární nebo alias)
    confirm_eligible: bool

@dataclass
class Corpus:
    cz: dict[int, str]
    en: dict[int, str]
    manifest: dict         # cesty, velikosti, mtime
    source_root: str
```

- `load_corpus(root) -> Corpus` - páruje podle čísla (`^(\d+)` u CZ, `#(\d+)`
  nebo `Book (\d+)` u EN). Duplicitní číslo dílu na téže straně → `ValueError`.
  Nespárovaný díl se přeskočí a nahlásí. Méně než `REFERENCE_MIN_CORPUS_BOOKS`
  (3) spárovaných dílů → `ValueError`.
- `count_en_surface(corpus, surface) -> Evidence` - kontrakt A.
- `count_cz_form(corpus, form) -> Evidence` - kontrakt B.
- `books_with_en(corpus, surfaces) -> set[int]`
- `build_manifest(root) -> dict` - jen `os.stat` (cesty, velikosti, mtime),
  EPUBy se neparsují. Používá se pro cache i pro otisk při `review`.
- `save_cache` / `load_cache(path, root)` - cache nese `schema_version`,
  `source_root` a manifest; neshoda → staví se znovu.

### `src/agents/lexicographer.py`

- `SYSTEM_PROMPT` - „jsi znalec české edice této série; vrať zavedený český tvar;
  **když termín neznáš, vrať null - nehádej**".
- `propose(items, client, *, model, max_tokens) -> dict[str, str | None]` -
  vstup `[{id, term_en, kind, note}]`, výstup mapa `id -> cz | None`.
- **Identita je `id = "{section}/{normalize_key(klíč)}"`**, ne `term_en`: stejné
  jméno může být v `places` i `terms`.
- **Obálka odpovědi je objekt:** `{"proposals": [{"id": ..., "cz": ...}]}`;
  `parsing.extract_json` umí regexem `\{.*\}` vytáhnout jen objekt.
- **Validace:** duplicitní `id` → `ValueError`; cizí `id` se ignoruje a nahlásí;
  `cz` musí být `str` nebo `null`.
- **Chybějící `id` != `cz: null`.** Explicitní `null` = „model termín nezná" →
  `unresolved`. Chybějící položka = model na ni zapomněl → **selhání položky**,
  převezme se předchozí nález jako `stale`.
- **Chyby:** `OutputTruncated` → jeden pokus s dvojnásobným `max_tokens`, pak
  dávka `failed`. Neparsovatelná odpověď, `ValueError` z validace a síťové či
  limitní výjimky, které `AnthropicClient` nepřevádí na `FatalRunError`
  (`APIConnectionError`, `RateLimitError`, 5xx po vyčerpání SDK retry) → dávka
  `failed`, běh pokračuje. Jen `FatalRunError` ukončí příkaz.

### `src/reference_mine.py`

```python
Finding = TypedDict("Finding", {
    "id": str,
    "section": str,            # characters | places | terms
    "surface": str,
    "cz": str | None,
    "klasifikace": str,        # confirmed | weak | proposed | not_attested
                               #   | compound | unresolved
    "primary_attested": bool,  # řídí předvyplnění
    "navrh": str | None,
    "hits": int,
    "books": list[int],
    "per_form": dict,
    "cooccurrence": list[int],
    "matched_en": str | None,
    "matched_cz": str | None,
    "stale": bool,
    "source": str,             # kept | proposed | compound
})

ResolveResult = TypedDict("ResolveResult", {
    "findings": list[Finding],
    "attempted": list[str],
    "failed": list[str],
    "missing_response": list[str],
    "not_attempted": list[str],
})
```

- `resolve(corpus, surfaces, client_factory, cfg) -> ResolveResult`
- `write_reference(result, path, run_id, fingerprint, source_root)` - atomicky
  (temp + `os.replace`). **Stavový automat pro každé `id` v aktuálním draftu:**

  | Stav v tomhle běhu | Zápis |
  |---|---|
  | vyřešeno stupněm 0 | nový nález nahradí starý |
  | `compound` (přeskočeno) | nový nález třídy `compound` |
  | posláno modelu, odpověď platná | nový nález nahradí starý |
  | dávka `failed` nebo chybí v odpovědi | předchozí nález s `stale: true` |
  | nezkoušeno kvůli `--limit` | předchozí nález beze změny |
  | bez předchůdce v těchto případech | `unresolved`, ale zůstává v `coverage` |
  | `id` už není v draftu | **odstraní se** |

- `write_report(final_payload, path, run_id)` - **až po** datech a z **finálního
  slitého payloadu**, ne z `ResolveResult`; jinak by report tvrdil `unresolved`
  tam, kde se převzal starší nález. Report je odvoditelný artefakt, ne
  transakční partner dat: pád mezi dvěma `os.replace` vyrobí „data nová, report
  starý", takže atomicita přes dva soubory by byla lež. Neshoda `run_id` znamená
  „zastaralý, spusť znovu".

### Schéma `data/reference.json`

```json
{
  "schema_version": 1,
  "run_id": 7,
  "source_root": "C:/.../Turn Coat/Reference",
  "fingerprint": {
    "draft": "sha1 klíčů a aliasů z guide.draft.json",
    "corpus": "sha1 manifestu",
    "thresholds": "sha1 hodnot REFERENCE_* z config"
  },
  "coverage": {
    "attempted": ["terms/white council"],
    "failed": ["terms/warlock"],
    "missing_response": ["terms/threshold"],
    "skipped_by_limit": ["terms/nevernever"]
  },
  "findings": [ { "...Finding..." } ]
}
```

`source_root` je **skutečně použitý kořen**, ne hodnota z konfigurace. Bez něj by
`reference --dir CESTA` (jednorázový override) zůstal `review` neznámý a při
výchozím `REFERENCE_DIR=""` by čerstvá těžba vyšla jako zastaralá.

`coverage` odlišuje čtyři důvody, proč položka nemá nález: model řekl „neznám"
(`attempted` + `unresolved`), dávka selhala (`failed`), model položku vynechal
(`missing_response`), nebo se nezkoušela (`skipped_by_limit`).

`load_reference(path) -> dict | None`:
- soubor neexistuje → `None`
- nečitelný JSON, neznámá `schema_version`, **nebo porušení schématu** (špatné
  typy, duplicitní `id`, neznámá sekce či třída, chybějící povinné pole) →
  `None` + varování. Validuje se celý dokument; syntakticky platný soubor se
  špatnými typy by jinak spadl až v `merge_sources` nebo v UI.

### Rozšíření `src/guide.py`

`merge_draft_and_guide` dnes zahazuje draftové `cz` a `render` (`guide.py:93`
čte `g.get("cz") or ""`, `:111` jen `suggested_cz`), takže by se vytěžená hodnota
do UI nedostala.

**Změna:** `merge_sources(draft, guide, reference=None) -> dict`, přednost
`guide` > `reference` > `draft`. U položky blok:

```json
"reference": {"klasifikace": "...", "primary_attested": true, "hits": 0,
              "books": [], "per_form": {}, "matched_en": "...",
              "matched_cz": "...", "navrh": "...", "cooccurrence": [],
              "stale": false, "draft_fresh": true, "corpus_fresh": true,
              "thresholds_fresh": true}
```

- **Čerstvost omezuje výhradně hodnoty a důkazy pocházející z `reference`.**
  Uložená lidská rozhodnutí z `guide.json` platí vždy a priorita
  `guide > reference > draft` zůstává.
- Předvyplnění z reference i číselné důkazy se použijí **jen když sedí všechny
  tři příznaky**; jinak se zobrazí pouze poznámka, že existuje nález z jiného
  běhu. Skrýt čísla a hodnotu ponechat nestačí: opakovaný `scan` může změnit
  aliasy při zachovaném hlavním klíči.
- **Odkud se otisky berou při `review`:** draft a prahy jsou levné. Korpusový
  otisk se sestaví `reference.build_manifest(source_root)`, kde `source_root`
  pochází **ze souboru `reference.json`**, ne z konfigurace. Porovnávat otisk
  proti manifestu uloženému v cache nestačí - to jsou dva historické údaje
  a pozdější změnu EPUBů neodhalí. Není-li `source_root` dostupný, je
  `corpus_fresh` **`unknown`** a chová se jako `false`.
- **Vazba důkazu na hodnotu** platí jen tam, kde je `cz` předvyplněné: liší-li
  se zobrazované `cz` od `matched_cz`, číselný důkaz se vynechá. Klasifikace
  a `navrh` se zobrazují vždy.

`merge_draft_and_guide` zůstane tenkým obalem (`reference=None`).

`normalize_key` se stěhuje do `textnorm`; `guide.normalize()`
(`strip().lower()`) zůstává beze změny kvůli `relationship_key`, aby se
nezměnily existující klíče vztahů.

## Chyby

| Situace | Reakce |
|---|---|
| chybí složka referencí / prázdná | `FatalRunError`, exit 1, soubor beze změny |
| méně než 3 spárované díly | `ValueError` → `_cmd_reference` → `FatalRunError` |
| duplicitní číslo dílu na jedné straně | `ValueError` → `FatalRunError` |
| jednotlivý EPUB se nenačte | přeskoč, nahlas, pokračuj |
| nespárovaný díl | přeskoč, nahlas |
| dávka selže | `failed`, převezme se předchozí nález, běh pokračuje |
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
`config.REFERENCE_PATH`; kořen korpusu si UI vezme ze `source_root` uvnitř
souboru, takže se `reference_dir` nemusí protahovat třemi vrstvami.

- `GET /api/guide` volá `merge_sources(draft, guide, load_reference(path))`
- **POST v tomto pořadí:**
  1. rozbal složené položky a přemapuj/zahoď jejich `must_decide`
  2. **`_check_must_decide_answered`** - kontrola nezodpovězených otázek
  3. `apply_must_decide`
  4. `validate`
  5. odstraň bloky `reference`
  6. `save_guide`

  Krok 2 nesmí zmizet ani se posunout za krok 3: `apply_must_decide`
  (`server.py:43`) prázdné odpovědi **přeskočí** a na konci celý seznam vymaže,
  takže by je pozdější `validate` už neviděla a nezodpovězená otázka by tiše
  propadla. Dnešní kód to má správně (`server.py:122` před `:125`).
  Dnes `server.py:129` ukládá celý payload, takže by metadata skončila
  v `guide.json` mezi lidskými rozhodnutími a po dalším běhu zastarala.
- validace odmítne payload s klíčem obsahujícím `/` nebo `" or "` a payload
  s kolizí povrchu proti aliasu jiné položky (rozhodnutí 6)

Formulář:
- **Rozdělit ručně** (`compound`) nahoře, s předvyplněnými variantami
- **Potvrzeno referencemi** (`confirmed`), sbalené, s počtem
- `weak` rozbalené s důkazem; alias-only `weak` s prázdným polem
- `proposed` a `not_attested` s prázdným polem a návrhem vedle
- `unresolved` **není jeden stav.** Podle `coverage` se rozliší čtyři důvody
  a každý má vlastní hlášku: „model termín nezná" (`attempted`), „dávku se
  nepodařilo zpracovat" (`failed`), „model položku vynechal"
  (`missing_response`), „nezkoušeno kvůli `--limit`" (`skipped_by_limit`).
  Bez toho by prázdné pole tvrdilo „nic se nenašlo" i tam, kde se nehledalo.
- `stale` a nečerstvé viditelně odlišené
- pole zůstávají editovatelná - ruka člověka vyhrává vždy

Chybějící blok `reference` nesmí UI rozbít.

## CLI a konfigurace

```
python main.py reference [--dir CESTA] [--refresh-cache] [--limit N]
```

`--limit N` omezí **jen stupeň 1** (počet povrchů poslaných modelu); stupeň 0 je
zdarma a deterministický. Příkaz patří do `_MUTATING`, lifecycle
`create_run` / `finish_run` jako `scan`, cost guard `interactive=False`.
Pořadí: `scan` → `reference` → `review`.

| Klíč | Výchozí | K čemu |
|---|---|---|
| `REFERENCE_DIR` | `""` (nutno `--dir`) | kořen se složkami `EN/` a `CZ/` |
| `REFERENCE_PATH` | `data/reference.json` | výsledek těžby |
| `REFERENCE_CACHE_PATH` | `data/reference_corpus.json` | předžvýkaný korpus |
| `REFERENCE_REPORT_PATH` | `data/reference_report.md` | souhrn |
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
2. **Matcher - eval fixture:** >=40 anotovaných dvojic, 100 % na negativní
   množině, >=90 % na pozitivní; celá tabulka z rozhodnutí 4; `Za-Lord`
   a `Listens-to-Wind` s pomlčkou; velikost písmen zachována; výpis zachycených
   tvarů pro 20 dotazů na skutečném korpusu.
3. **Složené položky a pořadí POSTu:** `White Court / Red Court / Vampire
   Courts` dostane `compound`, těžba ji přeskočí; POST ji rozbalí **před**
   `apply_must_decide`; **nezodpovězená `must_decide` po rozbalení musí payload
   odmítnout** (regrese: `apply_must_decide` prázdné odpovědi přeskočí a seznam
   vymaže, takže kontrola nesmí přijít až po ní); otázka
   `scope_key = "naagloshii/skinwalker"` se přemapuje na variantu, kterou
   payload výslovně určí, i když člověk ponechá obě; validace odmítne zbylý
   klíč se `/`.
4. **Kolize identity:** ruční položka `Billy` proti existujícímu aliasu
   `Billy Borden` → **chyba validace**, ne tiché sloučení ani přepsání;
   `seed_from_guide` guard nepřepíše `canonical_en` řádku nalezeného jen
   přes alias.
5. **Identita vstupu:** položka s prázdným klíčem se přeskočí, duplicitní
   `(section, normalize_key)` se sloučí včetně aliasů a poznámek, sloučení se
   nahlásí.
6. **Korpus:** párování dílů, odmítnutí duplicitního čísla i malého korpusu,
   `stole` skončí nejvýš `weak`, `Mab` (3 znaky) smí být `confirmed`,
   sjednocení rozsahů u `Harry Dresden`/`Dresden`, alias-only →
   `primary_attested = false` a **žádné předvyplnění**, pravidlo o začátku věty
   včetně hranice dokumentů, cache round-trip a invalidace.
7. **Agent:** dávkování, obálka `{"proposals":[...]}`, párování přes `id`,
   duplicitní `id` → `ValueError`, cizí `id` se ignoruje, chybějící `id` →
   `stale`, explicitní `null` → `unresolved`, `OutputTruncated` → pokus
   s dvojnásobkem, síťová výjimka → `failed`.
8. **Orchestrace:** všechny třídy včetně `compound`, hraniční testy souvýskytu
   (přesně na poměru, těsně pod, prázdné `E`), selhaná dávka → `stale`,
   `--limit` nesmaže položky mimo limit a zapíše se do `coverage`, UI rozliší
   všechny čtyři důvody prázdné položky (`attempted` / `failed` /
   `missing_response` / `skipped_by_limit`), zmizelý
   povrch se odstraní, prahy jen z primárního tvaru, report z finálního payloadu.
9. **Slití:** přednost `guide` > `reference` > `draft`; číselný důkaz se vynechá
   při neshodě `cz`/`matched_cz`; kterýkoli příznak čerstvosti nepravdivý →
   nepředvyplní se nic **z reference**, ale lidská rozhodnutí zůstanou;
   nedostupný `source_root` → `corpus_fresh` je `unknown`; poškozený
   `reference.json` UI neshodí.
10. **End-to-end:** `reference.json` → `GET /api/guide` → POST → `guide.json` →
   `glossary.seed_from_guide`. Musí prokázat, že metadata přežijí slití, že se
   `proposed`/`not_attested`/alias-only **nemůže** dostat do glosáře bez ručního
   vypsání, že postava bez doložení neprojde bez aktivní volby `render`, a že
   `guide.json` po POSTu neobsahuje blok `reference` ani složený klíč.

## Otevřené otázky k ověření prvním během

- Kolik ze 132 povrchů vyřeší stupeň 0 a kolik stupeň 1?
- Jak často skončí návrh jako `not_attested`? Vysoké číslo = model českou edici
  nezná a stupeň 2 bude nutný.
- Sedí prahy 5 výskytů / 2 díly, nebo je většina nálezů těsně pod nimi?
- Kolik návrhů projde výskytem, ale spadne na souvýskytu?
- Kolik falešných shod vyrobí zvolený matcher na skutečném korpusu?
