# Round 10 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - Task 13 Step 8 migrace přes `python -c`:** ověřeno -
  skript je víceřádkový s f-stringy/uvozovkami, `python -c "…"` na
  Windows/PowerShellu (Global Constraints: projekt cílí na Windows) má
  jiná pravidla escapování než bash a víceřádkový string literál na
  příkazové řádce je nespolehlivý. Instrukce přepsána na "ulož do
  souboru, spusť jako skript" (`python scripts/migrate_findings_ids.py`).
- **IMPORTANT - Task 10 `POST /api/polish/regenerate` obchází `write_lock`
  a needeklaruje re-check zámku po dlouhém Codex volání:** ověřeno čtením
  skutečného `polish_server.py` (`_require_lock` main.py:182-199 dělá
  SYNCHRONNÍ `refresh_lock` při KAŽDÉM volání, `_heartbeat` main.py:
  164-180 navíc nezávisle obnovuje zámek na pozadí) - reálné riziko je
  proto nízké (heartbeat běží nezávisle na délce requestu), ale Codexův
  bod o CHYBĚJÍCÍM re-checku PŘED `finish_run` (auditní zápis `runs`/
  `llm_calls`) je platný - kdyby zámek MEZITÍM přece jen ztratil (jiný
  proces ho převzal), `finish_run` by se zavolalo bez ověřeného
  vlastnictví, což doslovně odporuje Global Constraints textu ("žádný
  zápis tenhle vzor neobchází"). Opraveno: `finally` blok teď volá
  `app.state.require_lock()` TĚSNĚ PŘED `state.finish_run(...)` a zápis
  přeskočí, pokud zámek mezitím ztratil. Global Constraints sekce
  rozšířena o přesně zúženou výjimku (jen VÝHRADNĚ auditní zápisy, NIKDY
  `chapters`/historie, a jen s re-checkem PŘED KAŽDÝM takovým zápisem) -
  textová kontradikce mezi obecným pravidlem a Task 10's zdůvodněným
  odklonem od něj je tím odstraněná, ne jen mlčky tolerovaná. Nový test
  ověřuje: `require_lock()` vrátí `True` napoprvé (start handleru),
  `False` podruhé (`finally`) → `finish_run` se NEZAVOLÁ.

### Agreed + fixed (NITS)
- Task 2 Step 4: `test_findings.py` obsahuje 11 testů (spočítáno), ne 8 -
  opraveno očekávání.
- Task 5 Step 8: osamocený duplicitní textový fragment ("taky mimo
  try/finally, viz `polish_server.py:149`)...") smazán - byl zbytkem
  po dřívější editaci, nenavazoval na okolní text.

## Claude VERDICT

CONSENSUS (žádný vlastní nález, oba Codexovy IMPORTANT body i oba NITY
opraveny)

## Summary for log

Dvě reálné mezery - jedna platformní (Windows/PowerShell nekompatibilní
instrukce), jedna zámková (chybějící re-check před auditním zápisem po
dlouhém volání, i když existující heartbeat infrastruktura riziko už do
značné míry kryje). Plus 2 textové nity (špatný počet testů, osiřelý
fragment) - obojí stopy po předchozích 9 kolech editací. Claude verdict
potřetí za sebou CONSENSUS (kola 8, 9, 10) - čeká se na kolo 11, jestli
Codex konečně potvrdí totéž a smyčka dosáhne skutečné shody.
