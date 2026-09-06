# Multiagentní překladač knih - design (pokus 2)

Datum: 2026-09-06
Stav: schváleno, čeká na implementační plán

## Kontext a cíl

Pokus 1 (archivováno v `pokus-1/`) měl kompletní kostru multiagentního CLI
překladače, ale nikdy neběžel proti reálnému API - prompty, kvalita překladu,
cena i chování kritika zůstaly neověřené. Přešlo se z brainstormu rovnou do
kódu bez psaného specu.

Pokus 2 začíná od záměru.

**Dvojí kritérium úspěchu (obojí, ne jedno):**
1. Naučit se postavit reálný multiagentní systém - agenti se musí genuinně
   potřebovat, ne být divadlo.
2. Na konci mít použitelně přeloženou knihu.

**První reálný cíl:** urban fantasy román (Dresden Files), EN→CZ, ~350 stran,
pro vlastní čtení (ne k publikaci).

## Rozsah

### V rozsahu
- Načtení EPUB / TXT, segmentace na kapitoly a scény
- Pre-scan knihy (scout) → draft návodu. Default jedno volání; `scan --chunked`
  fallback (kniha se nevejde do kontextu nebo výstup usekne)
- Review fáze: lokální web UI na potvrzení/úpravu návodu
- Překladová smyčka: translator → kritik → revizor (max N kol) → uložení
- Deterministická kontrola konzistence termínů + drift napříč kapitolami
- Kandidátní vs schválené termíny (translatorem navržený termín není hned závazný)
- Dávkové otázky během běhu (flag-and-continue), příkazy `questions` / `answer`
- Navazatelný běh (SQLite stav, commit po kapitolách)
- Export kapitol do TXT (hotové + označené s markerem)
- Provider vrstva navržená tak, aby šlo přidat dalšího providera (OpenAI)
  malým zásahem - v pokusu 2 implementován jen Anthropic
- Sledování spotřeby tokenů (persistováno po každém volání) + měkký strop nákladů
- UTF-8 stdout (Windows konzole jinak padá na českém výstupu - zkušenost z pokusu 1)

### Mimo rozsah (pokus 2)
- Další LLM provideři (OpenAI, Ollama). Ollama pro literární překlad zamítnuta
  (kvalita malých lokálních modelů nestačí). OpenAI = "později".
- LLM jako orchestrátor (zvážen jako přístup B, zamítnut - viz níže)
- Automatická oprava stylu bez lidského gate za revizní smyčkou
- Export do EPUB (jen TXT)
- Balení do Docker / exe
- Paralelní zpracování kapitol

## Volba architektury

Zvažené přístupy:

- **A - Pipeline specializovaných agentů, orchestrace v kódu.** Pevná sekvence
  na kapitolu (`for` cyklus + revizní smyčka), LLM se volá jen na to, co kód
  neumí. **Zvoleno.**
- **B - LLM jako orchestrátor.** "Vedoucí" agent rozhoduje, kterého sub-agenta
  zavolat. Zamítnuto: pro takhle strukturovaný úkol (kroky jsou vždy stejné:
  přelož → zkontroluj → oprav → ulož) LLM-orchestrátor jen pálí tokeny na
  rozhodnutí, která zvládne `if`; je nepředvídatelný, hůř se ladí a navázání po
  pádu je těžké. Lekce "kdy NEpoužít LLM orchestrátor" je cenná, ale drahá a
  ne pro první multiagentní projekt.
- **C - Minimální (jeden translator + deterministické kontroly).** Zamítnuto:
  míjí učební cíl a kontrola kvality je slabá.

**Proč je A genuinně multiagentní:** nezávislý kritik s odděleným kontextem
(vidí jen EN originál + CZ překlad, ne translatorovo zdůvodnění) chytá jiné
chyby než by chytil translator sám. Revizní smyčka je reálná práce agent
agentovi. Systém učí jádro: specializace rolí, nezávislé ověření, omezená
revizní smyčka, sdílený stav mezi agenty.

## Adresářová struktura

