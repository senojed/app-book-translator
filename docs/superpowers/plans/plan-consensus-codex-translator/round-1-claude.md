# Round 1 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní nové - Codexovo BLOCKING níž jsem nezávisle ověřil čtením
`translator.py`/`src/llm/client.py` a potvrdil jako reálné, viz níž)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

### NITS
- Task 3, test `test_client_factory_translator_backend_codex_uses_codex_client`
  - po opravě BLOCKING bodu (viz níž) přidat i `assert client._inner.billed_model == "m"`.

## On Codex's points

### Agreed + fixed

- **BLOCKING (model propagation):** Ověřil jsem přímo v kódu -
  `pipeline.process_chapter` volá `translator.translate_scene(scene,
  guide_block, glossary_block, client_factory("translator"))` BEZ
  `model=` argumentu → `translate_scene`'s `model=None` default →
  `_complete()`'s `model=model or config.MODEL_TRANSLATOR` →
  `"claude-sonnet-5"` (ověřeno v `config.py:55`). Tahle hodnota jde do
  `PipelineLLMClient.complete(model="claude-sonnet-5")`, co ji použije
  PŘÍMO pro `self._price(model)` (cenová tabulka `PRICE_*_PER_MTOK["claude-
  sonnet-5"]` = $2/$10, NE naše nové `$0.0` pro `CODEX_MODEL`) i pro
  `record_llm_call(model=model, ...)` (audit řádek by tvrdil, že proběhlo
  Claude volání). Codex má pravdu - Task 1's `$0.0` ceny by se v praxi
  NIKDY nepoužily, cost guard by kalkuloval s cenou Claude modelu za
  volání, co ve skutečnosti nic nestojí, a audit log by lhal o tom, jaký
  model běžel.

  **Oprava:** `CodexLLMClient` dostane atribut `billed_model` (=
  `codex_model` z konstruktoru). `PipelineLLMClient.complete()` spočítá
  `effective_model = getattr(self._inner, "billed_model", None) or model`
  a použije ho pro `_guard()`/`_price()`/`record_llm_call(model=...)` -
  `self._inner.complete(model=model, ...)` (skutečné volání) dostává
  PŮVODNÍ `model` beze změny (pro `AnthropicClient` je to jediná správná
  hodnota; `CodexLLMClient` ho stejně ignoruje). `AnthropicClient`/
  `FakeLLMClient` nemají `billed_model` - `getattr` spadne na `model`
  param, NULOVÁ změna chování pro existující Claude cestu. Task 2
  (níž) rozšířen o tenhle fix + testy PŘÍMO na `PipelineLLMClient`
  (`tests/test_pipeline_client.py`), ne jen na `CodexLLMClient` samotný -
  bez toho by test dokazoval jen "Codex klient si pamatuje svůj model",
  ne "cena/audit se SKUTEČNĚ použijou správně".

- **IMPORTANT (prompt size guard):** Ověřil jsem - `stylist.polish()`
  má VLASTNÍ `STYLIST_MAX_CHARS` kontrolu (`stylist.py:514`), ale ta
  běží AŽ UVNITŘ `polish()`, PŘED voláním `_exec_codex()` - `CodexLLMClient.
  complete()` volá `_exec_codex()` PŘÍMO, takže tenhle guard NEDĚDÍ.
  Task 2 rozšířen o `config.CODEX_TRANSLATE_MAX_CHARS` (nová konstanta,
  NE reuse `STYLIST_MAX_CHARS` - jiná kompozice promptu: systém+návod+
  glosář+scéna/revize, ne jen EN+CZ) + kontrolu `len(system)+len(user)`
  PŘED `_exec_codex()` voláním, `StylistError` se stejným stylem hlášky.

- **IMPORTANT (Task 5 DB kopie neproveditelná):** Souhlasím, `run`
  fakt nemá `--db` parametr a vždycky čte `config.DB_PATH`. Existuje
  ALE už hotový mechanismus přesně na tohle - `config.PROJECT_DIR =
  os.environ.get("BOOK_TRANSLATOR_PROJECT_DIR", ".")` (z dřívějšího
  Tasku "parametrizuj kořenovou složku projektu", `config.py:39`) -
  `DATA_DIR`/`DB_PATH` se odvozují OD NĚJ. Task 5 Step 2 přepsán na
  konkrétní použitelný postup přes tenhle env var, ne vágní "použij
  kopii DB".

### Disagreed

- **IMPORTANT (StylistError → per-chapter "error", ne FatalRunError):**
  Nesouhlasím s obecným návrhem "technické chyby ukončí celý běh" jako
  BLANKET pravidlem pro `CodexLLMClient`. Důvod: `_polish_one_chapter`
  (existující main.py kód, main.py `_cmd_polish`) DNES zachytává STEJNOU
  třídu chyby (`stylist.StylistError` z `_exec_codex` přes `stylist.
  polish()`) a řeší ji jako per-kapitolové `outcome="failed"`, NE jako
  `FatalRunError` - to je zavedený precedent v týhle kódové bázi pro
  Codex CLI selhání, ne mezera, co tenhle plán zavádí nově. `_cmd_run`'s
  `except Exception as e: status="error"` (main.py:1015) navíc chová
  STEJNĚ ke KAŽDÉ výjimce z `process_chapter`, včetně Claude cest (např.
  `ValueError` z rozbitého JSON) - `CodexLLMClient` by tímhle nezaváděl
  nové chování, jen by ho sdílel se zbytkem systému.

  Rozumím riziku (auth vyprší uprostřed běhu → N kapitol za sebou
  hlásí `error` se stejnou příčinou, než uživatel stihne zasáhnout) -
  ale automatická klasifikace "je tahle konkrétní `StylistError`
  systémová, nebo per-kapitolová" by musela buď sniffovat text hlášky
  (křehké, `_exec_codex` už teď generuje čtyři různé zprávy pro čtyři
  různé příčiny) nebo měnit kontrakt `_exec_codex`/`stylist.py`, což je
  explicitně MIMO ROZSAH podle designu ("Revize `_exec_codex`/`stylist.
  py`'s subprocess mechaniky - používá se beze změny"). Riziko zůstává
  přijaté, ne přehlédnuté - `_cmd_run` VŽDY tiskne "Kapitola N: chyba
  (X), pokračuji" pro každou selhavší kapitolu, takže opakující se
  stejná příčina je viditelná hned a uživatel může běh přerušit (Ctrl-C)
  - žádná tichá/neviditelná degradace. Přidávám větu do plánu (Task 2),
  co tohle rozhodnutí zdůvodňuje, ať to čtenář plánu nemusí dohledávat
  v historii diskuze.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 1: Codex našel reálný BLOCKING (model propagation - Codex volání
by dostala Claude cenu/model v auditu, nulové ceny z Tasku 1 by se
nikdy nepoužily) a dvě IMPORTANT (chybějící prompt-size guard pro
translator, neproveditelná instrukce "kopie DB" v Tasku 5) - všechny tři
opraveny v plánu. Třetí IMPORTANT (StylistError vždy fatal) odmítnut s
odůvodněním - existující precedent (`_polish_one_chapter`) už stejnou
třídu chyby řeší jako per-kapitolovou, ne fatal, tenhle plán ho jen
sdílí, ne zavádí nově. Rozhodnutí dokumentováno přímo v plánu.
