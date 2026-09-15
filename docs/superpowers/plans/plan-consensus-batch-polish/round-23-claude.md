# Round 23 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `assign_ids`'s `if not f.get("id"):` nechávalo TRUTHY,
  ale NE-STRING `id` (např. `id: 123`) beze změny - GET by ho vrátilo
  klientovi, ale resolve/save (vyžadují `str`) by ho NAVŽDY odmítly -
  trvalý mrtvý nález. Duplicitní `id` v jedné dávce taky nebyly řešené,
  přestože merge/resolve předpokládají unikátnost.** Ověřeno čtením -
  potvrzeno, `_valid_entries` (migrace, Task 13 Step 8) filtruje jen
  ne-dict položky, ne shape `id` uvnitř dict - pre-Task-2 data v
  `chapters.notes` TEORETICKY mohla mít cokoli pod klíčem "id".
  `_valid_finding_shape` (Task 9 save) naopak KLIENTSKÝ vstup s
  ne-string `id` už odmítá (400) - problém je specificky v migraci
  starých, needitovaných dat. Opraveno - `assign_ids` teď sleduje
  `seen_ids` (lokálně, jen pro JEDNU dávku, stejný rozsah jako
  `_no_duplicate_ids`) a `id` je "platné, zachovej" jen když je `str`,
  neprázdné, A ještě NEVIDĚNÉ v týhle dávce - jinak nové `uuid4().hex`.
  2 nové testy (`test_assign_ids_replaces_non_string_id`, `...
  _duplicate_ids_within_same_batch`) - samostatný end-to-end test
  migračního skriptu se nepřidává (skript zůstává mimo test-pokryté
  soubory, viz kolo 11/12/20 zdůvodnění; jeho korektnost tady stojí
  ČISTĚ na `assign_ids`, co je teď přímo otestovaná).

## Claude VERDICT

CHANGES_NEEDED (souhlas, plná implementace)

## Summary for log

Kolo 23 - jediný bod, žádný spor. Zajímavé, že tenhle bug existoval od
Tasku 2 (kolo 1) a přežil 22 kol ping-pongu, dokud ho Codex nenašel
skrz kombinaci dvou různých částí plánu (assign_ids + migrace) - typ
nálezu, co je snadné přehlédnout při čtení jen JEDNÉ funkce izolovaně.
