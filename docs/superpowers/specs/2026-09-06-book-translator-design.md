# Multiagentní překladač knih - design (pokus 2)

Datum: 2026-09-06
Stav: v revizi (plan-consensus Claude↔Codex)

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
│   ├── glossary.py      # glosář termínů (logika nad SQLite tabulkou)
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
├── tests/
├── data/               # runtime (gitignored): state.sqlite3, guide*.json,
│                       #   .book-translator.lock (glosář je v SQLite)
└── output/             # runtime (gitignored): kniha_cz.txt
```

### Hranice modulů

| Modul | Zná | Nezná | Test |
|---|---|---|---|
| `ingest` | soubor → kapitoly | DB, LLM | vzorové soubory |
| `state` | jen SQLite | LLM, překlad | dočasná DB |
| `guide` | JSON na disku | LLM | přímo |
| `glossary` | logika nad SQLite tabulkou (přes `state`) | LLM | dočasná DB |
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
python main.py answer <question_id> "..."   # odpověď → pravidlo/glosář + přepočet kapitol
python main.py status             # přehled stavu kapitol
python main.py export             # hotové kapitoly → output/kniha_cz.txt
```

### Co dělá `run` na jednu kapitolu

```
0. status kapitoly → processing; DELETE FROM questions WHERE chapter_idx=? AND answer IS NULL
1. rozděl na scény (podle prahu slov)
2. pro každou scénu translator(scéna, návod, glosář); slouč překlady;
   METADATA scén agreguj: new_terms = union, questions = concat,
   rendered_terms = SEZNAM {term_id, cz_as_used, scene_idx} (bez dedup)
3. concordance.check_chapter(EN kapitola, CZ, glosář, rendered_terms) → Findings
4. kritik(EN kapitola, CZ) → Findings
5. dokud (critical nález kritika  NEBO  concordance leak  NEBO
          inconsistency u seeded/approved termínu)  a  kolo < MAX_REVIZE:
       findings = kritikovy critical + concordance nálezy (společný tvar Finding)
       translator revizní režim(EN kapitola, CZ, findings, návod, glosář) → nový CZ
         → jeho celokapitolová METADATA NAHRADÍ agregát z kroku 2
           (new_terms se ale kumulují)
       concordance.check_chapter znovu; kritik znovu
       revision_rounds += 1
6. z FINÁLNÍHO překladu (vše v jedné transakci s krokem 8):
     - new_terms → glosář jako `candidate` (dedup podle term_en)
     - ověř `rendered_terms` proti CZ textu, neověřené zahoď
     - DELETE FROM term_mentions WHERE chapter_idx=?
     - concordance.build_mentions(EN, CZ, glosář, rendered_terms) → INSERT
7. otázky → DB (upsert podle klíče (chapter_idx, kind, scope_key, severity)):
     - translatorova `guess` / `blocking` otázka
     - concordance `inconsistency` u kandidátního termínu → kind=term,
       scope_key=term_id, guess_answer=nalezený tvar, severity=guess
8. ulož translated_text + revision_rounds + notes(JSON Findings) + status:
       flagged        critical/leak nález přežil MAX_REVIZE kol
       needs_human    blocking otázka
       done           jinak
   (jedna transakce; commit uvolní kapitolu z `processing`)
```

Po každých `CROSS_REF_EVERY_N` kapitolách: `check_drift` → z každého
`DriftFinding` `question` (kind=term, scope_key=term_id, chapter_idx=NULL,
guess_answer=nejčastější tvar, severity=guess), upsert. Odpověď pak přes
běžná requeue pravidla přepočítá dotčené kapitoly.

**Které stavy `run` bere do fronty:** `pending` a `error` (error = auto retry).
`needs_human` a `flagged` `run` **přeskočí** (čekají na člověka); vrátí je do
hry `answer` resp. `run --retry-flagged`. Žádná kapitola nezastaví dávku.
Report na konci vypíše přeskočené.

`check_drift` (viz výše) navíc ukládá report do `drift_reports` pro audit.

Na konci `run`: report - kolik done / flagged / needs_human / error / čekajících
otázek (vč. drift otázek) + spotřeba tokenů za běh (z `llm_calls`).

### Stavový automat kapitoly