```
book-translator/
├── main.py              # CLI - tenký, jen parsuje a volá
├── config.py            # model IDs, cesty, prahy, MAX_REVIZE, MAX_SPEND_USD
├── pyproject.toml
├── pokus-1/             # archiv (nedotýkat)
├── docs/superpowers/specs/
├── src/
│   ├── ingest.py        # EPUB/TXT → kapitoly; dělení na scény
│   ├── state.py         # SQLite: stav běhu, navazatelnost
│   ├── guide.py         # překladatelský návod (JSON)
│   ├── glossary.py      # glosář termínů (JSON)
│   ├── concordance.py   # deterministická kontrola termínů + drift
│   ├── llm/
│   │   ├── client.py    # rozhraní LLMClient + AnthropicClient
│   │   └── parsing.py   # split_sections(), extract_json()
│   ├── agents/
│   │   ├── scout.py     # pre-scan knihy → draft návodu
│   │   ├── translator.py # překlad kapitoly; čerstvý i revizní režim
│   │   └── critic.py    # nezávislá revize, nálezy se závažností
│   ├── pipeline.py      # orchestrace: sekvence na kapitolu + revizní smyčka
│   └── review_ui/       # lokální web UI pro review fázi (izolované)
└── tests/
```

### Hranice modulů

| Modul | Zná | Nezná | Test |
|---|---|---|---|
| `ingest` | soubor → kapitoly | DB, LLM | vzorové soubory |
| `state` | jen SQLite | LLM, překlad | dočasná DB |
| `guide`, `glossary` | JSON na disku | LLM | přímo |
| `concordance` | text + glosář (čistá logika) | DB, LLM | vzorky |
| `llm/client` | jediné místo co importuje `anthropic` | agenti, pipeline | fake |
| `agents/*` | prompt → volání klienta → parsování | DB, soubory | fake klient |
| `pipeline` | jediné místo co drátuje agenty + stav + glosář | HTTP detaily | fake agenti |
| `review_ui` | `guide.*.json` přes `guide.py` | pipeline, agenti | POST validace |
| `main` | parsuj CLI, zavolej, vypiš | vše ostatní | - |

Revizor není samostatný modul - je to translator v revizním režimu (dostane
navíc EN originál kapitoly, předchozí CZ překlad a nálezy kritika + concordance).
Jeden modul, jedna rodina promptů.

## Fáze běhu (CLI příkazy)

```
python main.py init kniha.epub    # kniha → kapitoly do DB (status pending)
python main.py scan               # scout projede celou knihu → guide.draft.json
python main.py review             # web UI: potvrdíš/upravíš návod → guide.json
python main.py run                # překladová smyčka přes kapitoly
python main.py questions          # otázky nadhozené během běhu
python main.py answer 3 "..."     # odpověď → pravidlo do návodu + přepočet kapitol
python main.py status             # přehled stavu kapitol
python main.py export             # hotové kapitoly → output/kniha_cz.txt
```

### Co dělá `run` na jednu kapitolu

```
1. rozděl na scény (podle prahu slov)
2. translator(scéna, návod, glosář) pro každou scénu → slouč do plného překladu CZ
3. concordance.check_chapter(CZ, glosář) → nálezy (leak / inconsistency)
4. kritik(EN kapitola, CZ) → nálezy se závažností
5. dokud (critical nález kritika  NEBO  concordance leak  NEBO
          inconsistency u schváleného termínu)  a  kolo < MAX_REVIZE:
       findings = kritikovy critical + concordance nálezy (sjednocené do jednoho tvaru)
       translator v revizním režimu(EN kapitola, CZ, findings, návod, glosář) → nový CZ
       concordance.check_chapter znovu
       kritik znovu
       revision_rounds += 1
6. z FINÁLNÍHO překladu:
     - new_terms → glosář jako `candidate` (dedup podle term_en)
     - used_terms (jak byl každý známý termín v kapitole vyrenderován) → tabulka term_mentions
7. otázky z translatora → DB:
     - candidate termín → 1 otázka kind=term, guess_answer=navržený CZ, severity=guess
     - blocking otázka → severity=blocking
   před zápisem mentions: DELETE FROM term_mentions WHERE chapter_idx=? (retranslation)
8. ulož translated_text + revision_rounds + notes(JSON: kritik + concordance) + status:
       flagged        critical/leak nález přežil MAX_REVIZE kol
       needs_human    translator vrátil blocking otázku
       done           jinak (i s odhadnutým jménem / kandidátním termínem)
```

