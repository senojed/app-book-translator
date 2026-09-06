# Round 5 — Claude critique (plán)

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Codexový 1 BLOCKING (Windows lock) reálný,
zbytek precizace nedospecifikovaných míst (chunking, drift scheduling, field
name konverze).

## On Codex's points

### Agreed + fixed
- **BLOCKING: `os.kill(pid, 0)` na Windows volá `TerminateProcess`** — opraveno:
  `_pid_alive` platform-specific - POSIX `os.kill(pid, 0)`, Windows
  `ctypes ... OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`. Lock navíc přebírá
  zámek starší 6 h.
- **IMPORTANT: `style_notes`→`style`, `suggested_cz`→`cz` konverze nejasná** —
  opraveno: `merge_draft_and_guide` VÝSTUP používá finální názvy polí,
  předvyplněné z draft `suggested_*`. Explicitní mapování per sekce + test
  `test_merge_translates_draft_field_names_to_final`.
- **IMPORTANT: `apply_answer` ztrácí `accepted_alt`** — opraveno: syntaxe
  odpovědi `"cz"` nebo `"cz | alt1 | alt2"`; první = kanonický `cz` (promote),
  zbytek → `add_accepted_alt`.
- **IMPORTANT: `scan --chunked` chunking algoritmus nedefinovaný** — opraveno:
  `scout.chunk_chapters(chapters, word_limit)` - greedy packing pod
  `config.SCOUT_CHUNK_WORD_LIMIT = 40000`. CLI `scan --chunked` volá
  `chunk_chapters(chs, ...)`. Test `test_chunk_chapters_greedy_packs_under_limit`.
- **IMPORTANT: cost guard akceptuje strop < spent+est** — opraveno: `new_limit >=
  spent + est` povinné, jinak reprompt/`FatalRunError`. Test
  `test_cost_guard_rejects_ceiling_below_need`.
- **IMPORTANT: drift scheduling nepřesné** — opraveno: po každém `done`/`flagged`
  commitu, `n = done+flagged count`, `n % CROSS_REF_EVERY_N == 0` → `run_drift_check`.
  (Počítá hotové kapitoly, ne `idx`.)
- **NIT: Task 14 "8" → 7**, **Task 5 "8" (nyní opravdu 8)**, **Task 11 "6" → 7**.
- **NIT: Task 16 validace vyjmenovat required pole** — opraveno.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 1 BLOCKING (Windows lock, reálné), 6 IMPORTANT (vše precizace
nedospecifikovaných míst). Claude 0 vlastních. Rozsah čistě detail, ne
architektura.

## Summary for log
Kolo 5: Codex 1 BLOCKING (os.kill na Windows = TerminateProcess) + 6 IMPORTANT
(field name konverze, accepted_alt syntaxe, chunking algoritmus, cost guard
strop pod need, drift scheduling přesně) + 3 NIT. Claude 0 vlastních. Opraveno:
`_pid_alive` platform-specific (ctypes na Windows) + 6h staleness; merge výstup
= finální názvy polí; odpověď `"cz | alt | alt"` → accepted_alt; `chunk_chapters`
greedy pod SCOUT_CHUNK_WORD_LIMIT; cost guard `new_limit >= spent+est`; drift
po done/flagged commitu podle count % N. Sporné: nic.