```
pending ──překlad+kritika──┬──> done
                           ├──> flagged        (critical/leak nález přežil MAX_REVIZE)
                           ├──> needs_human     (blocking otázka)
                           └──> error           (recoverable výjimka)

error       ──běžný `run` (auto retry)──────────────────────> pending
needs_human ──answer, když už žádná blocking otázka kapitoly nezbývá──> pending
flagged     ──answer (mění-li výsledek) / `run --retry-flagged`──> pending
done        ──answer na guess otázku, když answer ≠ guess───> pending
```

**Requeue po `answer` (`answer` řeší JEDNU otázku):**
1. zapiš odpověď podle `kind`:
   - `term` / `name`: glosář `candidate` → `approved` (nebo oprav `cz`); pokud
     odpověď připouští víc tvarů, ty navíc → `accepted_alt`
   - `relationship` (`scope_key = "a|b"`): zapiš `address` do `guide.relationships`
   - `style` / `other`: `guide.add_rule(odpověď)`
2. **blocking otázka** (kapitola `needs_human`): kapitolu vrať na `pending` jen
   když pro její `chapter_idx` NEZBÝVÁ žádná nezodpovězená `severity=blocking`
   otázka. Jinak zůstává `needs_human`.
3. **guess otázka** (kapitola už `done`/`flagged`):
   - `answer` == `guess_answer` → nic, žádný přepočet
   - jinak → `affected_chapters` přejdou na `pending`:
     - `term`/`name`: kapitoly s řádkem v `term_mentions` pro `term_id`
       = `scope_key` (včetně `cz_form = NULL` omission řádků)
     - `relationship`: `done`/`flagged` kapitoly, kde se v EN textu vyskytují
       obě jména dvojice
     - `style`/`other` (bez scope_key): všechny `done`/`flagged` od kapitoly
       vzniku otázky