**Které stavy `run` bere do fronty:** `pending` a `error` (error = auto retry).
`needs_human` a `flagged` `run` **přeskočí** (čekají na člověka); vrátí je do
hry `answer` resp. `run --retry-flagged`. Žádná kapitola nezastaví dávku.
Report na konci vypíše přeskočené.

Každých `CROSS_REF_EVERY_N` kapitol: `concordance.check_drift` nad `term_mentions`
hotových kapitol, report do `drift_reports`, CLI vypíše počet nálezů.

Na konci `run`: report - kolik done / flagged / needs_human / error / čekajících
otázek + spotřeba tokenů za běh.

### Stavový automat kapitoly

```
pending ──překlad+kritika──┬──> done
                           ├──> flagged        (critical/leak nález přežil MAX_REVIZE)
                           ├──> needs_human     (blocking otázka)
                           └──> error           (recoverable výjimka)

error       ──běžný `run` (auto retry)──────────────────────> pending
needs_human ──answer (všechny blocking otázky kapitoly)─────> pending  (vždy)
flagged     ──answer (mění-li výsledek) / `run --retry-flagged`──> pending
done        ──answer na guess otázku, když answer ≠ guess───> pending
```

**Requeue po `answer` (přesná pravidla):**
1. zapiš odpověď. U `term`/`name`: povyš glosář `candidate` → `approved`
   (nebo oprav CZ). U `style`: `guide.add_rule()`.
2. **blocking otázka** (kapitola `needs_human`, žádný `guess_answer`): kapitola
   → `pending` VŽDY (původní překlad měl díru).
3. **guess otázka** (kapitola už `done`/`flagged`):
   - `answer` == `guess_answer` → nic, žádný přepočet
   - jinak → `affected_chapters` (kapitoly, jejichž `term_mentions` obsahují
     `scope_key`; u `style` bez scope_key: všechny `done`/`flagged` od kapitoly
     vzniku otázky) přejdou na `pending`
`answer` nikdy nesahá na kapitolu ve stavu `pending` / právě zpracovávanou.

### Export

- `export` zahrne `done` i `flagged` kapitoly (flagged mají nejlepší dostupný
  překlad). Před `flagged` kapitolu vloží řádek `[!! REVIDOVAT: <shrnutí nálezu>]`.
- `needs_human` a `error` kapitoly `export` nahradí `[!! CHYBÍ KAPITOLA N - <důvod>]`
  a vypíše varování na stdout (kniha nemá tiše chybět kapitola).
- `export --only-done` = jen čisté kapitoly; vynechané kapitoly stejně vypíše
  na stdout jako seznam (kniha nemá tiše chybět kapitola).
- `export` je read-only, nemění stav.

## Prostředí

- `main.py` na startu vynutí UTF-8 na stdout/stderr
  (`sys.stdout.reconfigure(encoding="utf-8", errors="replace")` + totéž stderr).
  Windows konzole jinak padá `UnicodeEncodeError` na českém výstupu (zkušenost
  z pokusu 1). Testy i CLI musí projít v `cp1252` konzoli.
- Python 3.11+. Závislosti: `anthropic`, `ebooklib`, `beautifulsoup4`,
  `fastapi`, `uvicorn`; dev: `pytest`.

## Agenti

Všichni: bezstavové funkce `(vstup, LLMClient) → strukturovaný výstup`. Postaví
prompt, zavolají klienta, zparsují. Žádná DB, žádné soubory.

### Scout (`agents/scout.py`)
- **Vstup:** kniha. Default 1 volání (350 stran ~ 130k slov, Sonnet 1M kontext).
- **Výstup (JSON - strukturovaná metadata):**
  ```
  characters:    [{name_en, aliases, suggested: keep|translate, note}]
  places:        [{name_en, suggested_cz, note}]
  terms:         [{term_en, suggested_cz, note}]
  relationships: [{a, b, observed, suggested: tyka|vyka}]
  style_notes:   "1. osoba, min. čas, sarkastický vypravěč, ..."
  must_decide:   [{kind: "term", scope_key: "The White Council",
                   question: "Přeložit nebo ponechat?", default: "ponechat"}]
  ```
- **Useknutý / neúplný výstup u scouta = tvrdá chyba, ne varování.** Částečný
  návod tiše vynechá postavy/termíny a znehodnotí celý běh. Reakce: zvětši
  `max_tokens`, nebo přepni na `--chunked`. Nikdy nepokračovat s částečným JSON.
