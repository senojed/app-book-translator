# Round 8 — Claude critique

Codex: CHANGES_NEEDED (1 IMPORTANT, 1 NIT). Obojí test-rigor.

## Claude's own findings
Žádné nové vlastní.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - canary nelze vyhodnotit:** kolo-7 runner nedržel token v proměnné a `finally` mazal T1/T2 před vyhodnocením → vytištěný výstup nešlo porovnat, jakýkoli vymyšlený hex by "prošel". **Fix:** `token = secrets.token_hex(16)` do proměnné; `leaked = token in out/err/out_file` VYHODNOCENO uvnitř `try` PŘED `finally`; `print("RETURNCODE:", proc.returncode)` + `assert returncode == 0` (neúspěšné spuštění = canary nevyhodnotitelný, ne negativní výsledek).
- **NIT - Task 8 integrační test slabý:** samotné `True` nedokazuje větev počtu výskytů (mohl vzniknout nový klíč). **Fix:** před `_polish_rejected` assert `len(base_leaks)==1 and len(after_leaks)==1` a shodné `_finding_key` množiny → `True` může přijít JEN z počtu výskytů.

### Disagreed
Žádné.

## Claude VERDICT

`CHANGES_NEEDED` - 1 IMPORTANT + 1 NIT, obojí zpřísnění testů, aplikováno. Vlastních 0. Konsensus na dosah.

## Summary for log

Kolo 8: Codex 1 IMPORTANT + 1 NIT, obojí test-rigor. Canary runner: token do proměnné + vyhodnocení před úklidem + returncode check. Task 8 integrace: assert předpokladů (1 leak, shodný klíč) → True dokazuje jen počet-výskytů větev. Sporné: 0. 0 BLOCKING 5 kol, IMPORTANT jen o testech.