`answer` běží jen když neběží `run` (run lock, viz Stav), takže nikdy nekoliduje
s právě zpracovávanou kapitolou.

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
  fakta → `merge_scout_facts()` (deterministicky v kódu):
  - normalizační klíč = `name_en.strip().casefold()`; položky se stejným klíčem
    se slijí, `aliases` = sjednocení, `note` = spojení
  - kolize jmen (různé entity, stejný povrch): nechat obě, přidat `must_decide`
  - `relationships`: stejná dvojice (klíč `sorted(a,b)`) s různým `suggested`
    napříč chunky → `suggested: null` + `must_decide`
  - `must_decide` a `terms`/`places` obdobně sjednotit podle scope_key
  → jeden draft návodu. Žádné další LLM volání.
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
  {"new_terms":      [{term_en, cz, note, type}],   # jen NEZNÁMÉ povrchy
   "rendered_terms": [{term_id, cz_as_used}],       # 1 řádek na výskyt známého termínu
   "questions": [{"kind": "term|name|relationship|style|other",
                  "scope_key": "term_id / a|b / null",
                  "guess_answer": "co translator zvolil / null u blocking",
                  "text": "...", "severity": "guess"|"blocking"}]}
  ```
  Prompt glosáře (`glossary.as_prompt_block()`) uvádí u každého termínu jeho
  `term_id`. Translator odkazuje známé termíny přes `term_id`; `term_en` použije
  jen v `new_terms` pro povrch, který v glosáři není.
  `guess` = přeloženo odhadem (má `guess_answer`), zapíše se otázka. `blocking`
  = "fakt nevím" (bez `guess_answer`) → kapitola `needs_human`. `new_terms` jdou
  do glosáře jako `candidate`.
  `rendered_terms` = pro každý termín z DODANÉHO glosáře, jak ho translator ve
  scéně přeložil. **Uzavřená množina** (jen termíny, které translator dostal),
  navíc pipeline každý `cz_as_used` ověří substringem proti CZ textu a
  neověřené zahodí. Je to "ukaž na co jsi sáhl", ne "prohledej text" - to kód
  ověří sám. Slouží jako vstup pro `concordance.build_mentions` (zachytí i
  tvar mimo kanonický `cz`/`accepted_alt`).
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

### Finding (sjednocený tvar nálezu)

Kritik i concordance produkují nálezy v jednom tvaru; pipeline je sloučí a
předá revizoru (a uloží do `chapters.notes`):

```
Finding = {
  source:     "critic" | "concordance",
  type:       "fidelity"|"fluency"|"register"  |  "leak"|"inconsistency"|"omission",
  severity:   "critical" | "minor",
  term_en:    str | null,     # jen concordance
  expected:   str | null,     # kanonický cz (concordance)
  actual:     str | null,     # co je v textu (concordance)
  cz_excerpt: str | null,     # jen critic
  issue:      str,
  suggestion: str | null,
}
```

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
  `anthropic`. `max_retries` na SDK klientovi (config, default 8). **Čistý -
  žádná DB, žádné `run_id`, žádný cost guard.**
- **`PipelineLLMClient(inner, run_id, agent, state, config)`** - obal, který
  pipeline vytvoří **zvlášť pro každé volání agenta** (`agent` = label do logu)
  a předá tomu agentovi místo holého klienta. Levný objekt. Implementuje stejný
  Protocol. Jeho `complete(system, user, max_tokens, model)`:
  1. odhad ceny volání = `count_tokens(system,user)*in_rate + max_tokens*out_rate`
     (konzervativně počítá plný `max_tokens` na výstupu - u překladu je output
     hlavní náklad)
  2. `spent_so_far` z `llm_calls` + odhad > `MAX_SPEND_USD` → pauza
     `pokračovat? [y/N]` (u `scan` tvrdě zastav)
  3. `inner.complete(...)` v `try/finally`
  4. **ve `finally`** zapiš řádek do `llm_calls`: `status ∈ {ok, truncated,
     error}`, `error_class` (u výjimky), tokeny nullable (u výjimky neznámé).
     Selhaná volání a retry exhaustion tak nezmizí z auditu ani cost reportu.
  Agenti nepoznají rozdíl, hranice modulů zůstávají (klient sám DB nezná).
- **Sonnet 5:** neposílat `temperature` / `top_p` / `top_k` (model non-default
  sampling odmítá 400). Předpoklady o kontextu/výstupu (1M / 128k) ověřit proti
  Anthropic docs a držet v `config.py`, ne v logice.
- **Kam půjde per-provider varianta promptů ("později"):** každý agent bude mít
  `SYSTEM_PROMPTS = {"anthropic": "..."}` klíčováno rodinou providera. V pokusu 2
  jen `"anthropic"`. Zapsáno v designu, nepostaveno.

### Modely (`config.py`, role → model id)
Vše `claude-sonnet-5` (levnější a novější než `claude-sonnet-4-6`).
Model IDs, kontextové limity i ceny ($/MTok in/out pro cost guard) jsou
konfigurační hodnoty v `config.py`, ne konstanty v logice. **Před pilotem
ověřit proti Anthropic docs** (model active? ceny? context/output limit?).
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
- **Jediný zdroj pravdy pro termín→CZ v promptu je glosář.**
  `guide_as_prompt_block()` emituje styl, vztahy (tyká/vyká) a rozhodnutí
  keep/translate, ale **NE** dvojice termín→český překlad - ty jdou do promptu
  jen z `glossary.as_prompt_block()`. Návod glosář jen seeduje; po `answer` má
  `approved` glosář přednost a v promptu není nic, co by ho přebíjelo.

### `glossary.py` - logika nad SQLite tabulkou `glossary` (ne JSON!)
Glosář se za běhu mění při každé kapitole. Musí být ve stejné DB jako kapitoly,
aby zápis glosáře a commit kapitoly byl JEDNA transakce (JSON soubor mimo SQLite
= riziko nekonzistence při pádu). `glossary.py` je jen logická vrstva, data
drží `state`.

- řádek: `term_id PK, canonical_en, aliases (JSON list), cz,
  accepted_alt (JSON list), note, type, status`
  - `term_id` = stabilní ID entity (ne povrch textu) - kvůli aliasům a případu
    "stejný povrch, různé entity". `canonical_en` + `aliases` = na co concordance
    matchuje v EN textu.
  - `type`: name | place | term
  - `status`: `seeded` (z návodu), `approved` (člověk potvrdil přes `answer`),
    `candidate` (translator navrhl, nepotvrzeno)
  - `cz` = kanonický překlad. `accepted_alt` = další tvary, které člověk
    EXPLICITNĚ schválil přes `answer` (ne automaticky pozorované). Pozorované
    tvary žijou jen v `term_mentions`, do glosáře se nepromítají.
- `term_mentions` a `questions` (u term/name) odkazují `term_id`, ne povrch.
- seed z návodu (keep → cz=term_en, translate → cz=guide.cz) = `seeded`
- za běhu: `new_terms` → `candidate` (dedup podle term_en; existující nepřepisuje)
- `as_prompt_block()` řadí `seeded`+`approved` jako závazné, `candidate` zvlášť
  jako "návrh, může se změnit"
- `add_candidate(term_en, ...)` (nový povrch → nový `term_id`),
  `promote(term_id, cz)`, `add_accepted_alt(term_id, cz_form)`,
  `resolve_surface(term_en) → term_id | None`, `as_prompt_block()` (uvádí
  `term_id`) - vše přes `state` (SQLite)

### `concordance.py` - deterministicky, BEZ LLM
Nahrazuje terminology + cross_reference agenty z pokusu 1. Vstup: EN a CZ text
kapitoly, glosář, a translatorem ohlášené `rendered_terms` (uzavřená, kódem
ověřená množina - viz Translator).

Množina zkoumaných termínů = jen ty, jejichž `canonical_en`/`aliases` je ve
scéně/kapitole, plus ty v `rendered_terms`. Ne celý glosář.

- **`build_mentions(en_text, cz_text, glossary, rendered_terms) → list[Mention]`:**
  `Mention = (term_id, cz_form | NULL, scene_idx | NULL, source)`. Pro každý
  zkoumaný termín:
  - každý ověřený `cz_as_used` z `rendered_terms` → řádek `source=rendered`
    (i víc řádků na termín, když se tvar liší)
  - navíc přesné shody `cz` / `accepted_alt` / kmene v CZ textu, které
    `rendered_terms` nepokryl → `source=detected`
  - žádná forma nenalezena → řádek `cz_form=NULL, source=omission`
  → tabulka `term_mentions` = ÚPLNÝ pozorovací záznam (i tvary mimo glosář).
- **`check_chapter(en_text, cz_text, glossary, rendered_terms) → list[Finding]`:**
  - `leak`: EN podoba překládaného termínu (`cz != term_en`) je v CZ textu →
    critical. `keep` položky (`cz == term_en`) se nehlásí.
  - `inconsistency`: `cz_form` termínu ∉ ({`cz`} ∪ `accepted_alt` ∪ jejich
    skloňování) → critical u approved/seeded, jinak `question`.
    **`cz_form` se do glosáře NEpřidává** (jen člověk přes `answer` může přidat
    `accepted_alt`). Pozorování žije v `term_mentions`.
  - `omission`: termín v EN, v CZ ani `cz` ani `accepted_alt` ani rendered_term
    → minor (ukáže se, nepadá; parafráze i chyba)
- **Drift napříč kapitolami** (`check_drift(term_mentions) → list[DriftFinding]`):
  pro každý `term_id` seskup ne-NULL `cz_form` z `term_mentions` všech
  `done`/`flagged` kapitol; 2+ zjevně různé kmeny → `DriftFinding{term_id,
  formy: [...], kapitoly: [...]}`. Data jsou úplná (i tvary mimo glosář),
  takže drift chytí i nekonzistenci, kterou `check_chapter` v době překladu
  neznal. Pipeline z každého DriftFinding udělá `question` (viz `run`).
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
- `POST /api/guide` → validace; při úspěchu zápis `guide.json`, odpověď
  `{ok: true}`, a server se sám ukončí s exit 0. Zavření prohlížeče bez uložení
  / SIGINT → exit ≠ 0.
- **CLI příkaz `review`** spustí server a čeká na jeho konec. Exit 0 → provede
  reseed glosáře (ne UI - drží izolaci): přepíše **jen `seeded`** řádky tabulky
  `glossary` z návodu; `approved`/`candidate` zůstávají; konflikt → `approved`
  vyhrává. Exit ≠ 0 → žádný reseed. `review` po celou dobu drží run lock.
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
    status: pending | processing | done | flagged | needs_human | error
    processing = kapitola je právě zpracovávaná; při startu `run` se každá
      uvízlá `processing` (pád v půlce) přepne zpět na `pending`
    notes: JSON - poslední nálezy kritika + concordance, nebo text chyby

questions (id PK, chapter_idx NULL, kind, text, scope_key, guess_answer,
           severity, answer, resolved_at)
    kind:     term | name | relationship | style | other
    scope_key: term_id (term/name), "a|b" (relationship),
      hash(text) (style/other) - nikdy NULL/"" aby UNIQUE fungoval
    severity: guess | blocking
    chapter_idx = NULL u globálních otázek (drift); jinak kapitola vzniku
    dedup jen mezi OTEVŘENÝMI otázkami:
      partial UNIQUE(chapter_idx, kind, scope_key, severity) WHERE answer IS NULL
      partial UNIQUE(kind, scope_key, severity) WHERE answer IS NULL AND chapter_idx IS NULL
      → zodpovězená otázka neblokuje založení nové pro stejný klíč (nový drift
        po opravě, opětovné nadhození po dalším rerunu)
    upsert; rerun kapitoly maže její nezodpovězené a zakládá znovu (krok 0).

glossary (term_id PK, canonical_en, aliases TEXT, cz, accepted_alt TEXT,
          note, type, status, updated_at)
    runtime glosář; v SQLite (ne JSON), aby zápis + commit kapitoly byla
    jedna transakce. guide.json/guide.draft.json zůstávají soubory
    (edituje je člověk přes review UI, za `run` se nemění).

term_mentions (id PK, term_id FK, cz_form NULL, chapter_idx, scene_idx NULL,
               source)
    source: rendered (z ověřeného rendered_terms) | detected (kód našel v CZ)
            | omission (cz_form NULL)
    JEDEN řádek na pozorovaný (term_id, cz_form) výskyt v kapitole - víc
      různých forem = víc řádků = viditelná intra-chapter inconsistency;
    plněno přes concordance.build_mentions(EN,CZ,glosář,rendered_terms);
    zdroj dat pro drift check i affected_chapters při requeue

drift_reports (id PK, up_to_chapter, report TEXT, created_at)

runs (id PK, command, started_at, ended_at, status)
llm_calls (id PK, run_id FK, agent, provider, model, input_tokens NULL,
           output_tokens NULL, cost_usd NULL, truncated, status,
           error_class NULL, ts)
    status: ok | truncated | error
    zápis po KAŽDÉM volání (přes PipelineLLMClient, ve finally), cost_usd = cena
    z reálných tokenů (sazby v config.py); cost guard i report čtou odtud.
    Pre-flight odhad guardu se nepersistuje (je jen dočasný v guardu).
```