- **`must_decide` je strukturované, ne volný string:**
  `{kind: "term|name|relationship|style", scope_key, question, default}` - review
  UI podle `kind`/`scope_key` ví, kam odpověď zapsat (postava / termín / vztah /
  pravidlo).
- **`scan --chunked` fallback:** kniha po chuncích (skupiny kapitol) → dílčí
  fakta z každého chunku → `merge_scout_facts()` (deduplikace postav/termínů
  podle jména, sjednocení aliasů, sběr must_decide) → jeden draft návodu.
  Deterministický merge v kódu, ne dalším LLM voláním.
- Model: `claude-sonnet-5`. Před pilotem změřit vstup přes `count_tokens`.

### Translator (`agents/translator.py`) - dva režimy
- **Čerstvý:** scéna (EN) + návod + glosář → překlad scény
- **Revizní:** EN kapitola (celá) + předchozí CZ (celá) + findings (kritik +
  concordance) + návod + glosář → opravený překlad celé kapitoly. EN originál
  je povinný - bez něj revizor neopraví věrnost ani vynechávky.
- **Výstup - oddělovačový formát (próza NIKDY v JSON):**
  ```
  ===PREKLAD===
  <čistý přeložený text>
  ===METADATA===
  {"new_terms":  [{term_en, cz, note, type}],
   "used_terms": [{term_en, cz_form}],   # jak byl každý známý termín vyrenderován
   "questions":  [{"kind": "term|name|relationship|style|other",
                   "scope_key": "term_en / null",
                   "guess_answer": "co translator zvolil / null u blocking",
                   "text": "...", "severity": "guess"|"blocking"}]}
  ```
  `guess` = přeloženo odhadem (má `guess_answer`), zapíše se otázka. `blocking`
  = "fakt nevím" (bez `guess_answer`) → kapitola `needs_human`. `new_terms` jdou
  do glosáře jako `candidate`. `used_terms` z FINÁLNÍHO překladu → `term_mentions`.
- Model: `claude-sonnet-5`. Největší žrout tokenů. `max_tokens` velký (~16000)
  + pojistka na useknutí (translator: useknuto = `error`, viz Chyby).

### Kritik (`agents/critic.py`)
- **Vstup:** EN kapitola + CZ překlad. NE translatorovo zdůvodnění ani metadata.
  Oddělené volání, oddělený kontext.
- **Výstup (JSON):**
  ```
  {"verdict": "pass"|"revise",
   "findings": [{"severity": "critical"|"minor", "cz_excerpt", "issue", "suggestion"}]}
  ```
- Revizní smyčku spouští `critical` nález kritika NEBO concordance `leak` NEBO
  `inconsistency` u schváleného termínu. `minor` se jen zapíše.
- Model: `claude-sonnet-5`.

## Provider vrstva (`llm/client.py`)

```python
class LLMClient(Protocol):
    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion: ...
    def count_tokens(self, *, system: str, user: str, model: str) -> int: ...

@dataclass
class Completion:
    text: str
    truncated: bool        # stop_reason == "max_tokens"
    input_tokens: int
    output_tokens: int
```

- `AnthropicClient` = jediná implementace v pokusu 2, jediný soubor importující
  `anthropic`. `max_retries` nastaveno na SDK klientovi (config, default 8).
  **Zůstává čistý - žádná DB, žádné `run_id`.**
- Agenti klienta dostanou parametrem, nikdy ho nevytváří.
- **Logging spotřeby:** pipeline obalí klienta do `LoggedLLMClient(inner,
  run_id, agent, state)` - ten po každém `complete()` zapíše řádek do
  `llm_calls` (přes `state`). Agenti dostanou obalený klient, nepoznají rozdíl.
  Tak se neporuší hranice modulů a usage přežije pád procesu.
- **Cost guard běží v pipeline PŘED `complete()`:** zavolá `count_tokens()`
  (samostatná metoda, nevolá model), přičte `spent_so_far` z `llm_calls`,
  porovná se stropem.
- **Sonnet 5:** neposílat `temperature` / `top_p` / `top_k` (model non-default
  sampling odmítá 400). Předpoklady o kontextu/výstupu (1M / 128k) ověřit proti
  Anthropic docs a držet v `config.py`, ne v logice.
