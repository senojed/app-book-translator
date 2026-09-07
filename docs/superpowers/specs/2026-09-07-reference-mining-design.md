# Těžba terminologie z profesionálních překladů - design

Datum: 2026-09-07
Stav: po kole 3 oponentury (Codex + Claude)
Navazuje na: `2026-09-06-book-translator-design.md`

## Kontext a cíl

Turn Coat je jedenáctý díl Dresden Files. Prvních deset dílů vyšlo česky
v profesionálním překladu. Čtenář, který je přečetl, zná zavedenou terminologii
a jména; překlad jedenáctky, který si vymyslí vlastní, je pro něj horší, i kdyby
byl sám o sobě dobrý. **Návaznost na zavedenou terminologii je hlavní důvod,
proč tenhle nástroj vzniká.**

Scout po `scan` navrhl 121 povrchů (54 postav, 59 termínů, 19 míst). Bez
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
- Vlastní morfologie češtiny - používá se kmenové porovnání, které už
  `concordance` má

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
znamená „v tomhle tvaru nedoloženo", ne „model se plete". Aby falešných nálezů
bylo co nejmíň, hledá se na CZ straně přes **existující**
`concordance.find_form_occurrences`, které porovnává na kmeni a běžné skloňování
snese. Vlastní morfologie se nestaví.

### 4. Pravidla hledání a falešné shody

Pokus ukázal past: `stole` má v referencích 79 výskytů v 10/10 dílech - je to
ale český lokativ slova *stůl* (*na stole*), ne ponechaný anglický termín.
Povrch `stole` v draftu scouta skutečně je (ve významu „štóla").

**Case-sensitivita to neřeší** a starší verze specu se v tom mýlila: české „na
stole" je malými písmeny, takže case-sensitive dotaz ho najde stejně. Jediná
spolehlivá obrana je nedůvěřovat automatu u obecných slov.

**Pravidla** (platí pro obě strany korpusu):

- Text i dotaz se normalizují přes `textnorm.normalize_key()` (NFC, `casefold`,
  zúžení bílých znaků).
- Dotaz se escapuje (`re.escape`), hranice slova přes `\b` s `re.UNICODE`.
  Víceslovný povrch se hledá jako posloupnost slov oddělená bílým znakem;
  apostrof a pomlčka uvnitř povrchu jsou součástí slova, ne hranicí
  (`Listens-to-Wind`, `Za-Lord`).
- **Velké počáteční písmeno** (vlastní jméno): case-insensitive, `confirmed`
  povoleno od 3 znaků výš.
- **Malé počáteční písmeno** (obecné slovo): case-sensitive a **nikdy
  nedosáhne `confirmed`** - končí nejvýš `weak`. Case-sensitivita je slabý
  filtr, ne záruka.
- 1-2 znaky se nehledají vůbec (`hits = 0` → `unresolved`).
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
- **`confirmed` vyžaduje doložení primárního povrchu.** Je-li doložen jen alias,
  třída je `weak` a v důkazu je uvedeno, který tvar zabral (`matched_en`).

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
| `src/reference.py` | EPUBy přes `ingest`, hledání přes `concordance`, `textnorm` | LLM, DB, `guide` |
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
- `count_en_surface(corpus, surface) -> Evidence` - hledá anglický povrch v CZ
  textu dle rozhodnutí 4.
- `count_cz_form(corpus, form) -> Evidence` - hledá český tvar v CZ textu přes
  `concordance.find_form_occurrences` (kmenové porovnání, snese skloňování).
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
  ignoruje se a nahlásí; `id` z dotazu chybějící v odpovědi → `unresolved`;
  `cz` musí být `str` nebo `null`, jinak `ValueError`.
- **Chyby:** `OutputTruncated` → jeden pokus s dvojnásobným `max_tokens`, pak se
  dávka označí jako `failed`. Neparsovatelná odpověď i `ValueError` z validace →
  dávka `failed`, běh pokračuje další dávkou.

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
  atomicky (temp + `os.replace`). Slévání s předchozím souborem:
  - `attempted` a úspěšné → nový nález nahradí starý
  - `failed` a `not_attempted` → **převezme se předchozí nález** s `stale: true`;
    bez předchůdce zůstává `unresolved`
  - id, které v aktuálním draftu už není → **odstraní se**
  Bez toho by `--limit N` smazal položky mimo limit a přechodná chyba dávky by
  zahodila dříve platné nálezy.
- `write_report(result, path, run_id)` - zapisuje se **až po** datech.
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
  "findings": [ { ...Finding... } ]
}
```

`load_reference(path) -> dict | None`:
- soubor neexistuje → `None` (běh bez těžby je legitimní)
- nečitelný JSON nebo neznámá `schema_version` → `None` + varování na stdout;
  poškozený soubor nesmí shodit `review`
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
              "cooccurrence": [], "stale": false, "fresh": true}
```