**Granularita navázání = kapitola.** Kapitola co spadne na scéně 3 z 5 se
přehraje od scény 1 (přijatelné, kapitola je minuty ne hodiny). `scan` je
idempotentní. `run` commituje po každé kapitole → pád na 47 → `run` naváže od 47.

**Run lock.** Mutující příkazy (`run`, `scan`, `answer`, `init`, a `review` po
dobu běhu serveru) na startu vezmou zámek (`.book-translator.lock` v `data/`
s PID + časem). Druhý mutující příkaz při aktivním zámku skončí s hláškou
"běží jiný příkaz". `status`, `questions`, `export` jsou read-only, zámek
ignorují. Zastaralý zámek (mrtvý PID) se přebere. Tím je pravidlo "`answer`
nesahá na právě zpracovávanou kapitolu" vynutitelné a `review` (zapisuje
`guide.json` + reseeduje glosář) nekoliduje s `run`.

**Transakce při zpracování kapitoly:**
- **Transakce A** (krok 0): `chapters.status → processing` + smazání
  nezodpovězených otázek kapitoly. Commit.
- LLM volání běží MIMO transakci (dlouhá, nesmí držet zámek DB). `llm_calls`
  se zapisují průběžně (autocommit).
- **Transakce B** (kroky 6-8): `glossary` (candidates), `term_mentions`
  (delete+insert), `questions` (upsert), `chapters` (translated_text, status,
  revision_rounds, notes). Buď vše, nebo nic.
