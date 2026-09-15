# Round 2 — Claude critique

## Claude's own findings

Vlastní nezávislý průchod nad opravami z kola 1 (hledal jsem regrese, co
moje vlastní úpravy mohly zavést, a nekonzistence mezi Tasky, co kolo 1
opravilo jen na jedné straně):

### IMPORTANT
- `rendered_terms` výpočet byl po kole 1 nekonzistentní SÁM SE SEBOU -
  dávka (Task 5) vždy brala živou DB, editor (Task 9) vždy historii.
  Sjednoceno do jedné sdílené `_preferred_rendered_terms` (Task 4),
  volané INTERNĚ z `_commit_polish_result` (odstraněna z parametrů
  úplně - obě volající strany dostávají stejné pravidlo automaticky).

## On Codex's points

### Agreed + fixed
- **BLOCKING - historie se validuje AŽ PO DB commitu:** ověřeno ve
  vlastním kódu z kola 1. `_commit_polish_result` teď načítá/validuje
  historii JAKO PRVNÍ krok; selhání SAMOTNÉHO zápisu na konci je nová
  `HistoryWriteFailedAfterCommit` výjimka, oba volající (Task 5 dávka,
  Task 9 save) ji zachytávají zvlášť se správnou hláškou.
- **BLOCKING - editor zůstává zamčený po úspěšném uložení:** ověřeno -
  `loadChapter()` nikdy nevolala `lockEditor(false)`, komentář v kódu byl
  vyloženě nepravdivý. Opraveno - `loadChapter()` je teď JEDINÉ místo,
  co `lockEditor` vždy nuluje (na začátku při chybě, na konci při
  úspěchu).
- **BLOCKING - `_polish_env` nemá zámek pro `refresh_lock`:** ověřeno -
  testy volají `_cmd_polish` přímo, žádný zámek předem nezískávají.
  Přidáno `config.LOCK_PATH` přesměrování + `state.acquire_lock`.
- **IMPORTANT - `toggleResolved` po regeneraci vrací 404:** souhlas,
  ověřeno - nové nálezy z regenerace nejsou v `chapters.notes`, dokud se
  neuloží. Přidán `PERSISTED_IDS` set - nálezy mimo něj se zaškrtávají
  jen lokálně, persistují se až s "Uložit".
- **IMPORTANT - ochrana `resolved` jen jednosměrná:** souhlas, moje
  vlastní kolo-1 oprava chránila jen false→true. Přepsáno na "server
  vždy vyhrává pro ZNÁMÉ id, oběma směry" - jednodušší a doopravdy
  správné, ne jen částečná záplata.
- **IMPORTANT - rovnost textu ≠ nulová změna:** souhlas. Přidána "lehká"
  zápisová větev (findings/status bez nové historie položky), když text
  sedí, ale nálezy/status potřebují aktualizovat.
- **IMPORTANT - `rendered_terms` nekonzistence dávka/save:** viz vlastní
  nález výš - stejná oprava.
- **IMPORTANT - Task 14 ochrana proti přepsání zůstává neúplná:** souhlas
  na všech třech bodech (regenerace odemyká před parse JSON, revert
  nezamyká vůbec, historická tlačítka fungují během save/regenerate).
  Přidán sdílený `EDITOR_BUSY` flag + `try/finally` s odemčením AŽ na
  konci zpracování ve všech třech handlerech.
- **IMPORTANT - Task 13 plošné mazání testů:** souhlas, 4 konkrétní
  testy (lock loss, poškozená historie, selhání před/po commitu)
  testovaly reálnou ochranu. Portováno do Task 9 Step 1 jako 4 nové
  testy, Task 13 na ně teď odkazuje jménem místo mlčení.
- **IMPORTANT - Task 10 `finish_run` nechráněné:** souhlas - výjimka
  odsud by přebila i řízenou chybovou odpověď z `except` bloku (Python
  `finally` sémantika). Zabaleno do vlastního `try/except: pass`.
- **NIT - `stylist` vs `main.stylist` v testu:** souhlas, oprava na
  `main.stylist` (soubor ho takhle importuje, ne pod bare jménem).
- **NIT - pořadí snapshot/create_run + úklid mimo finally:** souhlas.
  Snapshot teď vzniká PŘED `try:` (tedy i před `create_run`), úklid
  přesunut do existujícího `finally:` bloku (běží i při přerušení).
- **NIT - commit krok nezahrnuje `polish_store.py`:** souhlas, doplněno.

### Disagreed
- **IMPORTANT - Task 10 `status="ok"` i pro `outcome="failed"`:**
  ověřil jsem - tohle je STEJNÁ konvence jako dávkový `_cmd_polish`
  (per-kapitolové selhání ≠ `run_status="fatal"`, jen skutečná
  `FatalRunError`/výjimka to dělá). Neopravoval jsem chování, jen
  přidal ochranu kolem `finish_run` (viz výš) - `status="ok"` zůstává
  záměrně.

## Claude VERDICT

CHANGES_NEEDED (opravy byly rozsáhlé - `_commit_polish_result` signatura
se dál mění (odstraněn `rendered_terms` parametr), potřebuje další
ověření, jestli všechna volající místa/testy sedí)

## Summary for log

Kolo 2 odhalilo další reálné chyby, hlavně v tom, co kolo 1 samo zavedlo:
historie se validovala AŽ PO DB zápisu (přesně ta třída bugu, co kolo 1
mělo opravit u draft-fronty, jen se znovu objevila v novém kódu), editor
po úspěšném uložení zůstal navždy nepoužitelný (triviálně ověřitelné
manuálním testem, ale plán to samo netvrdilo správně), a testovací
izolace zámku byla pořád děravá. Vlastní nález (`rendered_terms`
nekonzistence) vedl k čistší opravě, než jen záplatovat obě strany zvlášť
- sjednoceno do jednoho pravidla volaného INTERNĚ sdílenou funkcí.
