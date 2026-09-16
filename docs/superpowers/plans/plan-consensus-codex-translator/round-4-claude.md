# Round 4 — Claude critique

## Claude's own findings
### BLOCKING
(žádné vlastní nové - Codexovo BLOCKING níž jsem nezávisle ověřil čtením
plánu a potvrdil jako reálné, viz níž)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **BLOCKING (`MARK_END not in raw` nestačí):** Souhlasím. Ověřil jsem -
  kolo 3's kontrola je pouhé "marker je NĚKDE v textu", ne "marker je
  jediný výskyt na SPRÁVNÉM místě na KONCI". Tři konkrétní díry:
  (1) marker duplicitní nebo vložený UPROSTŘED (např. halucinovaný
  uvnitř JSON stringu) projde, protože `in` kontroluje jen přítomnost;
  (2) text PO markeru (garbage, další pokus modelu) projde ze stejného
  důvodu; (3) nejzávažnější - pokud `===METADATA===` chybí ÚPLNĚ, ale
  `===KONEC===` je přítomný (model zapomene metadata sekci, ale marker
  přidá, protože si ho pamatuje z instrukcí), `split_sections(raw,
  [MARK_TRANSLATION, MARK_METADATA, MARK_END])` pro `MARK_TRANSLATION`
  hledá `nxt=MARK_METADATA` v `after` - není tam - takže `value = after`
  BEZE ZKRÁCENÍ, a `===KONEC===` string skončí JAKO SOUČÁST přeloženého
  textu (`sections["PREKLAD"]` by obsahovalo i literální "\n===KONEC===").
  Kapitola by šla do DB s marker-stringem zapečeným v próze.

  **Oprava:** `_parse()` teď vyžaduje PŘESNOU strukturu, ne pouhou
  přítomnost: (a) každý marker (`MARK_TRANSLATION`/`MARK_METADATA`/
  `MARK_END`) přesně JEDNOU (`raw.count(...) == 1`), (b) ve SPRÁVNÉM
  pořadí (`raw.index(MARK_TRANSLATION) < raw.index(MARK_METADATA) <
  raw.index(MARK_END)`), (c) `raw.rstrip().endswith(MARK_END)` - marker
  je opravdu POSLEDNÍ neprázdný obsah, nic po něm. Vedlejší efekt: `if
  MARK_METADATA in raw:` větev před `extract_json()` je teď mrtvý kód
  (přítomnost METADATA je zaručená kontrolou (a) výš) - zjednodušeno na
  bezpodmínečné volání. Task 2 rozšířena o negativní testy (duplicitní
  marker, marker uprostřed/špatné pořadí, text po markeru).

- **BLOCKING (Task 5's `test_run_translator_flag_passed_to_client_
  factory` nemockuje eager preflight):** Souhlasím a je to přímý
  důsledek MÉHO VLASTNÍHO kolo-3 fixu (eager `_polish_preflight()` na
  začátku `_cmd_run`) - tenhle test (napsaný v kole 1, PŘED kolem 3)
  spouští `run --translator codex` bez mocku `_polish_preflight`, takže
  by teď narazil na SKUTEČNOU kontrolu `STYLIST_ACCEPT_FS_RISK`/
  `CODEX_MODEL`/`stylist._resolve_codex_cmd(["codex"])` (reálný
  filesystem/PATH lookup) - v čistém CI bez `codex` binárky na PATH by
  `_cmd_run` vrátilo 1 hned na začátku, test by spadl na `assert ...
  == 0` dřív, než se spy factory vůbec stihne zavolat.

  **Oprava:** Přidán `monkeypatch.setattr("main._polish_preflight",
  lambda: ("m", ["codex"], None))` do testu, stejný vzor jako ostatní
  Task 4/5 testy, co Codex preflight mockují.

### Agreed but already addressed
- **IMPORTANT (chybí negativní testy pro marker strukturu):** Součást
  stejné opravy výš - přidány `test_duplicate_end_marker_raises`,
  `test_content_after_end_marker_raises`, `test_markers_out_of_order_
  raises` do Tasku 2.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 4: Codex našel dva reálné BLOCKING body, oba v mém vlastním kolo-3
kódu. (1) `MARK_END not in raw` kontroluje jen PŘÍTOMNOST markeru, ne
jeho POZICI/POČET - marker uprostřed, duplicitní, nebo text po něm by
prošly; nejhorší případ: chybějící METADATA marker by nechal `===KONEC===`
zapečený jako součást přeloženého textu. Opraveno přesnou strukturální
kontrolou (počet==1 každého markeru, pořadí, `endswith`). (2) Vlastní
eager-preflight fix z kola 3 rozbil existující Task 5 test, co
`_polish_preflight` nemockuje - opraveno přidáním mocku. Oba body jsou
ukázka, proč se plán ping-ponguje víc kol - nový fix v jednom kole umí
odhalit mezeru v JINÉM, dřívějším kole.