- `fresh = false`, neodpovídá-li fingerprint draftu aktuálnímu draftu. Pak se
  **číselné důkazy nezobrazí** a položka se označí jako z jiného běhu.
  Opakovaný `scan` může změnit klíče i aliasy; `run_id` čerstvost neprokazuje.
- **Vazba důkazu na hodnotu** platí jen pro `confirmed` a `weak` (tedy tam, kde
  je `cz` předvyplněné): liší-li se zobrazované `cz` od `matched_cz`, číselný
  důkaz se vynechá. Klasifikace a `navrh` se zobrazují vždy - u `proposed` /
  `not_attested` je `cz` prázdné záměrně a podmínka by tam metadata vždy zahodila.

`merge_draft_and_guide` zůstane tenkým obalem (`reference=None`), aby stávající
testy a volání platily.

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
- obě signatury dostanou `reference_path: str | None = None` (výchozí `None`
  drží zpětnou kompatibilitu se stávajícími testy)
- `GET /api/guide` volá `guide.merge_sources(draft, guide, load_reference(path))`
- `_cmd_review` předá `config.REFERENCE_PATH`
- **POST metadata odstraní.** Dnes `server.py:129` ukládá celý payload včetně
  bloků `reference`; ty by zůstaly v `guide.json` mezi lidskými rozhodnutími a
  po dalším běhu těžby zastaraly. Server je před uložením odstraní.
- **Postavy bez doložení vyžadují aktivní volbu `render`** (viz rozhodnutí 2);
  validace odmítne uložení, dokud člověk nerozhodne.

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
2. **Korpus:** párování dílů, odmítnutí duplicitního čísla i malého korpusu,
   `stole` skončí nejvýš `weak` i při stovkách výskytů, `Mab` (3 znaky, velké
   písmeno) smí být `confirmed`, sjednocení rozsahů u překryvu
   `Harry Dresden`/`Dresden` (žádné dvojí započtení), doložený jen alias →
   `weak` s `matched_en`, pravidlo o začátku věty včetně hranice dokumentů,
   escapování metaznaků, pomlčka uvnitř povrchu, cache round-trip a invalidace.
3. **Agent (fake klient):** dávkování, obálka `{"proposals":[...]}`, párování
   přes `id` (stejný `term_en` ve dvou sekcích se nesplete), duplicitní `id` →
   `ValueError`, cizí `id` se ignoruje, chybějící → `unresolved`,
   `OutputTruncated` → jeden pokus s dvojnásobkem, pak `failed`.
4. **Orchestrace (fake klient, mini korpus):** pět tříd, `proposed`/`not_attested`
   nechávají `cz` prázdné, hraniční testy souvýskytu (přesně na poměru, těsně
   pod, prázdné `E`), skloňovaný tvar se díky `concordance` najde (nespadne do
   `not_attested`), selhaná dávka převezme předchozí nález s `stale`,
   `--limit` nesmaže položky mimo limit, zmizelý povrch se odstraní.
5. **Slití (`merge_sources`):** přednost `guide` > `reference` > `draft`;
   číselný důkaz se vynechá při neshodě `cz`/`matched_cz`, klasifikace a `navrh`
   zůstanou; `fresh: false` při změněném fingerprintu; volání bez reference se
   chová jako dnes; poškozený `reference.json` UI neshodí.
6. **End-to-end invariant:** `reference.json` → `GET /api/guide` → POST →
   `guide.json` → `glossary.seed_from_guide`. Musí prokázat, že metadata přežijí
   slití, že se `proposed`/`not_attested` **nemůže** dostat do glosáře bez
   ručního vypsání, že **postava bez doložení neprojde bez aktivní volby
   `render`**, a že `guide.json` po POSTu neobsahuje žádný blok `reference`.

## Otevřené otázky k ověření prvním během

- Kolik ze 121 povrchů vyřeší stupeň 0 a kolik stupeň 1?
- Jak často skončí návrh jako `not_attested`? Vysoké číslo = model českou edici
  nezná a stupeň 2 bude nutný.
- Sedí prahy 5 výskytů / 2 díly, nebo je většina nálezů těsně pod nimi?
- Kolik návrhů projde výskytem, ale spadne na souvýskytu? Měří užitečnost filtru.
- Jak často kmenové porovnání `concordance` zachrání skloňovaný tvar, který by
  přesné hledání označilo za nedoložený?