- **Kam půjde per-provider varianta promptů ("později"):** každý agent bude mít
  `SYSTEM_PROMPTS = {"anthropic": "..."}` klíčováno rodinou providera. V pokusu 2
  jen `"anthropic"`. Zapsáno v designu, nepostaveno.

### Modely (`config.py`, role → model id)
Vše `claude-sonnet-5` (levnější a novější než `claude-sonnet-4-6`).
Později volitelně: translator + kritik na Opus pro kvalitu, scout zůstává Sonnet.

## Deterministické nástroje

### `ingest.py` (portováno z pokusu 1, otestované)
- `load_book(path)` → EPUB (pořadí podle spine, ne manifestu), TXT (regex
  nadpisů "Chapter N" / fallback jeden blok s varováním) → `list[Chapter]`
- `split_into_scenes(text, prah)` → dělení podle oddělovačů scén / prázdných
  řádků, pojistka proti předrobení
- Čisté funkce, `Chapter = dataclass(index, title, raw_text)`

### `guide.py`
- `guide.json` = lidská rozhodnutí:
  ```
  characters:    [{name_en, aliases, render: keep|translate, cz}]
  places:        [{name_en, cz}]
  relationships: [{a, b, address: tyka|vyka}]
  style:         "blok textu → jde do promptu translatora"
  rules:         ["volná pravidla, odpovědi na otázky z běhu"]
  ```
- `guide.draft.json` = výstup scouta (bohatší: note, suggested, must_decide)
- `load_guide()`, `save_guide()`, `guide_as_prompt_block()`, `add_rule()`

### `glossary.py`
- `{term_en: {cz, note, type, status}}`
  - `type`: name | place | term
  - `status`: `seeded` (z návodu), `approved` (člověk potvrdil přes `answer`),
    `candidate` (translator navrhl, nepotvrzeno)
- seed z návodu (keep → cz=term_en, translate → cz=guide.cz; místa, termíny) = `seeded`
- za běhu: `new_terms` z translatora → `candidate` (dedup podle term_en; existující
  se nepřepisuje)
- `as_prompt_block()` řadí `seeded`+`approved` jako závazné, `candidate` uvádí
  zvlášť jako "návrh, může se změnit"
- `add_candidate()`, `promote(term_en, cz)`, `as_prompt_block()`

### `concordance.py` - deterministicky, BEZ LLM
Nahrazuje terminology + cross_reference agenty z pokusu 1. Data bere ze dvou
zdrojů: `translated_text` kapitol (v DB) a tabulky `term_mentions` (plněná
z translatorových `used_terms`).

- **Kontrola kapitoly** (`check_chapter(cz_text, glossary) → list[Issue]`):
  - `leak`: EN podoba termínu je v CZ textu, ale termín se MÁ překládat
    (`cz != term_en`) → critical. Pro `keep` položky (`cz == term_en`) se `leak`
    nikdy nehlásí - tam je EN podoba správně.
  - `inconsistency`: očekávaný CZ tvar (`seeded`/`approved` termín) v kapitole
    chybí, ale je tam jiná známá varianta → critical u `approved`/`seeded`,
    jinak jen otázka
- **Drift napříč kapitolami** (`check_drift(term_mentions, glossary) → report`):
  pro každý `term_en` seskup `cz_form` z `term_mentions` všech `done`/`flagged`
  kapitol; 2+ zjevně různé kmeny (ne jen skloňování stejného slova) → drift nález
  s výčtem kapitol.
- České skloňování: v1 nedělá lemmatizaci. Porovnává na kmeni (slovo bez
  posledních 1-3 znaků) + přesnou shodou. Nejistoty ukáže člověku, tvrdě nepadá.
  LLM soudce ("stejné slovo skloňované?") případně později.
- **Proč kód a ne agent:** vyčerpávající hledání stringů je přesně to, v čem je
  LLM špatný a kód dobrý. Levné, spolehlivé, škáluje na desítky kapitol
  (kniha má typicky 40-60).

## Review UI (`src/review_ui/`)

- `python main.py review` → spustí lokální server (FastAPI + uvicorn, jedno
  statické HTML + vanilla JS, bez build stepu), otevře prohlížeč
