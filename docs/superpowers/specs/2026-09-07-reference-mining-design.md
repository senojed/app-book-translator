# Těžba terminologie z profesionálních překladů - design

Datum: 2026-09-07
Stav: po kole 1 oponentury (Codex + Claude)
Navazuje na: `2026-09-06-book-translator-design.md`

## Kontext a cíl

Turn Coat je jedenáctý díl Dresden Files. Prvních deset dílů vyšlo česky
v profesionálním překladu. Čtenář, který je přečetl, zná zavedenou terminologii
a jména; překlad jedenáctky, který si vymyslí vlastní, je pro něj horší, i kdyby
byl sám o sobě dobrý. **Návaznost na zavedenou terminologii je hlavní důvod,
proč tenhle nástroj vzniká.**

Scout po `scan` navrhl 121 povrchů (54 postav, 59 termínů, 19 míst - po odečtení
víceznačných). Bez referencí na všech odpovídá člověk ručně nebo se hádá.

**Cíl:** před fází `review` předvyplnit návod tím, co je **doložitelné**
z profesionálních překladů, a u každé položky ukázat důkaz.

**Invariant, který nesmí padnout:** do glosáře se nesmí dostat termín, který si
model vymyslel a není doložený v žádném českém textu. Invariant je vynucen
mechanicky (prázdné pole), ne kázní uživatele - viz rozhodnutí 2.

## Zdrojová data

`<Reference>/EN/*.epub` a `<Reference>/CZ/*.epub`, deset dílů, párované číslem
dílu v názvu souboru. Ověřeno: všech 20 souborů se načte stávajícím
`ingest.load_book`; EN korpus ~1 200 000 slov, CZ ~972 000 slov. Vnitřní členění
EPUBů se mezi jazyky liší (díl 1: EN 27 dokumentů, CZ 5; díl 2: EN 1 dokument),
takže **kapitoly na sebe nesedí**. Návrh proto na zarovnání kapitol nespoléhá a
pracuje s dílem jako s jedním textem.

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

## Zásadní rozhodnutí

### 1. Výsledek těžby žije ve vlastním souboru, ne v draftu

Původní varianta obohacovala `guide.draft.json`. Zamítnuto: `main.py:105` volá
`save_draft(GUIDE_DRAFT_PATH, result)` a přepíše draft **celý**, takže opakovaný
`scan` by těžbu tiše smazal.

**Zvoleno:** těžba zapisuje `data/reference.json` (nový soubor, `scan` na něj
nesahá). Podklad pro UI vzniká až slitím tří zdrojů v `guide.merge_draft_and_guide`:
`guide.json` (člověk) > `reference.json` (těžba) > `guide.draft.json` (scout).

Vedlejší přínosy: opakovaná těžba je triviálně idempotentní (soubor se nahradí
celý), provenience je oddělená od dat scouta, a `note` se nemodifikuje vůbec -
odpadá donekonečna přirůstající text při opakovaných bězích.

### 2. Nic neobchází review a neověřené nemá hodnotu

`reference` needituje glosář. Glosář se plní beze změny cestou `review` →
`guide.json` → `glossary.seed_from_guide`.

Samotné zvýraznění barvou ale neověřený návrh nezastaví: validace kontroluje jen
neprázdnost pole, takže vyplněná vymyšlenina by se uložením dostala do glosáře.

