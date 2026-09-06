# Round 3 — Claude critique (plán)

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Codexové 3 BLOCKING jsou reálné důsledky
kola 2 (interactive param, blocking otázka scope_key, must_decide routing).

## On Codex's points

### Agreed + fixed
- **BLOCKING: `run` používá `interactive=False` (jako scan), ale spec chce aby
  se `run` ptal** — opraveno: `run` `cf` má `interactive=True`; jen `scan` má
  `False`. Explicitní věta v Task 15.
- **BLOCKING: `apply_answer` volá `glossary.promote(scope_key)` i pro blocking
  otázky, jejichž `scope_key` není existující term_id** — opraveno:
  - blocking otázka: `scope_key` = normalizovaný povrch (jméno/výraz), ne term_id
    (translator ho nezná). Zapsáno v Task 12 konvenci.
  - `apply_answer` term/name: `glossary.resolve_term_or_surface(scope_key)` →
    nalezeno: `promote`; nenalezeno: `glossary.add_approved(canonical_en=scope_key,
    cz=answer)`. Nové helpery `add_approved`, `resolve_term_or_surface` v Task 6.
  - testy blocking otázek přepsány na reálné povrchy + assertion approved řádku.
- **BLOCKING: `must_decide` odpovědi se nikam nezapisují** — opraveno:
  `server.apply_must_decide(payload)` PŘED save routuje odpověď do
  `terms`/`characters`/`relationships`/`rules` podle `kind`, pak `must_decide`
  z payloadu smaže. Test `test_post_routes_must_decide_answer_into_terms`.
- **IMPORTANT: concordance běží před přidáním new_terms → first-pass leak check
  nové termíny nevidí** — opraveno: explicitní v1 chování - nové termíny
  objevené v této kapitole se v její revizní smyčce concordance-checkem neřeší,
  kontrolují se až od další kapitoly.
- **IMPORTANT: `review` reseed + lock jen manual smoke** — opraveno:
  `test_review_reseeds_only_on_success` (monkeypatch `run_review_server` → 0/1,
  ověří reseed jen na 0).
- **IMPORTANT: `INSERT OR IGNORE` tiše zahodí kandidáta, ale mention/question
  ho referuje** — opraveno: plain `INSERT`; na `IntegrityError` (slug kolize)
  najdi existující `term_id` a přemapuj mentions/questions toho kandidáta na něj,
  nikdy nezůstane visící FK.
- **NIT: `nt["cz"]` vs `candidate["cz"]` nekonzistence** — opraveno:
  sjednoceno na `cand[...]` v celém kroku (b)-(d).
- **NIT: model** — Codex ověřil, bez akce.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 3 BLOCKING (Codex) reálné (interactive scope, blocking otázka
scope_key, must_decide routing). Claude 0 vlastních. Chce potvrzovací kolo.

## Summary for log
Kolo 3: Codex 3 BLOCKING (run interactive=False místo True; apply_answer
promote na neexistující scope_key blocking otázek; must_decide odpovědi se
neroutují) + 3 IMPORTANT + 2 NIT. Claude 0 vlastních. Opraveno: run=interactive
scan=hard-stop; blocking otázka scope_key = povrch, apply_answer má
resolve_term_or_surface + add_approved; server.apply_must_decide routuje
odpovědi do polí; nové termíny v kapitole exempt z concordance té kapitoly;
review reseed test; INSERT + IntegrityError remap místo INSERT OR IGNORE.
Sporné: nic.