# Round 8 — Claude critique (plán)

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Codexové 2 BLOCKING (init bez data/ dir a
init_db; Task 8 stem test data) jsou reálné.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `init` bere lock ale `data/` neexistuje + chybí `state.init_db`** —
  opraveno: `main()` PŘED dispatchem: `_bootstrap_stdout` → `makedirs(DATA_DIR,
  OUTPUT_DIR)` → `state.init_db(DB_PATH)` (idempotentní) → dispatch. `init` už
  jen `seed_chapters`.
- **BLOCKING: Task 8 test `"Fů"` vs `"Fůha"` - `stem` je sjednotí** — opraveno:
  test data `"Šedý plášť"` vs `"Popelář"` (zjevně jiný kmen).
- **IMPORTANT: `new_terms` shoda s existujícím povrchem → "přeskoč" ztratí
  mention** — opraveno: shoda → přidej explicitní mention s resolved `term_id`
  (nezahazuj); jen nový povrch → kandidát.
- **IMPORTANT: `style`/`other` otázky s prázdným `scope_key` - hash(text) remap
  nespecifikován** — opraveno: pipeline normalizuje VŠECHNY questions před
  `commit_chapter_result` (`if not q["scope_key"]: q["scope_key"] =
  sha1(q["text"])[:16]`).
- **IMPORTANT: `apply_answer` atomicita falešná** (helpery každý vlastní connect)
  — opraveno: nová `state.commit_answer(*, qid, answer_text, glossary_ops,
  requeue_idxs, blocking_chapter_idx)` = jedna transakce, SQL nad `conn` (ne
  glossary.py helpery). `apply_answer` = fáze 1 (guide.json atomicky) + fáze 2
  (`commit_answer`).
- **IMPORTANT: stale lock takeover přes `os.replace` není mutually exclusive** —
  opraveno: stale → `os.unlink` + `continue` smyčky (`O_EXCL` retry, kdo vyhraje
  vlastní zámek; max 3 pokusy).
- **NIT: Task 16 valid guide payload bez `terms`** — opraveno: `validate` čte
  `payload.get(section, [])`.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 2 BLOCKING (Codex) reálné, Claude 0 vlastních. Vše atomicita +
init lifecycle + test data. Rozsah dál klesá.

## Summary for log
Kolo 8: Codex 2 BLOCKING (init bez data/ dir a init_db; Task 8 stem test data
"Fů"/"Fůha") + 4 IMPORTANT (new_terms shoda ztrácí mention; style scope_key
hash remap nespecifikován; apply_answer atomicita falešná; stale lock takeover
race) + 1 NIT. Claude 0 vlastních. Opraveno: main() dělá makedirs + init_db
před dispatchem; Task 8 test data jiný kmen; new_terms shoda → explicitní
mention; pipeline normalizuje scope_key všech questions; state.commit_answer
jednotransakční helper; stale lock unlink+O_EXCL retry. Sporné: nic.