- `GET /api/guide` → `guide.draft.json` slitý s `guide.json` (pokud existuje):
  tvá dřívější rozhodnutí mají přednost, nové nálezy scouta se přidají jako
  nepotvrzené. `scan` zapisuje **jen** `guide.draft.json`, nikdy `guide.json`,
  takže opakovaný `scan` nikdy nepřepíše tvoje rozhodnutí.
- `POST /api/guide` → validace, zápis `guide.json`, pak reseed glosáře:
  přegeneruje **jen `seeded`** položky z návodu; `approved` a `candidate`
  (runtime) zůstávají. Konflikt (seeded termín teď koliduje s `approved`):
  `approved` vyhrává (novější lidské rozhodnutí přes `answer`).
- Stránka - sekce formuláře, strukturovaný vstup (roletky, zatržítka - menší
  šance na překlep):
  - **Postavy:** tabulka, řádek = jméno (readonly) + aliasy + roletka
    `ponechat/přeložit` + pole CZ (aktivní u "přeložit") + scoutova poznámka
  - **Místa / Termíny:** termín → CZ (předvyplněno návrhem scouta)
  - **Vztahy:** seznam dvojic co scout viděl interagovat + roletka `tyká/vyká`
    + tlačítko "přidej dvojici"
  - **Styl:** textarea (předvyplněno scoutem)
  - **must_decide:** zvýrazněné nahoře, bez odpovědi nejde uložit
- "Ulož a zavři" → validace (žádné prázdné povinné, must_decide zodpovězeno) →
  zápis `guide.json` → server skončí
- **Izolace:** jádro (pipeline, agenti) `review_ui` nikdy neimportuje. UI sahá
  jen na `guide.*.json` přes `guide.py`.

## Stav a navazatelnost

### `state.py` - SQLite schéma
```
chapters (idx PK, title, raw_text, translated_text, status,
          revision_rounds INTEGER DEFAULT 0, notes TEXT, updated_at)
    status: pending | done | flagged | needs_human | error
    notes: JSON - poslední nálezy kritika + concordance, nebo text chyby

questions (id PK, chapter_idx, kind, text, scope_key, guess_answer,
           severity, answer, resolved_at)
    kind:     term | name | relationship | style | other
    scope_key: term_en (term/name), "a|b" (relationship), null (style/other)
    severity: guess | blocking

term_mentions (id PK, term_en, cz_form, chapter_idx)
    plněno z translatorových used_terms; zdroj dat pro drift check

drift_reports (id PK, up_to_chapter, report TEXT, created_at)

runs (id PK, command, started_at, ended_at, status)
llm_calls (id PK, run_id FK, agent, provider, model, input_tokens, output_tokens,
           estimated_cost_usd, truncated, status, ts)
    zápis po KAŽDÉM volání (přes LoggedLLMClient); cost guard i report čtou odtud
    cena: input_tokens*sazba_in + output_tokens*sazba_out, sazby v config.py
```

**Granularita navázání = kapitola.** Kapitola co spadne na scéně 3 z 5 se
přehraje od scény 1 (přijatelné, kapitola je minuty ne hodiny). `scan` je
idempotentní. `run` commituje po každé kapitole → pád na 47 → `run` naváže od 47.

## Chyby

Klasifikace určuje reakci. **Fatal běhu** = zastav příkaz hned, nesahej na žádnou
kapitolu (nemá smysl vyrábět 45× `error`). **Recoverable kapitoly** = označ tu
jednu `error`, pokračuj další.

| Třída | Co | Reakce |
|---|---|---|
| **Fatal běhu** | chybějící/špatný API klíč (auth error), neznámý model (404), 400 invalid request (špatné parametry), chyba konfigurace, `MAX_SPEND_USD` překročeno | výjimka ukončí příkaz, exit≠0, kapitoly beze změny |
| **API dočasná** | 429, 5xx, timeout | SDK retry (max_retries=8, backoff); po vyčerpání → recoverable |
| **Recoverable kapitola** | retry vyčerpán, neočekávaná výjimka v jedné kapitole | kapitola `error`, `run` pokračuje |
| **Useknutý výstup** | translator | `error` (useknutý překlad = ztráta dat) |
| | kritik | 1× retry s vyšším `max_tokens`; když zas useknuto → kapitola `flagged` (nepředpokládat pass) |
| | scout | **fatal běhu** - viz sekce Scout (částečný návod znehodnotí vše) |
| **Rozbitý výstup agenta** | neparsovatelný | translator → `error`; scout → fatal; kritik → 1× retry, pak `flagged` |
| **Pád procesu** (Ctrl-C, stroj) | | commit po kapitolách → `run` naváže; `scan` běží znovu |

