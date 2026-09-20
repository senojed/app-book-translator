# Round 20 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`questions=[]` v kolo-13/18's fatal-commit větvi
  nenávratně maže existující otázky):** Souhlasím a ověřil jsem přesně -
  `state.begin_chapter()` (`src/state.py:600-607`, VOLANÁ jako úplně
  PRVNÍ řádek `process_chapter()`'s těla) UNCONDITIONALLY maže `DELETE
  FROM questions WHERE chapter_idx=? AND answer IS NULL` - VŠECHNY
  nezodpovězené otázky kapitoly, ještě PŘED jakýmkoli LLM voláním.
  `commit_chapter_result()` NEDĚLÁ vlastní `DELETE` na otázkách (jen
  upsertuje, co dostane) - takže smazání z `begin_chapter()` zůstává
  TRVALÉ, pokud se nic nevrátí. STEJNÁ třída chyby jako kolo-18's
  mentions, jen JINÝ zdroj - mentions se mažou AŽ v `commit_chapter_
  result()` (opraveno tam), otázky HNED na začátku funkce (tenhle fix
  to musel řešit JINAK - snapshotem PŘED `begin_chapter()`, ne
  přebudováním PO).

  **Oprava:** `process_chapter()`'s úvod snapshotuje `existing_questions`
  (filtrované na tuhle kapitolu) PŘED voláním `begin_chapter()`.
  Fatal-commit větev je pošle jako `questions=` MÍSTO `[]`. Přidán
  regresní test s existující otevřenou otázkou.

### Disagreed (s odůvodněním)

- **IMPORTANT (statické markery kolidují s legitimní prózou):**
  Souhlasím, že RIZIKO je reálné - ověřil jsem, že "===KONEC===" (na
  rozdíl od "PREKLAD"/"METADATA") je NEJPRAVDĚPODOBNĚJŠÍ kolizní kandidát,
  protože "konec" je BĚŽNÉ české slovo, plauzibilní jako stylistický
  konec kapitoly/scény v samotné knize (Harry Dresden styl urban
  fantasy). NESOUHLASÍM ale s navrhovaným ŘEŠENÍM (per-volání nonce
  delimitery) jako SPRÁVNÝM kompromisem PRO TENHLE PLÁN, z konkrétních
  důvodů:

  1. **Riziko je nízko-pravděpodobné A bezpečně-selhávající.** Kolize
     vyžaduje PŘESNÝ formát (velká písmena, trojité rovnítko na OBOU
     stranách, NIC JINÉHO na řádku) - ne jen výskyt slova "konec" kdekoli.
     Selhání navíc NENÍ tichá korupce - `_parse()`'s count-based kontrola
     (kolo 4/6) to odmítne jako `InvalidTranslationOutput`, kapitola
     skončí `flagged`/`error` k LIDSKÉ kontrole. Nejhorší dopad: občasné
     zbytečné dožádání o ruční revizi, ne ztráta/poškození dat.

  2. **Fix je mechanicky rozsáhlý a sám o sobě rizikový.** Nonce
     delimitery by vyžadovaly přestavět `_FORMAT_RULES`/`SYSTEM_PROMPT_*`
     ze statických konstant na per-volání generované hodnoty (threading
     nonce přes `translate_scene()`/`revise_chapter()`/`_parse()`) A
     přepsat ~66 výskytů marker-literálů napříč testy v týhle (už teď
     obrovské) plánu. Kolo 17 v TÉHLE konverzaci PŘÍMO ukázalo, jak
     snadno se do menšího kopírování vloudí chyba (`calls["n"]`
     NameError) - riziko VNESENÍ nové, subtilnější chyby při 66-výskytové
     mechanické úpravě je reálné a těžko úplně ověřitelné bez
     spuštění testů (co v plan-authoring fázi nemám k dispozici).

  3. **Asymetrie rizik favorizuje NEfixovat.** Nízko-pravděpodobné,
     bezpečně-selhávající riziko VS. vysoko-pravděpodobné riziko
     vnesení skutečné regrese při rozsáhlé mechanické editaci - cena
     fixu převažuje jeho přínos.

  **Rozhodnutí:** Zdokumentováno jako VĚDOMĚ přijaté, ZVÁŽENÉ A
  ZAMÍTNUTÉ omezení v Global Constraints (stejný vzor jako kolo-2's
  char-limit rozhodnutí) - ne oprava kódu.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 20: dva IMPORTANT body. První (otázky se ztrácí ve fatal-commit
větvi) - stejná třída chyby jako kolo-18's mentions, jiný zdroj
(begin_chapter() maže hned na začátku funkce, ne commit_chapter_
result()); opraveno snapshotem PŘED begin_chapter() a obnovou ve fatal-
commit. Druhý bod (statické markery mohou kolidovat s legitimní prózou,
nejpravděpodobněji "===KONEC===") - souhlasím s rizikem, ale NESOUHLASÍM
s navrhovaným fixem (per-volání nonce, ~66 výskytů k přepsání) jako
proporcionální reakcí na nízko-pravděpodobné, bezpečně-selhávající
riziko - zdokumentováno jako vědomě přijaté omezení místo rizikové
mechanické editace.
