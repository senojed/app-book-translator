# Round 12 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **BLOCKING - `require_lock()` kontrola v `PipelineLLMClient.complete()`
  (kolo 11 fix) ověřovala zámek jen PŘED `self._inner.complete(...)`,
  ne TĚSNĚ před `record_llm_call` ve `finally`.** Souhlas - skutečné
  síťové volání leží MEZI kontrolou a zápisem, zámek může zmizet právě
  BĚHEM něj. Přidána DRUHÁ kontrola přímo ve `finally`, PŘED `record_
  llm_call` - na rozdíl od kontroly PŘED voláním (kde raději `FatalRun
  Error`, protože ještě nic neproběhlo) tahle DRUHÁ kontrola při selhání
  JEN VYNECHÁ auditní zápis, NEVYHODÍ výjimku - `_inner.complete()` už
  proběhlo (peníze utracené, výsledek existuje), zahodit HOTOVÝ výsledek
  kvůli neschopnosti zapsat diagnostický řádek by byl horší výsledek než
  jeden chybějící audit záznam (stejná filosofie jako `finish_run`
  re-check, Task 10 kolo 10). Nový test: `require_lock` vrátí `True`
  před voláním, `False` těsně před zápisem - výsledek se VRÁTÍ, žádný
  audit řádek se NEZAPÍŠE.
- **IMPORTANT (NIT) - `toggleResolved` komentář tvrdil, že "Uložit na
  resolve NEČEKÁ" - zastaralé od kola 8 (`PENDING_RESOLVE_PROMISES`).**
  Opraveno - komentář teď vysvětluje PŘESNĚ: Uložit čeká jen na resolve
  požadavky běžící V OKAMŽIKU kliknutí, nový resolve start PO tomhle
  okamžiku čekáním nekrytý zůstává, takže dohledání podle `id` (kolo 7
  fix) pořád platí jako pojistka.

### Agreed (částečně) + zpřesněno
- **IMPORTANT - kolo 11 tvrdilo "`assign_ids` je čistě aditivní", Codex
  správně namítl, že `_valid_entries` maže ne-dict položky a `assign_ids`
  koerzuje `_STR_FIELDS` typy - obojí JSOU modifikace.** Souhlas s
  FAKTICKOU nepřesností, oprava textu. Závěr (žádný automatický
  rollback) ale zůstává - z PŘESNĚJŠÍHO důvodu: odstraňovaná/koerzovaná
  data jsou VŽDY garbage (platný nález je vždy typovaný `dict`), žádný
  legitimní nález se neztrácí, a je to viditelně ohlášené. Skutečná
  chyba, kterou Codex ve stejném bodě našel a kterou plně přijímám BEZE
  ZBYTKU: obě zálohy (`backup_path`/`history_backup_path`) měly PEVNÉ
  jméno - druhé spuštění (po neúspěchu) by přepsalo zálohu z prvního
  běhu, ztráta PRAVÉ zálohy pre-migračního stavu. Opraveno - `if not
  os.path.exists(...)` kolem obou `shutil.copy2` volání, záloha se
  zapíše jen jednou.

## Claude VERDICT

CHANGES_NEEDED (1 reálný BLOCKING oprava, 1 IMPORTANT zpřesněn+opraven
- backup bug plně přijat, rollback návrh dál zdůvodněně odmítnut, 1 NIT
opraven)

## Summary for log

Kolo 12 potvrzuje vzorec z kola 8→9→10→11 - Codex nachází další vrstvu
STEJNÉHO problému (lock-check timing), tentokrát v `PipelineLLMClient`
samotné, po dvou předchozích kolech (10 `finish_run`, 11 `_client_
factory`/start handleru). Migrace-rollback debata (kolo 5→11→12) se
posunula - kolo 12 opravilo FAKTICKOU nepřesnost v mém odůvodnění, ale
závěr zůstal stejný z jiného, přesnějšího důvodu; ZÁROVEŇ odhalilo a
opravilo skutečný, nezávislý bug (pevně pojmenované zálohy přepsané při
retry) - ukázka, že "částečný nesouhlas" neznamená ignorovat zbytek
bodu.
