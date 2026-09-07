# Round 9 — Claude critique

## Claude's own findings

Žádné nad rámec Codexových. Zadání pro toto kolo (ověřit, že konsolidační přepis
neztratil rozhodnutí z logu) jsem formuloval právě proto, že přepis je
nejrizikovější operace — a ukázalo se, že oprávněně.

## On Codex's points

### Agreed + fixed

- **Přepis ztratil validaci identity z kola 4.** Ověřeno grepem: počet výskytů
  věty o validaci identity byl v konsolidovaném dokumentu **nula**. Rozhodnutí
  „prázdný klíč se přeskočí, duplicitní `(section, klíč)` se deterministicky
  sloučí" zmizelo. Obnoveno i s poznámkou, kdy vzniklo a kdy se ztratilo.

- **Nové pořadí POSTu rozbilo ochranu proti nezodpovězeným otázkám.** Nejlepší
  nález kola a regrese, kterou jsem zavedl já. Ověřeno v kódu:
  `apply_must_decide` (`server.py:43`) prázdné odpovědi přeskočí a na konci
  seznam vymaže; dnešní kód proto volá `_check_must_decide_answered`
  **před** ní (`server.py:122` před `:125`). Moje nové pořadí ten krok
  vypustilo, takže by nezodpovězená otázka tiše propadla do `guide.json`.
  Pořadí opraveno na šest očíslovaných kroků s vysvětlením, proč krok 2 nesmí
  zmizet ani se posunout.

- **Význam `coverage` se v UI ztratil.** Ukládání zůstalo, ale formulář ukazoval
  všechny čtyři důvody prázdné položky stejně. Doplněno: „model termín nezná",
  „dávku se nepodařilo zpracovat", „model položku vynechal", „nezkoušeno kvůli
  limitu" - každý s vlastní hláškou a testem.

- **Přemapování `must_decide` u více variant nebylo definované.** Správný
  postřeh na reálných datech: u `naagloshii/skinwalker` může člověk ponechat oba
  řádky, ale odpověď patří jen jednomu a z textu se to odvodit nedá. Payload
  proto nese cílové `id` a formulář u takové otázky nabídne roletku s variantami.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex 2 blokující a 2 důležité, vše přijato a ověřeno. Kolo potvrdilo riziko
konsolidačního přepisu: ztratila se validace identity z kola 4 (ověřeno, nula
výskytů v dokumentu) a význam `coverage` v UI, a nové pořadí POSTu zavedlo
regresi — vypustilo `_check_must_decide_answered`, bez které nezodpovězená
otázka tiše propadne, protože `apply_must_decide` prázdné odpovědi přeskočí
a seznam vymaže (ověřeno na server.py:43 a :122). Doplněno explicitní cílové
`id` pro přemapování otázek u složených položek s více ponechanými variantami.
