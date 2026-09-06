# Multiagentní překladač knih - design (pokus 2)

Datum: 2026-09-06
Stav: schváleno, čeká na implementační plán

## Kontext a cíl

Pokus 1 (archivováno v `pokus-1/`) měl kompletní kostru multiagentního CLI
překladače, ale nikdy neběžel proti reálnému API - prompty, kvalita překladu,
cena i chování kritika zůstaly neověřené. Přechod z brainstormu rovnou do kódu,
chyběl psaný spec.

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
- Pre-scan celé knihy (scout) → draft překladatelského návodu
- Review fáze: lokální web UI na potvrzení/úpravu návodu
- Překladová smyčka: translator → kritik → revizor (max N kol) → uložení
- Deterministická kontrola konzistence termínů + drift napříč kapitolami
- Dávkové otázky během běhu (flag-and-continue), příkazy `questions` / `answer`
- Navazatelný běh (SQLite stav, commit po kapitolách)
- Export hotových kapitol do TXT
- Provider vrstva navržená tak, aby šlo přidat dalšího providera (OpenAI)
  malým zásahem - v pokusu 2 implementován jen Anthropic
- Sledování spotřeby tokenů + měkký strop nákladů

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
navíc kritikovy nálezy + předchozí překlad). Jeden modul, jedna rodina promptů.

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
2. translator(scéna) pro každou scénu → slouč do plného překladu
3. concordance: termíny v kapitole vs glosář (deterministicky, bez LLM)
4. kritik(EN, CZ) → nálezy se závažností
5. dokud (critical nález nebo concordance problém) a kolo < MAX_REVIZE:
       translator v revizním režimu(CZ, nálezy) → nový CZ
       kritik znovu
       revision_rounds += 1
6. nové termíny z translatora → glosář (průběžně, aby další scéna viděla)
7. otázky z translatora → DB (severity guess / blocking)
8. ulož translated_text + status:
       critic_flagged   pokud critical nález přežil MAX_REVIZE kol
       needs_human      pokud translator vrátil otázku severity=blocking
       done             jinak (i s odhadnutým jménem u guess otázky)
```

Každých `CROSS_REF_EVERY_N` kapitol: drift check napříč hotovými kapitolami,
report do `drift_reports`, CLI vypíše počet nálezů.

Na konci `run`: report - kolik done / critic_flagged / error / čekajících otázek
+ spotřeba tokenů za běh.

### Stavový automat kapitoly

```
pending ──překlad+kritika──┬──> done
                           ├──> critic_flagged   (critical nález přežil MAX_REVIZE)
                           ├──> needs_human       (blocking otázka)
                           └──> error             (výjimka; run pokračuje dál)

needs_human    ──answer (všechny otázky kapitoly)──> pending
critic_flagged ──answer / ruční requeue──────────────> pending
error          ──run (auto)──────────────────────────> pending
```

`answer` vrací kapitolu do fronty i když je `done`, pokud se odpověď liší od
odhadu (v1: requeue vždy při odpovědi, přijímáme drobnou práci navíc).

## Agenti

Všichni: bezstavové funkce `(vstup, LLMClient) → strukturovaný výstup`. Postaví
prompt, zavolají klienta, zparsují. Žádná DB, žádné soubory.

### Scout (`agents/scout.py`)
- **Vstup:** celá kniha (350 stran ~ 130k slov se vejde do jednoho volání,
  Sonnet má 1M kontext).
- **Výstup (JSON - strukturovaná metadata, JSON je tu vhodný):**
  ```
  characters:    [{name_en, aliases, suggested: keep|translate, note}]
  places:        [{name_en, suggested_cz, note}]
  terms:         [{term_en, suggested_cz, note}]
  relationships: [{a, b, observed, suggested: tyka|vyka}]
  style_notes:   "1. osoba, min. čas, sarkastický vypravěč, ..."
  must_decide:   ["'The White Council' - přeložit nebo ponechat?"]
  ```
- Model: `claude-sonnet-5`. Jedno volání.

### Translator (`agents/translator.py`) - dva režimy
- **Čerstvý:** scéna (EN) + návod + glosář → překlad
- **Revizní:** navíc předchozí CZ + kritikovy nálezy → opravený překlad
- **Výstup - oddělovačový formát (próza NIKDY v JSON):**
  ```
  ===PREKLAD===
  <čistý přeložený text>
  ===METADATA===
  {"new_terms": [{term_en, cz, note, type}],
   "questions": [{"text": "...", "severity": "guess"|"blocking"}]}
  ```
  `guess` = přeloženo odhadem, jen se zapíše. `blocking` = "fakt nevím" →
  kapitola `needs_human`.
- Model: `claude-sonnet-5`. Největší žrout tokenů. `max_tokens` velký (~16000)
  + pojistka na useknutí (viz Chyby).

### Kritik (`agents/critic.py`)
- **Vstup:** EN kapitola + CZ překlad. NE translatorovo zdůvodnění ani metadata.
  Oddělené volání, oddělený kontext.
- **Výstup (JSON):**
  ```
  {"verdict": "pass"|"revise",
   "findings": [{"severity": "critical"|"minor", "cz_excerpt", "issue", "suggestion"}]}
  ```
- Revizní smyčka se spouští jen na `critical` nálezy. `minor` se zapíšou, neřeší.
- Model: `claude-sonnet-5`.

## Provider vrstva (`llm/client.py`)

```python
class LLMClient(Protocol):
    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion: ...