- Pád mezi A a B: kapitola zůstane `processing` → další `run` ji vrátí na
  `pending`. Pád během B: transakce se rollbackne, kapitola zůstane `processing`.

## Chyby

Klasifikace určuje reakci. **Fatal běhu** = zastav příkaz hned, nesahej na žádnou
kapitolu (nemá smysl vyrábět 45× `error`). **Recoverable kapitoly** = označ tu
jednu `error`, pokračuj další.

| Třída | Co | Reakce |
|---|---|---|
| **Fatal běhu** | chybějící/špatný API klíč (auth error), neznámý model (404), 400 invalid request (špatné parametry), chyba konfigurace, `MAX_SPEND_USD` překročeno | výjimka ukončí příkaz, exit≠0. Žádná kapitola nedostane finální stav; aktuální může zůstat `processing` (další `run` ji vrátí na `pending`). Dříve commitnuté kapitoly zůstávají. |
| **API dočasná** | 429, 5xx, timeout | SDK retry (max_retries=8, backoff); po vyčerpání → recoverable |
| **Recoverable kapitola** | retry vyčerpán, neočekávaná výjimka v jedné kapitole | kapitola `error`, `run` pokračuje |
| **Useknutý výstup** | translator | `error` (useknutý překlad = ztráta dat) |
| | kritik | 1× retry s vyšším `max_tokens`; když zas useknuto → kapitola `flagged` (nepředpokládat pass) |
| | scout | **fatal běhu** - viz sekce Scout (částečný návod znehodnotí vše) |
| **Rozbitý výstup agenta** | neparsovatelný | translator → `error`; scout → fatal; kritik → 1× retry, pak `flagged` |
| **Pád procesu** (Ctrl-C, stroj) | | commit po kapitolách → `run` naváže; `scan` běží znovu |

