# Round 10 — Claude critique

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Po 10 kolech je spec podle mého hodnocení
připravený k implementaci: architektura zmrzlá od kola 4, data model po kolech
5-10 zpřesněný, všech ~50 Codexových bodů zapracováno. Zbývající rizika jsou
běžná implementační, která odhalí `writing-plans` fáze a TDD.

## On Codex's points (kolo 10: 0 BLOCKING, 6 IMPORTANT, 2 NIT)

### Agreed + fixed
- **new_terms bez garantované otázky / term_id** — opraveno: krok 6 explicitně:
  po `add_candidate()` (přiřadí term_id) rovnou `upsert_open_question(...)`.
- **candidate vs seeded term_id kolize** (reálná díra) — opraveno: párování
  kandidáta i reseedu podle povrchu (`canonical_en`/`aliases`) → shoda = úprava
  in-place se zachováním `term_id`. Candidate a pozdější seeded/approved pro
  stejnou entitu sdílí `term_id`, FK drží.
- **`term_mentions = ÚPLNÝ` nepravdivé** — opraveno: přeformulováno na
  best-effort; drift na úplnost nespoléhá ("signál, ne důkaz").
- **`relationship` scope_key bez jednotné normalizace** — opraveno: jedna
  definice `relationship_key(a,b) = "|".join(sorted(normalize(resolve_surface(a)),
  normalize(resolve_surface(b))))`, používá se v scout merge, answer i questions.
- **cost guard bez stavu po potvrzení** — opraveno: `runs.spend_ceiling`
  (per-run navýšený strop); efektivní strop = max(config, ceiling); po
  potvrzení se neptá znovu.
- **upsert nad 2 partial indexy nedospecifikovaný** — opraveno: helper
  `upsert_open_question(q)` větví globální vs kapitolové, explicitní
  SELECT+UPDATE/INSERT v transakci B, ne obecný `ON CONFLICT`.
- **NIT: CLI bez `scan --chunked`** — doplněno.
- **NIT: model** — Codex ověřil OK.

### Disagreed
- Nic.

## Claude VERDICT
CONSENSUS — po zapracování kola 10 nevidím žádný BLOCKING ani IMPORTANT.
Architektura je stabilní 6 kol, data model uzavřený, každý bod za 10 kol
vyřešen. Spec je připravený na implementační plán.

## Summary for log
Kolo 10 (finální): Codex 0 BLOCKING, 6 IMPORTANT (candidate/seeded term_id
kolize, new_terms otázka, term_mentions best-effort, relationship_key,
cost guard stav, upsert helper) + 2 NIT. Claude 0 vlastních, VERDICT CONSENSUS.
Vše zapracováno. Codex drží CHANGES_NEEDED (je instruován nebýt shovívavý),
ale jeho kolo-10 nálezy byly schema nity, všechny opravené; architektura
nezměněna od kola 4, žádný BLOCKING od kola 8.