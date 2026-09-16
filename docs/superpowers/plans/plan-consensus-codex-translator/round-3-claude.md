# Round 3 — Claude critique

## Claude's own findings
### BLOCKING
(žádné vlastní nové - Codexovo BLOCKING níž jsem nezávisle ověřil čtením
`translator.py`/`src/llm/parsing.py` a potvrdil jako reálné, viz níž)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **BLOCKING (`truncated` VŽDY False + žádná validace markerů = tichá
  ztráta dat):** Ověřil jsem přímo v kódu - `translator._parse()`
  (`src/agents/translator.py:65-80`) volá `split_sections(raw,
  [MARK_TRANSLATION, MARK_METADATA])`. Pokud `===METADATA===` v `raw`
  vůbec NENÍ (useknutý výstup uprostřed překladu), `split_sections`
  (`src/llm/parsing.py:6-22`) nastaví `sections["PREKLAD"]` na VŠECHNO
  za `===PREKLAD===` do konce stringu - `_parse` to vezme jako
  KOMPLETNÍ, NEPRÁZDNÝ překlad, nic nevyhodí. `CodexLLMClient.complete()`
  (Task 2, dřívější kolo) vrací `truncated=False` VŽDY (zdokumentovaný
  limit - Codex CLI nemá spolehlivý `stop_reason` signál jako Claude) -
  takže JEDINÁ existující pojistka (`translator._complete()`'s `if comp.
  truncated: raise OutputTruncated`) je pro Codex cestu úplně mrtvá.
  Výsledek: useknutý Codex výstup by prošel jako hotový, kapitola by
  šla do DB jako `done` s USEKNUTÝM textem, BEZ JAKÉHOKOLIV varování -
  tichá ztráta dat u reálné knihy. Přesně to, co Codex popsal.

  **Oprava:** Nový povinný koncový marker `===KONEC===` v `translator.py`
  (`_FORMAT_RULES`, obě systémové promty). `_parse()` explicitně
  kontroluje `MARK_END in raw` PŘED čímkoliv jiným - chybí-li, `ValueError`
  ("useknutý nebo jinak neúplný výstup"), žádný tichý fallback na
  částečný text. Backend-agnostické (netýká se jen `CodexLLMClient` -
  funguje i jako obrana do hloubky pro Claude cestu, kdyby `stop_reason`
  detekce měla vlastní mezeru). Nová samostatná Task 2 (vkládá se PŘED
  dosavadní Task 2 "CodexLLMClient", ostatní tasky se posouvají o jednu).

- **IMPORTANT (revizní smyčka zahodí hotový scénový překlad):** Souhlasím
  - a víc než to, můj vlastní BLOCKING fix výš dělá tohle riziko
  PRAVDĚPODOBNĚJŠÍM, ne míň: dřív useknutý výstup PROŠEL tiše (špatně,
  ale bez výjimky); teď `_parse()` na něj SPRÁVNĚ vyhodí `ValueError` -
  a `pipeline.process_chapter`'s revizní smyčka (`revise_chapter()`
  volání, `src/pipeline.py:106-107`) NENÍ obalená - ta výjimka propadne
  z CELÉ `process_chapter()` funkce, PŘED `state.commit_chapter_result()`
  na konci, a zahodí i JIŽ HOTOVÝ, validní scénový překlad (`cz`
  proměnná). Můj kolo-2 argument ("přijmout riziko, jen zdokumentovat")
  podceňoval, jak snadno se teď tahle cesta spustí.

  Všiml jsem si, že `pipeline.py` už má PŘESNĚ tenhle vzor pro kritika
  - `_run_critic()` (`src/pipeline.py:52-63`): `except FatalRunError:
  raise` / `except Exception as e:` → pseudo-nález, `critic_failed=True`,
  NEvyhazuje dál. Mirror stejného vzoru na `revise_chapter()` volání:
  `FatalRunError` propaguje (run se má zastavit, beze změny), jakákoli
  JINÁ výjimka (`ValueError` z nového markeru, `OutputTruncated`, rozbité
  JSON) → smyčka se PŘERUŠÍ, `cz` zůstává na POSLEDNÍ platné hodnotě
  (scénový překlad nebo předchozí úspěšná revize), přidá se `"action":
  "note"` pseudo-nález (bez `str(e)` - jen `type(e).__name__`, ať se
  neopakuje riziko z bodu níž), a `status` výpočet dostane `revision_
  failed` do stejné `elif` větve jako `critic_failed` → `flagged`, ne
  `error`. Nic se neztratí, revize se prostě nepovedla a jde k člověku.
  Součást stejné nové Task 2 (spojeno s markerem výš - je to stejná
  třída chyby, dává smysl jeden integrační test na obojí).

- **IMPORTANT (preflight validace až při prvním volání - prázdná fronta
  ji obejde):** Souhlasím. Ověřil jsem `_client_factory`'s `factory()`
  closure (Task 3/nyní 4) - `_polish_preflight()` se volá AŽ UVNITŘ,
  při `agent=="translator"`u PRVNÍM volání. Pokud `queue` vyjde prázdná
  (`--only` míří jen na už `done`/`flagged`/`needs_human` kapitoly, nebo
  fronta je prázdná úplně), `client_factory("translator")` se nikdy
  nezavolá - `--translator codex` bez `STYLIST_ACCEPT_FS_RISK`/s rozbitým
  CLI tiše "uspěje" (0 kapitol), bez jakékoli indikace, že backend nebyl
  vůbec ověřený. `_cmd_polish` má PŘESNĚ opačný, existující precedent -
  volá `_polish_preflight()` HNED na začátku, PŘED čímkoliv (main.py:1243).

  **Oprava:** `_cmd_run` (Task 4/nyní 5) přidá stejnou eager kontrolu
  na začátek, PŘED `state.create_run` - `if args.translator == "codex":
  model, codex_cmd, err = _polish_preflight(); if err: print+return 1`.
  Duplicitní volání `_polish_preflight()` (jednou tady, jednou uvnitř
  líné `factory()`) je levné (žádný subprocess, jen config/`shutil.
  which`-styl kontrola) - nekomplikuje `_client_factory`'s existující
  cachování/lazy design.

- **IMPORTANT (`extract_json`'s `ValueError` nese až 2000 raw znaků do
  `chapters.notes`, bez redakce):** Souhlasím, a ověřil jsem, že je to
  PŘESNĚ ten samý bezpečnostní vzor, co `config.py` už řeší pro `polish`
  - `config.STYLIST_REPORT_REJECTED_TEXT` (default `False`) existuje
  specificky proto, že `STYLIST_ACCEPT_FS_RISK` znamená "agent smí číst
  disk", ne "smí se výsledek TRVALE uložit do souboru/DB, co bývá v
  synchronizované složce" (`config.py:142-149`, "kolo 31 IMPORTANT" -
  tohle už byl dřív vlastníkův vědomý rozhodnutý bod). `stylist.
  _redact_detail()` (`src/agents/stylist.py:206-215`) přesně tohle řeší
  - a `main.py`'s `_cmd_polish` ho DŮSLEDNĚ používá na VŠECH svých
  `except`/chybových cestách (main.py:670,1316,1380,1384,1389,1392,1444,
  1447). `_cmd_run`'s except blok (main.py:1015-1019) je jediné místo,
  co tenhle vzor NEPOUŽÍVÁ - a tenhle plán je první, co `run` propojí s
  Codexem. Bez opravy: `run --translator codex` na kapitole, kde Codex
  vrátí rozbitou odpověď, uloží až 2000 raw znaků Codexova výstupu do
  `chapters.notes` VŽDY, bez ohledu na `STYLIST_REPORT_REJECTED_TEXT`.

  **Oprava:** `_cmd_run`'s except blok (Task 4/nyní 5) - `detail =
  stylist._redact_detail(str(e)) if args.translator == "codex" else
  str(e)`. Gated JEN na `--translator codex` (ne univerzálně) - `stylist`
  je v `main.py` už importovaný, `_redact_detail` sama defaultně
  redaguje (`is True` kontrola), takže Claude-only `run` (dnešní
  chování, `args.translator == "claude"` default) zůstává BEZE ZMĚNY -
  žádná regrese v debugovatelnosti běžných Claude chyb, co s FS-risk
  nemají nic společného.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 3: Codex našel reálný BLOCKING (`===METADATA===` marker chybějící
u useknutého Codexova výstupu → tichá ztráta dat, `_parse()` to vzalo
jako hotový překlad) - opraveno novým povinným `===KONEC===` markerem +
striktní validací v `translator._parse()` (nová Task 2, backend-
agnostická). Tenhle fix zesílil relevanci Codexova IMPORTANT bodu o
revizní smyčce (teď se `ValueError` na useknutý výstup spustí SNÁZ) -
opraveno mirror vzoru z existujícího `_run_critic()` (FatalRunError
propaguje, jinak `flagged` s posledním platným překladem místo ztráty
dat, součást stejné nové Task 2). Zbylé dva IMPORTANT body (preflight
validace u prázdné fronty, raw Codex výstup bez redakce v `chapters.
notes`) taky souhlasím a opravuji - oba mají přímý existující precedent
v kódu (`_cmd_polish`'s eager `_polish_preflight()` volání a `stylist.
_redact_detail()` použití na VŠECH jeho chybových cestách), `_cmd_run`
byl jediné místo, co oba vzory nedodržovalo.