Rozlišení fatal vs recoverable: první volání každého `run`/`scan` je "kanárek" -
selže-li fatal třídou, končíme dřív než se cokoli zapíše.

### Cost guard
- Usage se píše do `llm_calls` po každém volání (přežije pád procesu).
- `config.MAX_SPEND_USD` - platí pro `run` i `scan`. Před každým voláním:
  `spent_so_far` (z `llm_calls`) + `count_tokens` odhad tohoto volání +
  worst-case odhad zbytku (zbývající kapitoly × prům. cena × (1 + MAX_REVIZE))
  > strop → pauza `pokračovat? [y/N]` (u `scan` tvrdě zastav, je to 1 volání).
- Vlastní rate limiter není potřeba (SDK backoff).

## Testy - po vrstvách

1. **Čistá logika (bez API, bez DB):** ingest (dělení kapitol/scén), concordance
   (únik termínu, drift grouping), parsing (`split_sections`, `extract_json`),
   guide/glossary load/save/format. Většina testů. Z pokusu 1 portovat 11.
2. **Stav:** dočasná SQLite, CRUD + přechody (requeue po answer, retry `error`).
3. **Agenti:** fake `LLMClient` s nakonzervovanými odpověďmi. Sestavení promptu +
   parsování výstupu + guess/blocking split. Bez API.
4. **Pipeline:** fake agenti. Revizní smyčka (spustí se na critical, zastaví na
   MAX_REVIZE, zastaví na pass), růst glosáře, logování otázek, izolace chyb.
5. **Pilot (neautomatizované):** jeden reálný `scan` + `run` na 2-3 kapitoly
   s klíčem. Checklist v README. Změří: fungují prompty, kvalita, cena, vydělává
   si multiagent na sebe.
6. **Review UI:** jeden test že POST validuje a zapíše `guide.json`. UI okem.

TDD tam kde se vyplatí: čistá logika + pipeline smyčka (hlavně concordance a
revizní smyčka - test napřed).

## Pořadí stavby

1. Skeleton: `config` (+ UTF-8 stdout), `state` (celé schéma), `ingest`
   (port z pokusu 1) + testy
2. `llm/client` + `llm/parsing` + fake klient + `count_tokens` + `llm_calls` zápis
3. `glossary` (candidate/approved) + `guide` (+ merge draft/final) + `concordance`
   (leak, inconsistency, drift nad `term_mentions`) + testy
4. `agents/scout` (+ `--chunked` merge) + test
5. `agents/translator` (čerstvý + revizní režim, `used_terms`) + test
6. `agents/critic` + test
7. `pipeline` (revizní smyčka, requeue logika, fatal/recoverable klasifikace,
   cost guard) + test
8. CLI: `init`, `scan`, `run`, `status`, `questions`, `answer`, `export`
9. Review UI (minimální schvalovací cesta stačí k prvnímu `run`)
10. Pilot na 2-3 reálných kapitolách + ladění promptů

Detail rozpadne implementační plán (skill writing-plans).

## Otevřené otázky k ověření pilotem

- Stačí 1 scout volání pro celou knihu, nebo se hned jede `--chunked`?
  (Fallback je navržený, jde jen o default.)
- Rozchází se kritik s translatorem často a smysluplně? (Pokud skoro nikdy,
  revizní smyčka je zbytečná režie a je to signál k zjednodušení - klíčové
  pro učební cíl "multiagent se musí potřebovat".)
- Kolik `guess` otázek a `candidate` termínů reálně padne za kapitolu?
  (Ovlivní ergonomii dávkových otázek a objem přepočtů.)
- Jak dobře funguje kmenové porovnání v concordance na české skloňování -
  kolik falešných drift nálezů? (Určí, jestli je potřeba LLM soudce dřív.)
- Cena za kapitolu → cena za knihu (měřeno z `llm_calls`).
