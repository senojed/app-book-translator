# Round 22 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `toggleResolved`'s `catch` (kolo 19) volá `window.
  location.reload()` a pak obyčejné `return` - navigace je ASYNCHRONNÍ,
  takže Promise doběhne VYŘEŠENÁ dřív, než stránka fakticky odejde.
  Uložit/revert (kolo 8 `Promise.all(PENDING_RESOLVE_PROMISES...)`)
  by tak mohly odeslat VLASTNÍ request nad stavem, co právě přiznal
  nejistotu.** Ověřeno logicky (asynchronní chování `location.reload()`
  je standardní, dokumentované chování prohlížečů). Opraveno - `catch`
  teď končí `await new Promise(() => {})` (navždy visící) místo `return`
  - `Promise.all` v Uložit/revert pak čeká DÁL, dokud stránka fakticky
  nenaviguje pryč. Automatizovaný test nejde (žádný JS test framework v
  projektu) - přidán konkrétní manuální ověřovací krok do Task 14 Step 4.

- **IMPORTANT - `btn-save`/`revertChapter` po POTVRZENÉM 200 volají
  `loadChapter()`, ale jeho VLASTNÍ selhání (síťová chyba na GETu) se
  ignoruje - editor se odemkne nad STARÝMI daty, přestože commit
  proběhl.** Ověřeno čtením - potvrzeno, `loadChapter()` nevracelo nic,
  volající na výsledek nereagovaly. Opraveno - `loadChapter()` teď vrací
  `true`/`false`, `btn-save`/`revertChapter` na `false` PO potvrzeném
  commitu reagují tvrdým `window.location.reload()` (ne tichým
  pokračováním nad zastaralým stavem).

- **IMPORTANT - `POST /api/findings/resolve` (Task 11) nevolá `main.
  _backup_db_once`, na rozdíl od OBOU větví Tasku 9.** Ověřeno čtením
  vlastního kódu z předchozích kol - potvrzeno, chybělo úplně. Pokud je
  resolve PRVNÍ mutující operace session, startovní snapshot se při
  čistém vypnutí smaže beze stopy, přestože reálný zápis proběhl.
  Přidáno `main._backup_db_once(db_path, app.state.backup_state)` PŘED
  `UPDATE`, stejné místo jako u Tasku 9's lehké větve. Nový test ověřuje
  `backup_state["done"]` po prvním resolve.

## Claude VERDICT

CHANGES_NEEDED (souhlas se všemi třemi, plná implementace)

## Summary for log

Kolo 22 - tři nezávislé, reálné mezery, žádný spor. První dvě pokračují
"ambiguous write" a "async race" témata z kol 15/19-21, teď v NOVÝCH
místech (resolve→save/revert interakce, post-commit reload selhání).
Třetí je stejná třída jako kolo 20/21 (chybějící ochrana, co OSTATNÍ
podobné cesty už mají) - `_backup_db_once` byla v Tasku 9 na obou
větvích, ale Task 11 (přidaný později, jiný task) na ni zapomněl.
