# Round 9 — Claude critique (plán)

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Codex poprvé bez BLOCKING - 4 IMPORTANT jsou
dotažení detailů (place kind, blocking alts id, stale metadata mention,
atomicity test síla).

## On Codex's points

### Agreed + fixed
- **IMPORTANT: `must_decide` pro places - `kind:"place"` nedefinovaný,
  `apply_must_decide` nemá place větev** — opraveno: `merge_scout_facts` `kind`
  = name/place/term podle sekce; `apply_must_decide` má `place` větev →
  `payload["places"]`.
- **IMPORTANT: blocking term/name s alternativami - `tid_or_new` nedefinované
  před transakcí** — opraveno: `target_tid = tid or ("term_" + slugify(scope_key))`
  (deterministické, stejné jaké `add_approved` vytvoří); `glossary_ops` i
  `requeue_idxs` používají `target_tid`. Test
  `test_blocking_answer_with_alternatives_creates_approved_with_alts`.
- **IMPORTANT: `extra_mentions` `cz_form=nt["cz"]` neověřeno proti finálnímu cz** —
  opraveno: `mention_form = nt["cz"] if concordance.contains_form(cz, nt["cz"])
  else None`; `source = "rendered"` jen když je forma v textu, jinak
  `"omission"` (kapitola zůstane v requeue scope, ale nešpiní drift falešným
  tvarem).
- **IMPORTANT: atomicity test slabý (bez `new_candidates`)** — opraveno: test
  má validní `new_candidates` řádek + FK-vadnou mention → assert že po rollbacku
  je pryč kandidát, otázka, translated_text, status zůstane `processing`.
- **NIT: Task 7 testy bez `terms`** — opraveno (3 payloady).
- **NIT: `must_decide` konflikt objekty - všechna pole** — opraveno: `{kind,
  scope_key, question, default}`.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 0 BLOCKING (Codex poprvé), 4 IMPORTANT (detaily). Claude 0
vlastních. Blízko konsenzu - 1-2 potvrzovací kola.

## Summary for log
Kolo 9: Codex 0 BLOCKING, 4 IMPORTANT (place kind + apply_must_decide větev;
blocking alts target_tid deterministické; extra_mentions ověřit cz_form proti
finálnímu textu; atomicity test s new_candidates) + 2 NIT. Claude 0 vlastních.
Vše přijato. Poprvé bez BLOCKING - konverguje.