**Zvoleno:** u třídy `proposed` zůstává `cz` **prázdné**. Návrh modelu se ukazuje
jen jako text vedle pole („model navrhuje: Bílá rada - v referencích nedoloženo")
a člověk ho musí opsat nebo napsat vlastní. Invariant tak drží mechanicky.

### 3. Model navrhuje, ale globální výskyt není důkaz vazby

Původní znění tvrdilo „rozhoduje korpus". To bylo příliš silné: `Rada` je běžné
české slovo a jeho četnost o vazbě na *White Council* nevypovídá nic. Totéž platí
pro anglické homografy na CZ straně.

**Zvoleno, dvě opatření:**

- Třída `confirmed` smí vzniknout **jen ze stupně 0** - anglický povrch doslova
  v českém textu je přímý důkaz, že ho překladatel ponechal. Návrh modelu se
  `confirmed` nikdy nestane.
- Návrh modelu se navíc testuje na **souvýskyt**: v kolika dílech se navržený
  český tvar vyskytuje na CZ straně *a zároveň* je v témže dílu na EN straně
  příslušný anglický termín. Souvýskyt vazbu neprokazuje, ale vyvrací ji, když
  chybí - to stačí na odlišení `proposed` od `contradicted`.

### 4. Falešné shody a pravidla hledání

Pokus ukázal past: hledání `stole` bez ohledu na velikost písmen našlo 79 výskytů
v 10/10 dílech - jenže to je český lokativ slova *stůl*, ne ponechaný termín.

**Pravidla hledání** (platí pro obě strany korpusu):

- Text i dotaz se normalizují na Unicode NFC.
- Hranice slova se hledají přes `regex` s `\b` a `re.UNICODE`; víceslovný povrch
  se hledá jako posloupnost slov oddělená libovolným bílým znakem.
- Povrch začínající **velkým** písmenem (vlastní jméno): hledá se
  case-insensitive.
- Povrch začínající **malým** písmenem (obecné slovo): hledá se
  **case-sensitive**.
- Délka povrchu: 1-2 znaky se nehledají vůbec (`hits = 0`, třída `unresolved`).
  3-4 znaky se hledají, ale nikdy nedosáhnou třídy `confirmed` - jdou nejvýš do
  `weak`. 5+ znaků bez omezení.
- Povrch kratší než 5 znaků musí mít alespoň jeden výskyt **mimo začátek věty**,
  jinak se nepočítá. Chrání před jmény, která jsou zároveň českými slovy
  (`Bob` na začátku věty vs. luštěnina).

## Stupně řešení

Pouštějí se v pořadí, každý pracuje jen s tím, co předchozí nevyřešil.

**Stupeň 0 - ponecháno anglicky (zdarma, bez API).**
Anglický povrch se hledá v CZ korpusu podle pravidel z rozhodnutí 4. Nalezen
dostatečně často → překladatelé ho ponechali → `cz = anglický povrch`,
u postav `render = keep`. Jediný stupeň, který smí dát `confirmed`.

**Stupeň 1 - návrh modelem + ověření (~$0.10-0.20, počáteční odhad, neměřeno).**
Nevyřešené povrchy jdou po dávkách (~30) agentovi `lexicographer`. Vrátí
`{term_en, cz | null}`. Každý návrh se ověří v CZ korpusu a otestuje na
souvýskyt podle rozhodnutí 3.

**Stupeň 2 - poziční zarovnání (nestaví se).**
Seam: `reference_mine.resolve(corpus, surfaces, ...) -> list[Finding]`. Další
stupeň je další funkce se stejným tvarem vstupu i výstupu.

## Klasifikace nálezu

| Třída | Vzniká z | Podmínka | `cz` předvyplněno | Chování v UI |
|---|---|---|---|---|
| `confirmed` | stupeň 0 | ≥ `REFERENCE_MIN_HITS` výskytů ve ≥ `REFERENCE_MIN_BOOKS` dílech, povrch ≥ 5 znaků | ano | sbaleno |
| `weak` | stupeň 0 | nalezeno, ale pod prahem nebo povrch 3-4 znaky | ano | rozbaleno, s důkazem |
| `proposed` | stupeň 1 | model navrhl, tvar v CZ korpusu doložen, souvýskyt sedí | **ne** | návrh vedle pole, pole prázdné |
| `contradicted` | stupeň 1 | model navrhl, ale tvar v korpusu není nebo souvýskyt nesedí | **ne** | návrh vedle pole, výrazně označený jako nedoložený |
| `unresolved` | - | model nenavrhl nic | ne | prázdné, jako dosud |

Výchozí prahy v `config.py`: `REFERENCE_MIN_HITS = 5`, `REFERENCE_MIN_BOOKS = 2`.
Jsou to **počáteční odhady bez měření**; první běh je má potvrdit nebo posunout.
Práh rozhoduje jen o rozdílu `confirmed` / `weak`, tedy o míře zvýraznění -
nerozhoduje o tom, co obejde člověka, protože neobchází ho nic.

## Moduly a hranice

| Modul | Zná | Nezná |
|---|---|---|
| `src/reference.py` | EPUBy přes `ingest`, počítání výskytů v textu | LLM, DB, `guide` |
| `src/agents/lexicographer.py` | prompt → klient → parsování | korpus, DB, soubory |
| `src/reference_mine.py` | drátuje korpus + agenta + `reference.json` | DB, glosář |
| `src/guide.py` (rozšíření) | slití tří zdrojů pro UI | LLM, korpus |
| `main.py` (`reference`) | parsuj, zavolej, vypiš | vše ostatní |

### `src/reference.py`

```python
@dataclass
class Evidence:
    hits: int            # výskytů celkem
    books: list[int]     # čísla dílů, kde se vyskytuje
    matched: str         # tvar, na který se ptalo (kvůli vazbě důkazu na hodnotu)

@dataclass
class Corpus:
    cz: dict[int, str]   # číslo dílu -> celý text
    en: dict[int, str]
```

- `load_corpus(root) -> Corpus` - najde `EN/` a `CZ/`, spáruje podle čísla
  (`^(\d+)` u CZ, `#(\d+)` nebo `Book (\d+)` u EN). **Duplicitní číslo dílu na
  téže straně je chyba** (`ValueError`) - tiché přepsání klíče by zkreslilo
  důkaz. Nespárovaný díl (chybí protějšek) se přeskočí a nahlásí. Méně než
  `REFERENCE_MIN_CORPUS_BOOKS` (výchozí 3) spárovaných dílů → `ValueError`;
  na dvou dílech nelze smysluplně tvrdit `confirmed`.
- `count(corpus, surface, side="cz") -> Evidence` - dle pravidel rozhodnutí 4.
- `cooccurrence(corpus, en_surface, cz_form) -> list[int]` - čísla dílů, kde je
  `cz_form` na CZ straně a zároveň `en_surface` na EN straně.
- `save_cache(corpus, path)` / `load_cache(path, root) -> Corpus | None` -
  cache nese `schema_version`, normalizovaný `root` a pro každý soubor
  `(cesta, velikost, mtime)`. Neshoda v čemkoli → cache se ignoruje a staví se
  znovu. Načtení 20 EPUBů trvá ~30 s, proto to stojí za to.

### `src/agents/lexicographer.py`

- `SYSTEM_PROMPT` - "jsi znalec české edice této série; vrať zavedený český tvar;
  **když termín neznáš, vrať null - nehádej**".
- `propose(terms, client, *, model, max_tokens) -> list[dict]` - vstup
  `[{term_en, kind, note}]`, výstup `[{term_en, cz | None}]`.
- **Obálka odpovědi je objekt**, ne seznam: `{"proposals": [...]}`. Sdílený
  `parsing.extract_json` umí regexem `\{.*\}` vytáhnout jen objekt, seznam by
  neprošel. Neparsovatelná odpověď → `ValueError`; volající dávku přeskočí a
  pokračuje další.

### `src/reference_mine.py`

```python
Finding = TypedDict("Finding", {
    "section": str,        # "characters" | "places" | "terms"
    "key": str,            # normalizovaný primární klíč (viz identita níže)
    "surface": str,        # původní povrch, jak ho napsal scout
    "cz": str | None,      # None u proposed/contradicted/unresolved
    "klasifikace": str,    # confirmed | weak | proposed | contradicted | unresolved
    "navrh": str | None,   # co navrhl model (i když se nepředvyplní)
    "hits": int,
    "books": list[int],
    "cooccurrence": list[int],
    "matched_cz": str | None,  # tvar, ke kterému se důkaz vztahuje
    "source": str,         # kept | proposed
})
```

- **Identita povrchu:** `(section, normalizovaný klíč)`, kde klíč je
  `name_en` (characters, places) resp. `term_en` (terms), normalizovaný přes
  NFC + `casefold()` + zúžení bílých znaků. Aliasy se netěží samostatně - patří
  k primárnímu klíči. Stejný normalizovaný klíč ve dvou sekcích jsou dvě různé
  položky (sekce je součástí identity); v rámci jedné sekce je duplicita chyba
  vstupu a nahlásí se.
- `resolve(corpus, surfaces, client_factory, cfg) -> list[Finding]`
- `write_reference(findings, path)` - `data/reference.json`, atomicky
  (temp + `os.replace`), **nahrazuje soubor celý**.
- `write_report(findings, path)` - `data/reference_report.md`, zapisuje se
  **až po** úspěšném zápisu `reference.json`; nese id běhu.

### Rozšíření `src/guide.py`

`merge_draft_and_guide(draft, guide)` dnes zahazuje draftové `cz` a `render`
(`guide.py:93` čte `g.get("cz") or ""`, `:111` čte jen `suggested_cz`), takže by
se vytěžená hodnota do UI vůbec nedostala.

**Změna:** podpis na `merge_sources(draft, guide, reference=None) -> dict`.
Přednost: `guide` > `reference` > `draft`. U každé položky navíc blok:

```json
"reference": {"klasifikace": "...", "hits": 0, "books": [], "matched_cz": "...",
              "navrh": "...", "cooccurrence": []}
```

Blok se **vynechá**, liší-li se zobrazovaná hodnota `cz` od `matched_cz` -
důkaz posbíraný pro jiný tvar nesmí viset u hodnoty, ke které nepatří.
Stará `merge_draft_and_guide` zůstane jako tenký obal (volá `merge_sources`
s `reference=None`), aby stávající testy a volání platily.

## Chyby

Těžba je **volitelný krok**, ne podmínka běhu.

| Situace | Reakce |
|---|---|
| chybí složka referencí / prázdná | `FatalRunError`, exit 1, `reference.json` beze změny |
| méně než 3 spárované díly | `FatalRunError` - na tak malém korpusu nelze tvrdit `confirmed` |
| duplicitní číslo dílu na jedné straně | `FatalRunError` - dvojznačné číslování zkresluje důkaz |
| jednotlivý EPUB se nenačte | přeskoč, nahlas, pokračuj |
| nespárovaný díl (chybí EN nebo CZ) | přeskoč, nahlas |
| dávka termínů selže (rozbitý JSON) | přeskoč dávku, nahlas, pokračuj další |
| `FatalRunError` z klienta (auth, cost guard) | ukonči příkaz, `reference.json` beze změny |
| chybí `guide.draft.json` | `FatalRunError` s vysvětlením, že má běžet `scan` |

`reference.json` se zapisuje **až na konci**, jedním atomickým zápisem. Report se
zapisuje až po něm. Pád uprostřed nenechá report bez dat ani data bez reportu.

**Co příkaz zapisuje do DB:** jen `runs` (`create_run` / `finish_run`) a
`llm_calls` (přes `PipelineLLMClient`). Tabulek `chapters`, `glossary`,
`questions`, `term_mentions` a `drift_reports` se **nedotkne**. Původní znění
„na databázi nesahá vůbec" bylo nepřesné.

## Review UI

`GET /api/guide` vrací u položek blok `reference`. Formulář podle něj:

- sekce **Potvrzeno referencemi** (`confirmed`) nahoře, sbalená, s počtem položek
- `weak` rozbalené, s důkazem („12× v dílech 3, 5, 7")
- `proposed` a `contradicted` s **prázdným polem** a návrhem vedle něj;
  `contradicted` navíc výrazně označené jako v referencích nedoložené
- pole zůstávají editovatelná - ruka člověka vyhrává vždy

Validace se nemění. Chybějící blok `reference` (běh bez těžby) nesmí UI rozbít -
sekce se pak nezobrazí.

## Testy

1. **Korpus (bez API):** párování dílů, odmítnutí duplicitního čísla, odmítnutí
   příliš malého korpusu, case-sensitive pravidlo (`stole` se jako termín
   nenajde, `Mab` ano), délková pravidla včetně tříznakových povrchů, pravidlo
   o začátku věty, NFC normalizace, cache round-trip a invalidace při změně
   velikosti/mtime/kořene.
2. **Agent (fake klient):** sestavení dávky, parsování obálky `{"proposals":[...]}`,
   `null` jako „neznám", rozbitá dávka → `ValueError` a běh pokračuje.
3. **Orchestrace (fake klient, mini korpus):** klasifikace do pěti tříd,
   `proposed`/`contradicted` nechávají `cz` prázdné, souvýskyt rozhoduje mezi
   nimi, `reference.json` se nahrazuje celý (idempotence), report až po datech.
4. **Slití (`merge_sources`):** přednost `guide` > `reference` > `draft`;
   blok `reference` se vynechá při neshodě `cz` a `matched_cz`; volání bez
   reference se chová jako dnes.
5. **End-to-end invariant:** obohacený `reference.json` → `GET /api/guide` →
   POST → `guide.json` → `glossary.seed_from_guide`. Musí prokázat, že
   metadata přežijí slití a že se `proposed`/`contradicted` **nemůže** dostat
   do glosáře bez toho, aby ho člověk vypsal ručně.

## Otevřené otázky k ověření prvním během

- Kolik ze 121 povrchů vyřeší stupeň 0 a kolik stupeň 1?
- Jak často model navrhne tvar, který korpus nedoloží (`contradicted`)? Vysoké
  číslo = model českou edici nezná a stupeň 2 bude nutný.
- Sedí prahy 5 výskytů / 2 díly, nebo je většina nálezů těsně pod nimi?
- Kolik návrhů projde výskytem, ale spadne na souvýskytu? To měří, jestli má
  souvýskyt jako filtr smysl.
- Jsou falešné shody i jinde než u obecných slov s malým písmenem?
