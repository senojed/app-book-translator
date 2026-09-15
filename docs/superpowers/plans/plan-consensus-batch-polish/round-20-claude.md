# Round 20 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **BLOCKING - kolo-19 `drop_stale_non_markers=True` (bez rozlišení)
  odporuje existujícímu, PŘED-kolem-19 testu `test_save_chapter_text_
  change_does_not_wipe_finding_added_via_light_write` (kolo 4).**
  Ověřeno přímo simulací obou scénářů - Codex má pravdu, obojí najednou
  nejde splnit prostým "zahoď, co není v incoming". Přepracováno na
  `known_ids` parametr místo bool flagu - `_merge_findings_by_id`
  dostává TŘETÍ množinu (`PERSISTED_IDS` z klientova GET, poslaná v
  novém `known_ids` poli save payloadu), co rozlišuje "klient tenhle
  nález ZNAL a superseduje ho" (smaž) od "klient o něm NIKDY nevěděl -
  přidal ho JINÝ požadavek mezitím" (zachovej vždy). Ověřeno, že OBA
  scénáře (kolo 4 test i kolo 19 test) teď vychází správně - kolo-4 test
  neposílá `known_ids` vůbec (default `[]` → nic se neznalo → nic se
  nemaže, PŮVODNÍ chování zachováno), kolo-19 test teď explicitně posílá
  `known_ids: ["old-f1"]` (simuluje, že klient ten nález VIDĚL při GET).
  Přidána validace tvaru `known_ids` (400 na non-string položky) + test
  na bezpečný fallback při chybějícím poli.

- **IMPORTANT - migrace (Task 13 Step 8) zálohovala DB přes `shutil.
  copy2`, což VLASTNÍ existující `_snapshot_db` docstring (main.py,
  kolo 14 tamního ping-pongu, PŘED-existující kód) výslovně zakazuje -
  prostý copy může zachytit nekonzistentní stav, neumí WAL/SHM.** Můj
  vlastní komentář u toho tvrdil "tady to je OK, není to server" -
  NEPRAVDIVÉ zdůvodnění (riziko nesouvisí s tím, kdo zálohu spouští).
  Opraveno - `shutil.copy2` nahrazeno `main._snapshot_db`, selhání
  zastaví CELOU migraci PŘED jakýmkoli zápisem (stejný vzor jako
  existující "historie se nenačte → STOP" větev). Historie (JSON,
  žádné WAL/multi-file obavy) zůstává na `shutil.copy2` beze změny -
  správně, ne totéž riziko.

## Claude VERDICT

CHANGES_NEEDED (souhlas s oběma, plná implementace + přepracování
vlastní kolo-19 opravy)

## Summary for log

Nejvýznamnější kolo od kola 19 - Codex odhalil, že MOJE VLASTNÍ oprava
z minulého kola porušila existující, dobře zdůvodněný test z kola 4 -
"drop chybějící" bylo příliš hrubé řešení. `known_ids` (odvozené z
klientova PERSISTED_IDS) je přesnější náhrada, co uspokojuje OBA
scénáře současně, ne kompromis. Druhý bod je podobná chyba jinde - moje
vlastní (nesprávné) zdůvodnění u `shutil.copy2` v migračním skriptu
odporovalo existující, staré dokumentaci `_snapshot_db`. Vzorec "moje
vlastní oprava zavedla novou chybu, Codex ji chytil další kolo" se
objevil poprvé od kola 13 (fixture signature) - důležité nezlevňovat
ostražitost ani po 19 předchozích kolech.
