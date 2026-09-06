# Round 7 — Claude critique (plán)

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Codexové 2 BLOCKING jsou reálné (nedefinovaná
proměnná v `apply_answer`, chybějící `g` v `run`). Zbytek atomicita/robustnost.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `run` nenačítá `g` (guide)** — opraveno: `g = guide.load_guide(
  config.GUIDE_PATH)` před smyčkou; test `test_run_without_guide_json_still_works`
  (prázdný shape → `run` funguje bez `review`).
- **BLOCKING: `apply_answer` používá nedefinované `scope_key`** — opraveno:
  `scope_key = q["scope_key"]` na začátku, přepsáno na `answer_text`/`q[...]`.
- **IMPORTANT: `apply_answer` - answer_question první, pak glossary/guide** —
  opraveno: pořadí = guide.json (atomický zápis) → DB změny v jedné transakci
  (glossary + answer_question + requeue). `save_guide`/`save_draft` teď atomické
  (temp + `os.replace`).
- **IMPORTANT: lock "soubor neexistuje → zapiš" není atomické** — opraveno:
  `os.open(O_CREAT|O_EXCL)` atomické vytvoření; `FileExistsError` → staleness
  check → atomický takeover přes `os.replace`.
- **IMPORTANT: `seed_from_guide` nechrání `cz`/`accepted_alt` u approved** —
  opraveno: approved řádek → reseed nesahá na `cz`/`status`/`accepted_alt`, jen
  sjednotí aliasy. Test `test_seed_does_not_overwrite_approved`.
- **IMPORTANT: blocking `scope_key` lowercased → ztráta povrchu** — opraveno:
  `_parse` blocking `scope_key` jen `.strip()`, NE lowercase (použije se jako
  `canonical_en`). `resolve_surface` je case-insensitive, takže lookup funguje.
- **IMPORTANT: `count_tokens` fail → `len/4` podcení** — opraveno: `len/2`
  (konzervativní nadhad). Test `test_count_tokens_failure_uses_conservative_estimate`.
- **IMPORTANT: `scan` lifecycle netestován** — opraveno:
  `test_scan_scout_truncated_is_fatal_no_draft`, `test_scan_scout_bad_json_is_fatal`.
- **NIT: stale lock neparsovatelný `ts`** — opraveno: "JSON/ts nejde zparsovat
  → stale". Test `test_unparseable_lock_is_treated_as_stale`.
- **NIT: model** — Codex ověřil, bez akce.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 2 BLOCKING (Codex) reálné (nedefinovaná proměnná, chybějící
`g`). Claude 0 vlastních. Zbytek atomicita + test coverage. Rozsah klesá.

## Summary for log
Kolo 7: Codex 2 BLOCKING (run nenačítá guide; apply_answer nedefinované
scope_key) + 6 IMPORTANT (apply_answer ordering/atomicita; lock O_EXCL;
seed_from_guide approved ochrana cz/accepted_alt; blocking scope_key lowercase
ztráta povrchu; count_tokens fail len/4 podcení; scan lifecycle testy) + 2 NIT.
Claude 0 vlastních. Opraveno: g=load_guide v run; scope_key=q[...];
save_guide/save_draft atomické (temp+os.replace); lock os.open(O_EXCL); reseed
nesahá na approved cz/accepted_alt; blocking scope_key neztrácí velikost písmen;
count_tokens fallback len/2. Sporné: nic.