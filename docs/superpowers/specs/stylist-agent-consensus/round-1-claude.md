# Round 1 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní, kromě těch, co Codex taky našel - viz níže)

### IMPORTANT
- `_cmd_polish` v draftu používal `interactive=False` u `_client_factory` -
  to je styl `scan`/`reference` (jedno velké volání). `polish` je ale
  smyčka přes VÍC kapitol s LLM voláním (kritik) na každou, přesně jako
  `_cmd_run`, který používá `interactive=True`. Bez toho by cost guard
  uprostřed dávky tvrdě spadl místo nabídnutí nového stropu. Opraveno.

### NITS
(žádné nad rámec Codexových)

## On Codex's points

### Agreed + fixed
- **BLOCKING - argv délka/viditelnost:** prompt (EN+CZ celé kapitoly) teď
  jde přes vstupní soubor, pozicionální argument je jen krátký odkaz na
  cestu. Řeší limit délky příkazové řádky i viditelnost obsahu v seznamu
  procesů.
- **BLOCKING - guardrail není deterministický:** přidána levná strukturální
  kontrola PŘÍMO v `stylist.polish` (počet odstavců musí sedět, poměr délky
  0.5-1.5x) - běží PŘED tím, než se výsledek vůbec vrátí volajícímu, zdarma
  (bez LLM). Nenahrazuje kritika (ten hlídá význam), je to druhá, nezávislá
  síť proti hrubému selhání (uťatý/zkrácený výstup).
- **BLOCKING - "jen text, žádné soubory" je nepravdivé:** `-C` teď míří na
  izolovaný `tempfile.mkdtemp()`, ne na kořen repa - Codex nemá k čemu
  přistoupit kromě vstupního/výstupního souboru, který mu sami dáme.
- **IMPORTANT - chybějící `finish_run`:** `_cmd_polish` teď má
  `try/finally` se `status` proměnnou stejně jako ostatní příkazy.
- **IMPORTANT - nekonzistentní DB stav po přijetí:** místo tří
  nezávislých zápisů (`update_chapter` + ruční `notes`/`mentions`) se
  znovu použije `state.commit_chapter_result` - STEJNÁ atomická transakce,
  co používá `process_chapter`. `notes` i `term_mentions` teď vždycky
  popisují AKTUÁLNÍ (přijatý) text.
- **IMPORTANT - slabé pravidlo přijetí:** `_polish_rejected` je přísnější
  než `pipeline.has_revise_triggers` - odmítá při JAKÉMKOLI nálezu typu
  `leak`/`omission`/`inconsistency`/`fidelity`, bez ohledu na `action`
  nebo `severity`. U stylisty je cíl nulová změna obsahu, takže i "minor
  fidelity" nález je důvod k zamítnutí.
- **IMPORTANT - test rozhraní v rozporu (`str` vs. shell string):**
  `codex_cmd` je teď typovaný jako `list[str]`, testy volají
  `[sys.executable, str(fake)]`. Žádné implicitní `shlex.split`.
- **IMPORTANT - neošetřené chyby přeruší celý příkaz:** `_cmd_polish`
  teď má `except Exception` kolem volání `stylist.polish` pro JEDNU
  kapitolu (log + `failed += 1` + pokračuj), navíc `except StylistError`
  zvlášť pro čitelnější hlášku. `KeyboardInterrupt` propaguje ven (chycen
  až vnějším blokem, který nastaví `status = "interrupted"`).
- **IMPORTANT - chybí idempotence/značka:** `_stylist_marker` zapsaný do
  `notes` (stejný tvar jako ostatní nálezy - `source`, `type`, `severity`,
  `action`, `term_id`, `expected`, `actual`, `cz_excerpt`, `issue`,
  `suggestion` - takže nic, co `notes` čte jinde, nespadne na neznámý
  klíč). `_already_styled` filtruje podle `source == "stylist"`.
  `--force` obchází.
- **IMPORTANT - model/config Codexu neřízený:** přidán `config.CODEX_MODEL`
  (výchozí `None`), `polish()` bere `codex_model` parametr, `-m` flag se
  přidá jen když je nastavený. Model se zaznamená do `_stylist_marker`.

### Agreed but already addressed
(žádné - draft byl první verze, nic nebylo řešeno dřív)

### Disagreed
- **IMPORTANT - "chybí rollback a audit původního překladu" (plná
  historie):** Částečně nesouhlasím s rozsahem návrhu. Plná verzovaná
  historie (uchování VŠECH předchozích tvarů kapitoly) by byla
  nekonzistentní s existující architekturou - ani revizní smyčka
  (`translator.revise_chapter`) dnes historii nedrží, přepisuje
  `translated_text` bez stopy po předchozí verzi. Zavádět verzování JEN
  pro `polish` by byl nekonzistentní precedens. Místo toho `_stylist_marker`
  ukládá hash + délku PŘED stylizací (dohledatelnost "co se změnilo, kdy,
  jakým modelem" - bez uchování celého starého textu). Považuju to za
  přiměřený kompromis vůči zbytku kódové základny, ne za odbytí nálezu -
  jádro obavy (nedohledatelnost) je vyřešené.
- **IMPORTANT - "sledování Codex volání a úspěšnosti" jako perzistentní
  audit KAŽDÉHO pokusu (i zamítnutých/selhaných):** Nesouhlasím s rozsahem.
  Zamítnutá nebo selhaná stylizace NIC v DB nemění - není co dohledávat,
  žádný nekonzistentní stav nehrozí. Konzolový výstup pro daný běh stačí;
  perzistentní tabulka pokusů by byla čistě diagnostický nice-to-have bez
  vazby na konkrétní zjištěnou mezeru. Audit PŘIJATÉ stylizace (to jediné,
  co skutečně persistuje a mění chování) je vyřešený přes `_stylist_marker`.

## Claude VERDICT

`CHANGES_NEEDED` v tuhle chvíli by znamenalo, že vidím ve VLASTNÍM
nezávislém čtení dalších oprav navíc k těm, co jsem právě aplikoval - po
aplikaci všech výše uvedených oprav (3 BLOCKING + 7 IMPORTANT od Codexu, 1
IMPORTANT vlastní) žádné další vlastní BLOCKING/IMPORTANT nenacházím.

`CONSENSUS`

## Summary for log

Kolo 1: Codex našel 3 BLOCKING (argv limit délky, chybějící deterministický
guardrail, špatný pracovní adresář pro Codex) a 9 IMPORTANT/NITS. Všech 3
BLOCKING a 7 z 9 IMPORTANT přijato a opraveno v `stylist.py`/`_cmd_polish`
(soubor místo argv, izolovaný `mkdtemp` cwd, strukturální kontrola odstavců
+ délky, `finish_run`, `interactive=True`, přísnější `_polish_rejected`,
`list[str]` `codex_cmd`, broad exception handling, idempotence přes
`notes` marker, řízený model). 2 body (plná historie, plný audit
zamítnutých pokusů) vědomě zúženy s odůvodněním - jádro obav vyřešeno
levnějším mechanismem konzistentním se zbytkem kódu. Claude vlastní čtení
navíc přidalo opravu `interactive=False → True`. Návrh je teď kompletní a
implementovatelný - žádné vlastní BLOCKING/IMPORTANT nezbývá.