**Kanárek.** První LLM volání běhu je fatal-kanárek. Transakce A (`processing`)
proběhne, pak kanárek: selže-li fatal třídou, příkaz skončí, transakce B se
nikdy nespustí → žádná kapitola nedostane finální stav (`done`/`flagged`/
`error`). Uvízlá `processing` je samoopravná (další `run` ji vrátí na
`pending`). Viz Transakce v sekci Stav.

### Cost guard
- Sedí v `PipelineLLMClient.complete()` (viz Provider vrstva) - má tam k
  dispozici `system`/`user`/`max_tokens`, takže odhad ceny volání (vstup přes
  `count_tokens` + výstup `max_tokens × out_rate`) je spolehlivý.
- `config.MAX_SPEND_USD` platí pro `run` i `scan`. `spent_so_far` (z `llm_calls`)
  + odhad tohoto volání > strop → pauza `pokračovat? [y/N]`; u `scan` tvrdě
  zastav (fatal běhu).
- Usage v `llm_calls` po každém volání → přežije pád procesu.
- Vlastní rate limiter není potřeba (SDK backoff).

## Testy - po vrstvách

1. **Čistá logika (bez API, bez DB):** ingest (dělení kapitol/scén), concordance
   (`build_mentions`, leak vs keep, inconsistency, omission, drift grouping,
   kmenové porovnání), parsing (`split_sections`, `extract_json`),
   guide/glossary (candidate/approved/seeded, reseed merge),
   `merge_scout_facts`. Většina testů. Z pokusu 1 portovat 11.
2. **Stav:** dočasná SQLite, CRUD + přechody (blocking→pending, guess requeue
   podle scope_key, error retry, uvízlé `processing`→`pending`, run lock).
3. **Agenti:** fake `LLMClient` s nakonzervovanými odpověďmi. Sestavení promptu +
   parsování výstupu + guess/blocking split. Bez API.
4. **Pipeline:** fake agenti + fake klient. Revizní smyčka (spustí se na
   critical/leak, zastaví na MAX_REVIZE, zastaví na pass), glosář candidate,
   `term_mentions` mazání při retranslation, cost guard pauza, fatal vs
   recoverable klasifikace, izolace chyb.
5. **Pilot (neautomatizované):** jeden reálný `scan` + `run` na 2-3 kapitoly
   s klíčem. Checklist v README, první položka: **ověřit model ID + ceny +
   context/output limity proti Anthropic docs**
   (https://docs.anthropic.com/en/docs/about-claude/model-deprecations),
   zapsat do `config.py`. Dál: fungují prompty, kvalita, cena za kapitolu,
   vydělává si multiagent na sebe.
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
5. `agents/translator` (čerstvý + revizní režim, question metadata) + test
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
