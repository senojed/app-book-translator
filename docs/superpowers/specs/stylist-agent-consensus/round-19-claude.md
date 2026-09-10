# Round 19 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní nad rámec Codexova)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Codex citoval "stale shutil.copy2 prózu" na řádcích 1248-1257 a 1369-1373
- POPÁTÉ V ŘADĚ (kola 15-19). Ověřil jsem přímo: řádek ~1370 už
  explicitně říká "`_snapshot_db` (kolo 14 IMPORTANT nahradilo
  `shutil.copy2`, viz jeho docstring)", ostatní jsou historicky rámované
  ("Dřív (kolo 13)"). Žádný neoprávněný current-tense výskyt. Beru to
  jako ustálený artefakt Codexova přepočítávání řádků proti verzi
  dokumentu před mými opravami v témže kole - NENÍ to reálná mezera.

## On Codex's points

### Agreed + fixed
- **BLOCKING - agentní CLI nad textem knihy s ověřeným čtením celého
  disku není bezpečné k nasazení:** Codex má pravdu, že kolo-18 "zdokumentuj
  + canary test" NESTAČÍ - exfiltrace nastane uvnitř Codexova běhu, dřív
  než guardraily. Předložil jsem uživateli/vlastníkovi projektu 4
  varianty (opt-in gate / neagentní API / kontejner / odložit). Rozhodl
  pro variantu 1 (opt-in), s otázkou, jestli jde pozdějí přejít na 2/3 -
  jde, protože design od začátku izoluje `stylist.polish()` jako jediné
  místo, co mluví s Codexem. Implementováno: `config.STYLIST_ACCEPT_FS_
  RISK = False` default, `_cmd_polish` bez `is True` rovnou odmítne s
  hláškou o riziku. Nová spec sekce "Bezpečnostní rozhodnutí (kolo 19)"
  s ověřeným nálezem, rozhodnutím i migrační cestou.
- **IMPORTANT - spy na `sqlite3.Connection.backup` nejde
  (`TypeError`):** ověřil jsem si Python sémantiku - `sqlite3.Connection`
  je immutable C typ, `setattr` na jeho metody selže. Test scénář
  přepsán na proxy connection z monkeypatchnutého `main.sqlite3.connect`
  (na 2 místech - prose i Rozhodnutí bullet).
- **IMPORTANT - canary checklist neobsahuje `--ignore-user-config`:**
  přesný bod - a je to symptom hlubšího problému (argv na 3 místech).
  Zaveden `_codex_argv` helper jako JEDINÉ místo skládání argv, `polish`
  ho volá, argv test i canary checklist ho odkazují.
- **NIT - kolo-17 Rozhodnutí bullet stále "NEOVĚŘENO":** ověřeno,
  doplněna POZN. o kolo-18 živém testu.

## Claude VERDICT

Po aplikaci 1 BLOCKING (opt-in gate, rozhodnutí uživatele) + 2 IMPORTANT
+ 1 NIT z kola 19 nenacházím nic dalšího. Bezpečnostní blocker je
vyřešen na úrovni, co Codex sám označil za přijatelné minimum ("nesmí
být standardně dostupný" - teď není).

`CONSENSUS`

## Summary for log

Kolo 19: Codex ESKALOVAL kolo-18 bezpečnostní nález na BLOCKING (agentní
`codex exec` čte celý disk, exfiltrace přes prompt injection nastane
dřív než guardraily - dokumentace + canary nestačí). Uživatel rozhodl
pro variantu 1: povinný opt-in `config.STYLIST_ACCEPT_FS_RISK = True`
(default `False`), `polish` bez něj neběží. Nová spec sekce
"Bezpečnostní rozhodnutí (kolo 19)" + explicitní migrační cesta na
neagentní API / kontejner (jde odložit - riziko je celé uvnitř
`stylist.polish()`). Dál: `_codex_argv` helper (argv byl na 3 místech,
canary checklist neměl `--ignore-user-config`); spy test na `pages=100`
přes proxy connection (`sqlite3.Connection` je immutable C typ). Stale
shutil.copy2 NIT popáté v řadě - ověřeno, není reálná mezera. Čeká se na
kolo 20 Codexu.
