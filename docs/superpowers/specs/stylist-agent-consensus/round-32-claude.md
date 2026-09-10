# Round 32 — Claude critique

Šesté review kola-27 dodatku. Codex 2 IMPORTANT + 3 NITS - obojí fallout
z kola 31. Úzké, navazující.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `STYLIST_REPORT_REJECTED_TEXT` obecná truthiness:**
  správně - pro bezpečnostní opt-in `1`/`"False"`/`None` NESMÍ plný
  detail aktivovat (stejný vzor jako `STYLIST_ACCEPT_FS_RISK is not
  True`, kolo 19-20). → `is True` na obou kódových místech: `polish()`
  stderr větev, `_polish_one_chapter`'s `full =`.
- **IMPORTANT - `_write_polish_report` docstring opakuje odmítnutý
  rationale:** kolo 31 rozhodlo, že perzistence je SAMOSTATNÉ riziko, ne
  "uvnitř přijatého FS rizika" - docstring to pořád tvrdil. Přepsáno.

### NITS - fixed
- `stylist.polish` komentář "za opt-outem" → "opt-in" (default `False`).
- sekce "Kolo 27+" pořád popisovala dedup přes `(type, term_id)` →
  `_finding_key`.
- chybová tabulka vynechávala `run_id` v hlavičce reportu.

## Claude VERDICT

`CHANGES_NEEDED` - 2 IMPORTANT, oba navazující na kolo-31 změny.
Aplikováno. Kolo 32 = čistě dolaďování kola 31, žádné nové oblasti.
Čeká se na kolo 33.

## Summary for log

Kolo 32: 2 IMPORTANT + 3 NITS, obojí fallout z kola 31. (1)
`STYLIST_REPORT_REJECTED_TEXT` obecná truthiness → `is True` na obou
místech. (2) `_write_polish_report` docstring pořád opakoval odmítnutý
"uvnitř přijatého FS rizika" rationale → přepsáno. NITs: "opt-out" →
"opt-in", stale dedup próza, `run_id` v tabulce. Čeká se na kolo 33.
