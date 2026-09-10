# Round 9 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem udělal vlastní grep sweep na starý přímý
`shutil.copy2(db, backup_path)` zápis (nahrazený snapshot+`os.replace`
promocí), starý `backup_state = {"done": False}` literál (teď musí nést i
`snapshot_path`), `_kill_process_tree(pid)` a `codex_cmd: str` vzory - nic
z toho nezůstalo. Navíc jsem doplnil test scénář, co v dokumentu chyběl:
neprázdné `chapters`, ale VŠECHNY skončí jinak než přijetím → dočasný
`.pre-polish-snapshot` se uklidí, žádný `.pre-polish-backup` nevznikne ani
se nepřepíše - nová dvoufázová snapshot/promote logika (kolo 9 BLOCKING
oprava) tohle chování nemá odkud "zdarma" zdědit z předchozí (kolo 8)
jednofázové implementace, tak jsem to explicitně přidal jako vlastní
doplněk.

## On Codex's points

### Agreed + fixed
- **BLOCKING - časování zálohy DB pořád nezachytávalo skutečný
  pre-invocation stav:** ověřil jsem přímo v dokumentu - `state.
  create_run` a kritik/`check_meaning_preserved` volané i pro kapitoly,
  co skončí `rejected`/`failed`, zapisují do DB PŘED bodem, kde `_backup_
  db_once` (kolo 8 verze) vůbec poprvé proběhne. Přepracováno na
  dvoufázový mechanismus: `_cmd_polish` pořídí `shutil.copy2` snapshot do
  DOČASNÉHO souboru HNED po ověření, že `chapters` není prázdné (PŘED
  `create_run`), `_backup_db_once` ho pak jen atomicky PROMUJE
  (`os.replace`) na kanonickou `.pre-polish-backup` cestu těsně před
  prvním skutečným zápisem výsledku. Nepromovaný snapshot se uklidí ve
  `finally`.
- **IMPORTANT - `shutil.copy2` na existující zálohu riskuje částečný
  zápis:** vyřešeno STEJNOU opravou jako bod výš - `os.replace` je
  atomické přejmenování na úrovni souborového systému, ne stream kopie,
  takže tenhle bod padá zadarmo spolu s BLOCKING opravou (žádná
  samostatná úprava navíc nebyla potřeba).
- **IMPORTANT - kritik tiše domýšlí neplatné `severity`/`type`:** ověřil
  jsem přímo v `_to_finding` (existující, `src/agents/critic.py`) - `raw.
  get("severity") or "minor"` s `{"severity": 0}` dá `"minor"` (0 je
  falsy), ne chybu. Přidána validace v `review()` PŘED voláním `_to_
  finding` - jakýkoli nález se `severity`/`type` mimo deklarovaný enum
  zneplatní CELOU odpověď (stejná filozofie jako kolo 7 pro nedict
  položky).
- **IMPORTANT - `value in (True, False)` propouští `0`/`1`:** ověřil jsem
  přímo v Pythonu (`0 in (True, False)` → `True`, protože `0 == False`).
  Nahrazeno `isinstance(..., bool)` na obou polích (`meaning_changed`,
  `register_changed`).
- **IMPORTANT - žádný test neověřuje skutečný argv Codex volání:**
  přidán `test_polish_invokes_codex_with_expected_argv` - fake skript
  zapíše svůj `sys.argv` do vedlejšího JSON souboru, test ověří
  `--sandbox read-only`, `--skip-git-repo-check`, `--ephemeral`, `-C`,
  `-o`, `-m <model>` a pozicionální `-` na konci.
- **IMPORTANT - stale próza:** udělal jsem cílený grep sweep na
  konkrétní vzorce (baseline `[]`/rendered_terms, `status="ok"`,
  "neprázdná kapitola vytvoří zálohu", "jen VÝZNAM", "v době, kdy
  kapitola dostala done") - všechny existující výskyty jsou buď (a) už
  opravené v kódu i próze z předchozích kol, nebo (b) legitimní
  historické/kontrafaktuální odkazy ("bez preflightu BY vypsal...",
  "dřív kontrolovala jen VÝZNAM" v minulém čase), ne aktuální nepravdivá
  tvrzení. Jediné SKUTEČNĚ stale místo bylo přímo v kódu/komentářích
  kolem `_backup_db_once`/`_cmd_polish`, které BLOCKING oprava výš stejně
  přepsala. Doplnil jsem novou "Rozhodnutí" bullet sekci pro kolo 9 (5
  bodů) a přejmenoval hlavičku sekce i odkaz na `round-{1..9}-claude.md`.
- **NIT - fail-fast pořadí guardrail vrstev:** `_polish_one_chapter`
  teď volá `_polish_rejected` dvakrát (žádná duplicitní logika) -
  poprvé nad konkordancí+kritikem (zadarmo/už zaplaceno), a `check_
  meaning_preserved` (placené Anthropic volání) se zavolá až když první
  volání nezamítlo.

### Agreed but already addressed
(žádné nové)

## Claude VERDICT

Po aplikaci 1 BLOCKING + 5 IMPORTANT + 1 NIT z kola 9 (vlastní sweep
nenašel nic dalšího nad rámec toho, co Codex označil) nenacházím nic
dalšího.

`CONSENSUS`

## Summary for log

Kolo 9: Codex našel 1 BLOCKING (`_backup_db_once`'s lazy timing z kola 8
pořád nezachytávalo skutečný pre-invocation stav - `create_run`/`llm_calls`
zapisují do DB dřív, než záloha vůbec proběhne) + 5 IMPORTANT (atomicita
promoce přes `os.replace` místo opakovaného `shutil.copy2`; kritik tiše
domýšlí neplatné `severity`/`type`; `isinstance(bool)` mezera u `0`/`1`
jako bool; chybějící argv-assertion test; zbylá stale próza - žádná
nenalezena mimo to, co BLOCKING oprava sama přepsala) + 1 NIT (fail-fast
pořadí guardrail vrstev). Zavedena dvoufázová snapshot-před-`create_run` +
atomická-promoce-při-prvním-zápisu záloha DB - třetí a nejspíš finální
revize tohohle mechanismu. Design je teď kompletní - čeká se na kolo 10
Codexu, jestli konečně potvrdí konsensus.
