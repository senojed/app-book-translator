# Round 7 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem udělal vlastní sweep na stale patterny
(`_kill_process_tree(pid)` starý vzor, `isinstance(f, dict)` filtr v
critic.py, `codex_cmd: str`) - nic dalšího nenalezeno.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - registr/tykání-vykání jen instrukcí, bez verifikace:**
  ostrý, správný bod - `guide_block` (kolo 6) dal stylistovi INSTRUKCI,
  ale žádná vrstva to neOVĚŘOVALA, což odporuje vlastní zásadě "nikdy
  nevěřit naslepo". Rozšířen `check_meaning_preserved`/`MEANING_CHECK_PROMPT`
  o `register_changed` pole a nový nález typ `register_drift`,
  `_polish_rejected` ho odmítá stejně jako `meaning_drift`.
- **IMPORTANT - rollback/historie stále nedostatečné vůči "uživatel je
  poslední soudce":** přesvědčivý bod - v době, kdy uživatel posuzuje
  výsledek, je DB UŽ přepsaná, takže hash sám o sobě "poslednímu soudci"
  nic neumožňuje VRÁTIT. Přidána `shutil.copy2(db, db +
  ".pre-polish-backup")` PŘED prvním zápisem dávky - jedna přepisovaná
  záloha, ne rostoucí historie (furt konzistentní s tím, že plná
  verzovaná historie zůstává mimo rozsah), ale SKUTEČNĚ obnovitelná.
- **IMPORTANT - kritik pořád ne-fail-closed (top-level ne-dict,
  smíšené findings):** ověřil jsem přímo - `data.get(...)` na top-level
  poli/stringu by spadlo na `AttributeError` MIMO retry cyklus (žádný
  `except` ho nechytá). A tiché přeskočení nedict položek ve `findings`
  by nechalo `{"verdict":"pass","findings":[1]}` projít jako čistý
  výsledek. Přidána `isinstance(data, dict)` kontrola hned po
  `extract_json`, a kontrola "žádná položka findings není dict → celá
  odpověď je rozbitá" (místo tichého filtru).
- **IMPORTANT - `taskkill` sám může viset:** `subprocess.run(["taskkill",
  ...])` v `_kill_process_tree` neměl VLASTNÍ timeout - funkce volaná
  právě proto, že něco viselo, by mohla viset na svém vlastním nástroji
  na zabíjení. Přidán `timeout=10` + `except (TimeoutExpired, OSError)`.
- **NIT - "Rozhodnutí" sekce má dva protichůdné bully o číslech:** ověřeno
  - starý kolo-4 bullet "MIMO ROZSAH" nikdy nebyl odstraněn, když kolo 6
  kontrolu PŘIDALO. Nahrazeno přesným popisem aktuálního stavu.

### Agreed but already addressed
(žádné nové - kolo 7 nálezy jsou nové, kromě jednoho níže)

### Vlastní doplněk nad rámec Codexova bodu
- Codexův bod o `status="ok"` rozporu (Ř. 1094-1097 v jeho číslování) byl
  DALŠÍ výskyt stejné mezery, co jsem myslel, že jsem opravil v kole 6 -
  fixoval jsem TEHDY jeden odstavec, ale existoval JEŠTĚ jeden o pár
  řádků výš v témže seznamu testovacích scénářů. Udělal jsem doplňkový
  grep sweep přes CELÝ dokument na `status.*"ok"` a `přesto.*ok`, abych
  potvrdil, že žádný další výskyt nezůstal.

## Claude VERDICT

Po aplikaci 4 IMPORTANT + 1 NIT z kola 7 (žádný nový BLOCKING - to
poslední bylo přeřazeno Codexem samotným pod IMPORTANT tentokrát) a
vlastním doplňkovém sweepu nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 7: Codex našel 4 IMPORTANT (registr/tykání bez verifikace - nový
ostrý bod; rollback argument eskalovaný a přesvědčivý - user-je-soudce
neplatí, když je DB už přepsaná; kritik pořád ne-fail-closed na top-level
typ a smíšené findings; taskkill bez vlastního timeoutu) + 1 NIT
(protichůdné bully o číslech v Rozhodnutí sekci). Nejzávažnější zjištění:
poslední zbylý výskyt stale `status="ok"` prózy, co unikl kolo-6 opravě -
potvrzuje vzorec "kód opravený, próza ne vždy dopromítnutá všude" a
motivuje důkladnější sweep před uzavřením kola. Design je teď kompletní -
čeká se na kolo 8 Codexu.