@dataclass
class Completion:
    text: str
    truncated: bool        # stop_reason == "max_tokens"
    input_tokens: int
    output_tokens: int
```

- `AnthropicClient` = jediná implementace v pokusu 2, jediný soubor importující
  `anthropic`. `max_retries` nastaveno na SDK klientovi (config, default 8).
- Agenti klienta dostanou parametrem, nikdy ho nevytváří. Pipeline ho sestaví
  z configu.
- Klient akumuluje spotřebu tokenů, `get_usage()`.
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
- `{term_en: {cz, note, type}}`
- seed z návodu (keep → term=term, translate → term=cz; místa, termíny)
- roste za běhu z translatorových `new_terms`
- `add_or_update()`, `as_prompt_block()`

### `concordance.py` - deterministicky, BEZ LLM
Nahrazuje terminology + cross_reference agenty z pokusu 1.
- **Kontrola kapitoly** (`check_chapter(cz_text, glossary) → list[Issue]`):
  pro každý termín z glosáře - je EN termín v CZ textu nepřeložený? (reálný bug,
  triviální detekce). Chybí očekávaný CZ tvar, zatímco je přítomná známá varianta?
- **Drift napříč kapitolami** (`check_drift(chapters, glossary) → report`):
  pro každý termín posbírej všechny odlišné tvary napříč hotovými kapitolami;
  2+ zjevně různé české překlady (ne jen skloňování) → drift nález.
- České skloňování: v1 nedělá lemmatizaci. Vysoká hodnota = detekce "EN termín
  unikl nepřeložený". Měkké shody ukáže člověku, tvrdě nepadá. LLM soudce
  ("jsou tyhle dva tvary totéž slovo skloňované?") případně později.
- **Proč kód a ne agent:** vyčerpávající hledání stringů je přesně to, v čem je
  LLM špatný a kód dobrý. Levné, spolehlivé, škáluje na 350 kapitol.

## Review UI (`src/review_ui/`)

- `python main.py review` → spustí lokální server (FastAPI + uvicorn, jedno
  statické HTML + vanilla JS, bez build stepu), otevře prohlížeč
- `GET /api/guide` → `guide.draft.json` (+ `guide.json` když existuje, pro
  návrat k rozdělané editaci)
- `POST /api/guide` → validace, zápis `guide.json`
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
          revision_rounds INTEGER DEFAULT 0, critic_notes TEXT, updated_at)
    status: pending | done | critic_flagged | needs_human | error
questions (id PK, chapter_idx, text, severity, answer, resolved_at)
    severity: guess | blocking
drift_reports (id PK, up_to_chapter, report TEXT, created_at)
runs (id PK, command, input_tokens, output_tokens, started_at, ended_at)
```

**Granularita navázání = kapitola.** Kapitola co spadne na scéně 3 z 5 se
přehraje od scény 1 (přijatelné, kapitola je minuty ne hodiny). `scan` je
idempotentní. `run` commituje po každé kapitole → pád na 47 → `run` naváže od 47.

## Chyby

| Úroveň | Co | Reakce |
|---|---|---|
| API dočasná (429, 5xx, timeout) | jakýkoliv agent | SDK retry (max_retries=8, exp. backoff) |
| API trvalá (špatný klíč, 400) | | výjimka → kapitola `error`, `run` pokračuje |
| Useknutý výstup (`truncated=True`) | translator | výjimka → `error` (useknutý překlad = ztráta dat, neukládat) |
| | kritik / scout | varování, zparsuj část |
| Rozbitý výstup agenta (neparsovatelný) | | parser vyhodí → kapitola `error` |
| Pád celého běhu (Ctrl-C, stroj) | | commit po kapitolách → `run` naváže; `scan` znovu |

`run` nikdy nespadne kvůli jedné kapitole. Report na konci vypíše `error` +
`critic_flagged` + čekající otázky.

### Cost guard
- `run` vypisuje průběžný součet tokenů po každé kapitole
- `config.MAX_SPEND_USD` - měkký strop. Před kapitolou hrubý odhad; při
  projektovaném překročení pauza `pokračovat? [y/N]`.
- Vlastní rate limiter není potřeba (SDK backoff); tvrdé limity účtu pokryje
  `error` + navázání.

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

1. Skeleton: `config`, `state`, `ingest` (port z pokusu 1) + testy
2. `llm/client` + `llm/parsing` + fake klient
3. `glossary` + `guide` + `concordance` + testy
4. `agents/translator` + test
5. `agents/critic` + test
6. `pipeline` (revizní smyčka) + test
7. `agents/scout` + test
8. CLI drátování (`init`, `run`, `status`, `export`, `questions`, `answer`)
9. Review UI
10. Pilot na reálných kapitolách + ladění promptů

Detail rozpadne implementační plán (skill writing-plans).

## Otevřené otázky k ověření pilotem

- Vejde se celá kniha (130k slov) do jednoho scout volání pohodlně, nebo je
  potřeba chunking?
- Rozchází se kritik s translatorem často a smysluplně? (Pokud skoro nikdy,
  revizní smyčka je zbytečná režie a je to signál k zjednodušení.)
- Kolik `guess` otázek reálně padne za kapitolu? (Ovlivní ergonomii dávkových
  otázek.)
- Cena za kapitolu → cena za knihu.
