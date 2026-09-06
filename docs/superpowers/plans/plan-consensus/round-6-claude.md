# Round 6 — Claude critique (plán)

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Codexové 3 BLOCKING jsou přímé důsledky
kola 5 (merge field names, chunk_chapters typ vstupu, validation order).

## On Codex's points

### Agreed + fixed
- **BLOCKING: `test_merge_keeps_human_decisions` v rozporu s interface** —
  opraveno: test teď očekává `newguy["render"] == "translate"` (předvyplněno
  z `draft.suggested`), konzistentní s interface.
- **BLOCKING: `chunk_chapters` čeká `.raw_text` objekt, CLI předává dict rows** —
  opraveno: `raw = ch["raw_text"] if isinstance(ch, dict) else ch.raw_text`;
  test `test_chunk_chapters_accepts_dict_rows`.
- **BLOCKING: validation PŘED apply_must_decide → nesmyslná odpověď se uloží** —
  opraveno: POST pořadí = (1) must_decide answered check, (2) `apply_must_decide`,
  (3) PLNÁ `validate` VÝSLEDNÉHO payloadu (chytí `address` mimo {tyka,vyka}),
  (4) save.
- **IMPORTANT: Task 11 code fence neuzavřený** — opraveno: ``` doplněno.
- **IMPORTANT: critic failure `action:"note"` nespustí `flagged`** — opraveno:
  explicitní `critic_failed` flag; status pravidlo = `flagged if critic_failed
  or has_revise_triggers`. Test `test_critic_recoverable_failure_flags_chapter`.
- **IMPORTANT: `scan` `ValueError` z `scan_book` bublá jako stacktrace** —
  opraveno: `except (OutputTruncated, ValueError) → FatalRunError` s hláškou.
- **IMPORTANT: must_decide routing testy jen `term`** — opraveno: přidány
  `name`, `relationship` (+ neplatná odpověď 422), `style`, a
  update-existing-not-duplicate.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 3 BLOCKING (Codex) = důsledky kola 5, Claude 0 vlastních.
Rozsah čistě test coverage + konzistence. Chce 1 potvrzovací kolo.

## Summary for log
Kolo 6: Codex 3 BLOCKING (merge test vs interface rozpor; chunk_chapters typ
vstupu dict vs objekt; validation PŘED apply_must_decide) + 4 IMPORTANT
(neuzavřený code fence; critic_failed flag; scan ValueError bublá;
must_decide routing testy jen term). Claude 0 vlastních. Vše přijato.
POST pořadí = answered-check → apply_must_decide → plná validace → save.
critic_failed explicitní flag. must_decide testy pro všechny kind.
Sporné: nic.