# Round 15 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem grep sweepnul zbylé `shutil.copy2`
výskyty (Codex citoval "ř. 1061 a 1173" jako stale) - všechny nalezené
výskyty jsou buď restore recept (legitimně pořád `copy2`), historicky
rámované ("Dřív (kolo 13)"), nebo moje vlastní nové kolo-15 texty. Žádný
zbylý neoprávněný current-tense výskyt jsem nenašel - beru Codexovo
číslo řádku jako odkaz na stav před některou z mých dřívějších oprav.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `_snapshot_db` nemá časový limit:** ostrý bod - ověřil
  jsem si Python `sqlite3.Connection.backup()` API (`progress` parametr,
  volaný periodicky po dávkách stránek, výjimka z něj se propaguje ven) -
  přesně tenhle mechanismus jde použít jako deadline. Přidán `timeout`
  parametr (výchozí 30 s) + `progress` callback kontrolující `time.
  monotonic()`.
- **IMPORTANT - obnova ze zálohy nepočítá s WAL sidecary:** souhlasím s
  opravou (cheap, defenzivní), i když jsem si znovu ověřil (jako v kole
  14), že `state.connect()` WAL nepoužívá - dnešní riziko je teoretické,
  budoucí ne. Recept teď explicitně zmiňuje smazání `-wal`/`-shm` PŘED
  `os.replace`.
- **IMPORTANT - chybová tabulka "jen fluency → přijato" odporuje
  `_polish_rejected`:** ověřil jsem přímo - `_to_finding`'s `action`
  závisí VÝHRADNĚ na `severity` (`"revise" if severity == "critical"
  else "note"`), `type` do tohohle vůbec nevstupuje. Kritický `fluency`
  nález má `action="revise"` a `_polish_rejected`'s pravidlo 2 ho odmítá
  bez ohledu na `type` - tabulkový řádek "jen fluency → přijato" byl
  fakticky nepravdivý. Opraveno + přidán regresní test.
- **NIT - test zálohy vyžaduje bytovou shodu, nevhodné pro `backup()`:**
  ověřil jsem přímo - `sqlite3.Connection.backup()` kopíruje na úrovni
  STRÁNEK přes SQLite vlastní mechanismus, ne syrových bajtů souboru
  (na rozdíl od `shutil.copy2`, co jsem nahradil v kole 14) - výsledek
  nemusí být bajtově identický, i když je logicky STEJNÝ. Tohle je
  přímý, nezamýšlený důsledek kolo-14 změny, co jsem si sám nevšiml.
  Test přepsán na logickou rovnocennost (obsah tabulek/integrity_check),
  ne hash.
- **NIT - próza kolem `shutil.copy2` na jiných místech:** viz vlastní
  grep sweep výš - nic dalšího nenalezeno.
- **NIT - Rozhodnutí kolo 9 bez poznámky o kolo-14 náhradě:** ověřeno,
  chybělo (na rozdíl od kolo 7/8, co POZN. dostaly v kole 12). Doplněno.
- **NIT - `critic.review()` docstring nepočítá s `polish` kontextem:**
  ověřil jsem - docstring tvrdil jen "pipeline udělá flagged kapitolu",
  ale STEJNÁ `pipeline._run_critic` volaná z `_polish_one_chapter` vede
  k `outcome="rejected"` BEZ jakékoli změny statusu v DB - kvalitativně
  jiný výsledek stejné výjimky podle volajícího kontextu. Docstring
  rozšířen na oba případy.

## Claude VERDICT

Po aplikaci 3 IMPORTANT + 4 NITS z kola 15 (vlastní sweep nenašel nic
dalšího nad rámec Codexem citovaného) nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 15: Codex našel 3 IMPORTANT (0 BLOCKING, druhé kolo v řadě) + 4
NITS. Nejzávažnější: (1) `_snapshot_db` dostala časový limit přes
`progress` callback - `backup()` sama by mohla viset neomezeně na
zamčené DB; (2) obnova ze zálohy teď počítá s `-wal`/`-shm` sidecary
(obrana proti budoucí, ne dnešní, hrozbě); (3) chybová tabulka "jen
fluency → přijato" byla fakticky nepravdivá - `action` závisí na
`severity`, ne na `type`, kritický fluency nález se odmítá. Vedlejší
zjištění vlastní opravy: `sqlite3.backup()` (kolo 14) nekopíruje bajt po
bajtu jako `shutil.copy2`, takže "bytově identický" test claim byl
nechtěně rozbitý - opraveno na logickou rovnocennost. Design je teď
kompletní, 0 BLOCKING dvě kola v řadě, IMPORTANT trend 4→3→3 - čeká se
na kolo 16 Codexu (uživatel mezitím vypíná codex pluginy kvůli
opakovaným zaseknutím startu).
