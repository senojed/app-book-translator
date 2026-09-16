# Round 9 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (timeout revize se necommitne jako `flagged`):** Souhlasím
  a ověřil jsem přesně, krok za krokem - `_exec_codex()`'s timeout se
  dnes přebalí na OBYČEJNÝ `StylistError` (`src/agents/stylist.py:398`,
  žádné odlišení od auth/exit-kód selhání). Kolo 2's fix přebalí KAŽDÝ
  `StylistError` (včetně timeoutu) na `FatalRunError` - a Task 2's
  revizní smyčka má `except FatalRunError: raise`, takže timeout BĚHEM
  revize by propagoval CELOU `process_chapter()` funkcí, zahodil hotový
  scénový překlad, a zastavil celý běh. To přímo POPÍRÁ vlastní komentář
  u Tasku 2's kolo-3 fixu ("bezpečné i pro delší kapitoly... jen označí
  flagged, nezahodí ho") - timeout kolem 2's fixem OMYLEM spadl do
  "fatální" kategorie spolu s auth/launch selháními, se kterými nemá nic
  společného (timeout je PER-CALL/transientní, ne systémové selhání).

  **Oprava:** Nová `stylist.StylistTimeoutError(StylistError)` podtřída -
  MINIMÁLNÍ zásah do `stylist.py` (jedna nová třída, JEDEN existující
  `raise` přepnutý na podtřídu, ŽÁDNÁ změna subprocess mechaniky).
  `CodexLLMClient.complete()` ji NEpřebaluje na `FatalRunError` (na
  rozdíl od ostatních `StylistError` příčin) - necháváme propadnout:
  scénová smyčka ji zpracuje jako per-kapitolový `error` (auto-retry
  příští run je tady SPRÁVNÉ chování pro dočasný problém), revizní
  smyčka (Task 2) ji zachytí a kapitolu označí `flagged` s posledním
  platným překladem. Přidán unit test (`CodexLLMClient` úroveň) i
  integrační test PŘES CELÝ stack (CodexLLMClient → PipelineLLMClient →
  pipeline.py revizní smyčka, umístěný do `tests/test_pipeline.py`
  Taskem 3, protože potřebuje `CodexLLMClient`/`StylistTimeoutError`, co
  Task 2 ještě nemá k dispozici).

- **IMPORTANT (marker parsing substring, ne řádkově kotvené):**
  Souhlasím - `raw.count()`/`raw.index()`/`split_sections()` hledají
  markery jako libovolné podřetězce KDEKOLI v textu, ne jako samostatné
  řádky. Legitimní přeložený text (citace nápisu v knize) nebo JSON
  metadata (`note` pole citující zdrojový text) může teoreticky
  obsahovat marker-podobný řetězec UPROSTŘED - parser by ho chybně
  odmítl jako "poškozený výstup", i když `_FORMAT_RULES` už vyžaduje
  marker na VLASTNÍM řádku (tahle kontrola to jen nevynucovala).

  **Oprava:** Markery se hledají regulárním výrazem kotveným na CELÝ
  ŘÁDEK (`^{marker}$`, `re.MULTILINE`) - nová `_marker_line_positions()`
  pomocná funkce. `split_sections()` (`src/llm/parsing.py`) zůstává
  BEZE ZMĚNY (obecná substring utilita, jediný volající je teď chráněný
  validací PŘED jejím zavoláním). Přidány testy ověřující, že marker-
  podobný text UPROSTŘED překladu i uvnitř JSON hodnoty NEZPŮSOBÍ
  falešné odmítnutí.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 9: dva IMPORTANT body, oba odhalily reálné mezery ve VLASTNÍCH
dřívějších fixech. (1) Kolo 2's StylistError→FatalRunError fix omylem
zahrnul i timeout (per-call/transientní), ne jen systémová selhání
(auth/launch) - to přímo popíralo Tasku 2's kolo-3 slib "revize
zachová hotový překlad". Opraveno novou StylistTimeoutError podtřídou,
co se NEpřebaluje na FatalRunError. (2) Marker parsing (count/index)
hledal substring kdekoli v textu, ne řádek - legitimní obsah s marker-
podobným textem uprostřed by se chybně odmítl. Opraveno řádkově
kotveným regexem, split_sections beze změny (chráněná validací před
sebou). Oba fixy jsou příklad toho, proč se plán ping-ponguje víc kol -
pozdější fix v jednom kole odhalí mezeru v jiném, dřívějším kole.
