# Round 6 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní - Codex round 6 pokryl to podstatné)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
(žádné vlastní)

## On Codex's points

### Agreed + fixed
- **BLOCKING - kolo-5 oprava `status="fatal"` se nepromítla do testovací
  prózy a tabulky:** Ověřil jsem přímo - kód opraven správně, ale
  testovací scénář ("test čte runs a ověří status=='ok'") a chybová
  tabulka ("status běhu zůstává 'ok'") pořád mluvily o starém chování.
  Opraveno na obou místech.
- **IMPORTANT - `taskkill` bez fallbacku, `proc.wait()` bez limitu:**
  přidán fallback na `proc.kill()`, když `taskkill` vrátí nenulový kód,
  a `proc.wait(timeout=10)` s vlastním `except TimeoutExpired: pass`
  místo neomezeného čekání. Přidán test pro fallback cestu.
- **IMPORTANT - registr/hlas/tykání-vykání bez kontroly:** ostrý bod,
  žádná z existujících tří vrstev na to nemá signál (EN sám tykání/vykání
  nenese, `check_meaning_preserved` se ptá jen na VÝZNAM). Přidán
  `guide_block` parametr do `stylist.polish` (stejný text jako translator/
  kritik dostávají přes `pipeline._guide_block`/`guide_as_prompt_block`),
  vložen do promptu jako explicitní "NEPORUŠUJ" sekce, `_cmd_polish` ho
  načítá a předává.
- **NITS - zastaralá próza na 6 místech** (test-dokumentace zmiňující
  `subprocess.run` místo `Popen`, tabulka "tiché přeskočení" navzdory
  hlášení, baseline-z-notes formulace, `rendered_terms=[]` formulace) -
  opraveno všude, kde jsem to našel.
- **NIT - 8 hex SHA-1 zbytečně slabé:** přepnuto na celý `hashlib.sha256`.
- **NIT - "text knihy se nikdy nezapíše na disk" je nadsázka:** opraveno -
  PŮVODNÍ text jde stdinem (pravda), ale STYLIZOVANÁ verze se dočasně
  zapisuje přes `-o` (nutné, jinak by ji nešlo přečíst zpátky), a mazání
  je normální `os.remove`, ne kryptograficky bezpečné vymazání.

### Agreed but already addressed
(žádné)

### Reverzováno z předchozích kol (ne "agreed but addressed" - skutečná
změna názoru po novém argumentu)
- **Deterministická kontrola čísel/dat (kola 4-5 disagree → kolo 6
  agree):** Codexův argument v kole 6 byl kvalitativně jiný než v kolech
  4-5 - "polish operuje nad UŽ SCHVÁLENÝM textem (regresní riziko), ne
  nad prvním konceptem" je jiné tvrzení než "číslo se dá zkontrolovat
  levně", které jsem v kole 4-5 odmítal jako irelevantní vůči
  architektonickému precedentu. Návrh se navíc zúžil na multiset arabských
  číslic/procent (pár řádků regexu), ne plný extraktor, jak jsem
  odmítal v kole 4. Přidáno `_number_multiset` + kontrola v `stylist.polish`,
  s normalizací desetinného oddělovače (`,`/`.`), aby legitimní počeštění
  zápisu čísla neprošlo jako falešný poplach - to byl scénář, kterého
  jsem se v kole 4 obával, a teď je explicitně ošetřený testem.

### Disagreed (zachováno)
- **IMPORTANT - automatická verifikace kvality stylu:** trvám na
  stanovisku z kol 4-5 - mimo explicitní zadání, uživatel zůstává
  posledním soudcem. Codex tenhle bod v kole 6 nezopakoval.

## Claude VERDICT

Po aplikaci 1 BLOCKING + 3 IMPORTANT + 5 NITS z kola 6 (včetně
reverzování vlastního dřívějšího stanoviska u čísel na základě nového,
kvalitativně jiného argumentu) nenacházím ve vlastním čtení nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 6: Codex našel 1 BLOCKING (kolo-5 `status="fatal"` oprava se
nepromítla do testovací prózy/tabulky - reálný rozpor mezi kódem a
dokumentací) a 3 IMPORTANT (taskkill bez fallbacku/limitu, registr/hlas
bez kontroly - nový, ostrý bod, deterministická čísla - přesvědčivější
verze stejného opakovaného bodu) + 5 NITS. Všechno opraveno, VČETNĚ
reverzování vlastního kolo-4/5 nesouhlasu u čísel - Codexův kolo-6
argument (regresní riziko nad už schváleným textem, ne počáteční kvalita)
byl kvalitativně jiný a přesvědčivý, ne jen tvrdošíjné opakování. Design
je teď kompletní - čeká se na kolo 7 Codexu.
