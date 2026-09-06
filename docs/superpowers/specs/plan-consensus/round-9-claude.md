# Round 9 — Claude critique

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Codexových 5 bodů = poslední konzistence
`Finding`/`term_id`/CLI. Architektura beze změny 5 kol.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `Finding` neunese potřeby concordance question (term_id, routing)**
  — opraveno: `Finding` má `action: revise|question|note` + `term_id`. Pipeline
  routuje podle `action`. Doplněna tabulka mapování (kritik critical→revise,
  minor→note; concordance leak/approved-inconsistency→revise, candidate-
  inconsistency→question, omission→note).
- **IMPORTANT: `rendered_terms` bez `scene_idx`, revize "nahradí" metadata** —
  opraveno: translator `scene_idx` NEhlásí; pipeline ho doplní u fresh scén,
  revizní celokapitolový výstup → `scene_idx = NULL` (`term_mentions.scene_idx`
  je nullable).
- **IMPORTANT: reseed delete+insert rozbije FK `term_id`** — opraveno:
  deterministické `term_id` (`slug(canonical_en)` u seed, `cand_<slug>` u
  kandidáta); reseed = UPDATE podle `term_id`, nový → INSERT, odebraný →
  ponechán. FK z `term_mentions`/`questions` zůstávají platné.
- **IMPORTANT: `run --retry-flagged` chybí v CLI/build/test** — opraveno:
  doplněno do seznamu příkazů (`run --retry-flagged [IDX...]`, resetuje
  `revision_rounds=0`), do stavového automatu, build kroku 8 a test vrstvy 2.
- **IMPORTANT: `new_terms` dedup podle povrchu vs "term_id řeší homonyma"** —
  opraveno: přiznané omezení v1 - translatorem nalezené `new_terms` se
  deduplikují podle povrchu; split povrchu na 2 entity je ruční `answer`
  operace.
- **NIT: "partial UNIQUE" DDL** — opraveno: zapsáno jako dva samostatné
  `CREATE UNIQUE INDEX ... WHERE answer IS NULL`, ne inline constraint.
- **NIT: model předpoklad** — Codex ověřil OK, bez akce.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 0 vlastních. Codexův 1 BLOCKING byl Finding schema (reálná
mezera), zbytek konzistence. Po tomto kole by měl být Finding/term_id/CLI
model uzavřený. Poslední kolo (10) jako finální kontrola.

## Summary for log
Kolo 9: Codex 1 BLOCKING (Finding schema neunese concordance question) + 4
IMPORTANT + 2 NIT. Claude 0 vlastních. Opraveno: `Finding` +`action`+`term_id`
s routing tabulkou; `scene_idx` doplňuje pipeline ne translator (revize→NULL);
deterministický `term_id` + reseed jako UPDATE (FK integrita); `run
--retry-flagged` doplněn do CLI/automatu/buildu/testů; přiznané v1 omezení
new_terms dedup podle povrchu; partial unique jako CREATE INDEX WHERE.
Sporné: nic.