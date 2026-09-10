# Round 13 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem si všiml, že kolo 12 taky nedostalo
vlastní souhrnný bullet v "Rozhodnutí" sekci (stejná mezera, co jsem
opravoval u kola 10 v kole 11 - zjevně se mi to nestalo poprvé). Doplnil
jsem bully pro kolo 12 i 13 najednou a nadpis na "kol 1-13".

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `shutil.copy2` snapshotu bez vlastního `except`:** ověřil
  jsem přímo - vnější `try` v `_cmd_polish` chytá jen `FatalRunError`/
  `KeyboardInterrupt`, žádný obecný `except Exception`. Obyčejný `OSError`
  ze samotného `shutil.copy2` by tak propadl jako NEZACHYCENÝ traceback,
  přesně jak Codex tvrdil - moje vlastní kolo-12 test próza ("vrátí 1,
  status=fatal") byla FAKTICKY NEPRAVDIVÁ (a "status=fatal" navíc nemá
  kam se zapsat, protože `create_run` ještě neproběhl). Zabaleno do
  `FatalRunError`, próza opravena na přesný popis (jen návratový kód,
  žádný perzistentní stav).
- **IMPORTANT - `finish_run` ve `finally` může přebít původní chybu:**
  ověřil jsem si Python sémantiku - výjimka vyhozená uvnitř `finally`
  NAHRADÍ tu, co propaguje (nebo zruší právě dokončovaný `return`). Kdyby
  `finish_run` sám selhal (typicky STEJNOU třídou chyby, co nás do
  `finally` přivedla), volající by dostal matoucí/jinou chybu místo
  skutečné příčiny. Zabaleno do vlastního `try/except`, selhání se jen
  vypíše.
- **IMPORTANT - sekvence vs. multiset u číselné kontroly:** ostrý,
  přesvědčivý bod - seřazená množina `{"3","5"}` je stejná bez ohledu na
  to, kterému číslu patří která hodnota, takže přehození DVOU RŮZNÝCH
  čísel mezi dvěma místy (postavy, datum den/měsíc) by prošlo beze
  změny. Ověřil jsem, že `SYSTEM_PROMPT_TEMPLATE` stylistovi explicitně
  zakazuje měnit "pořadí událostí" i čísla - takže přechod na sekvenční
  (neseřazenou) kontrolu NEriskuje časté falešné poplachy na legitimním
  přeuspořádání, protože takové přeuspořádání beztak není povolené
  chování. Přejmenováno `_number_multiset` → `_number_sequence`,
  odstraněno řazení, přidán regresní test.
- **NIT - próza "kol 1-11" a chybějící kolo-12 bullet:** ověřeno a
  opraveno.
- **NIT - chybí regresní test na samostatný `register_drift`:** ověřil
  jsem - existující scénář testuje jen `meaning_drift`, `register_drift`
  (přidaný v kole 7) vlastní test nikdy nedostal. Přidán.

### Disagreed (částečně)
- **IMPORTANT - normalizace desetinného oddělovače může skrýt
  významovou změnu (1.234 vs 1,234):** souhlasím s KRITIKOU zdůvodnění
  (bylo skutečně nepřesné - popisovalo EN→CZ převod, ale funkce srovnává
  dvě ČESKÉ verze), takže zdůvodnění jsem přepsal na přesné. NEsouhlasím
  ale s tím, že samotná normalizace je nebezpečná - ověřil jsem si českou
  typografickou konvenci: desetinný oddělovač je VÝHRADNĚ čárka, tisícový
  MEZERA, nikdy tečka. Tečka v už přeloženém českém textu je tak téměř
  vždy reziduální anglicismus (překladatelovo nedopatření), ne záměrně
  jiná hodnota - riziko skutečné kolize (stylista SOUČASNĚ změní hodnotu
  I oddělovač tak, aby řetězcová shoda náhodou vyšla) je v tomhle úzkém
  CZ-vs-CZ kontextu prakticky zanedbatelné. Normalizace zůstává,
  zdůvodnění je teď přesné.

## Claude VERDICT

Po aplikaci 4 IMPORTANT (1 s korigovaným, ne identickým zdůvodněním) + 2
NITS z kola 13 nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 13: Codex našel 4 IMPORTANT (samotný `shutil.copy2` snapshotu bez
vlastního except - propadal by jako traceback, ne return 1; `finish_run`
ve `finally` mohl přebít původní chybu; SEKVENCE vs. MULTISET u číselné
kontroly - seřazená množina nerozliší přehození dvou různých čísel;
normalizace desetinného oddělovače měla nepřesné zdůvodnění) + 2 NITS
(próza "kol 1-11"/chybějící kolo-12 bullet; chybí test na samostatný
register_drift). Nejzávažnější oprava: `_number_multiset` → `_number_
sequence` bez řazení - uzavírá reálnou mezeru (přehození dvou čísel mezi
sebou), bezpečně díky tomu, že stylistův prompt už beztak zakazuje měnit
pořadí. Normalizace desetinného oddělovače zůstává (jen přesnější
zdůvodnění) - jediný bod, kde jsem nesouhlasil s NAVRHOVANOU ZMĚNOU
chování, i když jsem přijal kritiku zdůvodnění. Design je teď kompletní -
čeká se na kolo 14 Codexu.
