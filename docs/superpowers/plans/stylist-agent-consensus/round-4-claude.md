# Round 4 — Claude critique

Codex: CHANGES_NEEDED (3 IMPORTANT, 0 BLOCKING). Konvergence: 1B→0B.

## Claude's own findings
Žádné nové vlastní.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - append invariant má mezeru:** spec `report.append(rec)` (1913) je MIMO vnitřní `try`; KI mezi návratem `_polish_one_chapter` a appendem přeskočí kapitolu (uniká i in-loop `except KeyboardInterrupt` - ten je na už dokončeném `try`). Reálné okno (bytecode boundary), byť úzké. **Fix:** Task 12 Step 3.1 odchylka - tělo iterace obalené `try/finally`, append v `finally` s identitní stráží (`report[-1] is not rec`). Fatal/interrupted větve si `rec` staví PŘED `raise`, `finally` je pak zapíše. +test `test_cmd_polish_report_records_every_iteration` (mock `_polish_one_chapter` na pevnou sekvenci, ověří 4/4 záznamy, pořadí, summary).
- **IMPORTANT - redakce není testovaná ve skutečných větvích** (kolo 1 nález, teď ostřeji): `_redact_detail` unit test dokazuje jen helper; `test_polish_raises_on_nonzero_exit` neposílá secret; strukturální testy kontrolují jen `match=` kategorii. Odstranění `_redact_detail` ze 4 produkčních větví `polish()` by prošlo. **Fix:** Task 5 Step 1c - parametrizovaný `test_polish_redacts_all_codex_derived_error_values` přes `(False,1,"False",None,True)` × {stderr secret, změněné číslo, počet odstavců, poměr délky}, +`_fake_codex_stderr` helper. "Executor doplní" zrušeno.
- **IMPORTANT - Task 13 neposkytuje důkazy pro ruční kontrolu:** `polish()` zahazuje Codex stdout/stderr; zamítnutý text se default maže; `force=False` může kapitolu přeskočit → ověření vakuové. **Fix:** (a) MCP/config/kontext pozorování přesunuto do Step 2 (přímé `codex exec`, stdout viditelný) + druhý přímý běh s reálným EN+CZ na eyeball kvality; (b) Step 3 skript: `STYLIST_REPORT_REJECTED_TEXT=True` (jen v TMP), `force=True` POVINNÉ, assert `attempted_count >= 1` (kapitola skutečně prošla, ne přeskočena).

### Disagreed
Žádné.

## Claude VERDICT

`CHANGES_NEEDED` - 3 Codex IMPORTANT platné, aplikováno. Vlastních 0.

## Summary for log

Kolo 4: Codex 3 IMPORTANT (0 BLOCKING), Claude 0 vlastních. IMPORTANT: (1) append invariant - okno KI mezi návratem helperu a appendem → append přesunut do `finally` s identitní stráží + test úplnosti; (2) redakce netestovaná ve skutečných větvích → parametrizovaná matice stderr/číslo/odstavce/poměr × 5 hodnot flagu; (3) Task 13 bez důkazů → Codex pozorování do přímého Step 2, Step 3 `force=True` + `REPORT_REJECTED_TEXT=True` v TMP + assert kapitola prošla. Sporné: 0. Konvergence B: 3→0→1→0.
