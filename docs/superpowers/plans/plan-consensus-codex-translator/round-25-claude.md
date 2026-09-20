# Round 25 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (checkpoint pokrývá jen scénovou smyčku + kritik/revize,
  ne zbytek `process_chapter()`):** Souhlasím a ověřil jsem přesně proti
  reálnému `src/pipeline.py` - mezi scénovou smyčkou (kolo 23/24) a
  pre-loop kritikem (kolo 22/24) zůstávalo NECHRÁNĚNÉ `cz = ...`/
  `rendered = _verified_rendered(...)`/`glossary_rows = glossary.
  all_terms(...)`/`findings = concordance.check_chapter(...)` - selhání
  PŘÍMO tady by zahodilo hotový scénový překlad BEZ checkpointu. A
  "příprava transakce B" (nové termíny do glosáře, `concordance.
  build_mentions()`, finální `commit_chapter_result()`) PO revizní
  smyčce nemělo ŽÁDNOU ochranu vůbec - poslední místo v celé funkci.

  Tohle je ŠESTÉ kolo v řadě (9,13,18,20,21,22,23,24,25), co najde další
  mezeru ve stejné oblasti - rozhodl jsem se PROTO nekonsolidovat do
  jednoho velkého obalu (riziko: přepisovat už 5x ověřený kód najednou,
  bez možnosti testy skutečně spustit v plan-authoring fázi), ale
  přidat DVĚ další cílené, malé záplaty využívající STEJNÝ sdílený
  `_checkpoint_flagged()`, konzistentně s dosavadním vzorem.

  **Oprava 1 (kontrola fáze):** Rozšířil jsem `try` kolem `_run_critic()`
  (kolo 22) DOZADU, aby zahrnul i `_verified_rendered()`/`glossary.
  all_terms()`/`concordance.check_chapter()`. `except` klauzule
  rozšířena z úzkého `(FatalRunError, KeyboardInterrupt)` na `(Exception,
  KeyboardInterrupt)` - tyhle tři volání NEJSOU LLM volání s vlastní
  `FatalRunError` klasifikací jako `_run_critic()`, jejich chyba je
  obyčejný `Exception` (mirror scénové smyčky, kolo 23/24, co má stejně
  širokou klauzuli). Vedlejší, ale nutná oprava: `_checkpoint_flagged()`
  dřív ČERPALO `glossary_rows` z vnějšího scope - kdyby `glossary.
  all_terms()` SAMO bylo tím, co selhalo, `glossary_rows` by nebyl vůbec
  bound a checkpoint by spadl na `NameError` MÍSTO uložení flagged
  stavu. Teď si `glossary_rows` fetchuje ZNOVU, bezpečně zabalené v
  `try/except Exception: gl_rows = []`. `findings = []` přidáno PŘED
  `try` (dřív první přiřazení bylo AŽ uvnitř), aby `_checkpoint_
  flagged()`'s `findings_now` parametr byl vždy bezpečně bound.

  **Oprava 2 (transakce B prep):** Obalil jsem celou fázi (od
  `new_candidates, extra_mentions = [], []` po `result = state.
  commit_chapter_result(...)`) v `try/except (Exception,
  KeyboardInterrupt)`, co zavolá `_checkpoint_flagged(cz, findings,
  questions, rounds, type(e).__name__)` a re-raisne. `return` zůstává
  MIMO try - dosáhne se ho jen po úspěšném commitu.

  Přidány tři regresní testy: `test_kontrola_phase_fatal_error_
  preserves_scene_translation` (mockuje `concordance.check_chapter`),
  `test_transakce_b_prep_fatal_error_preserves_final_translation`
  (mockuje `concordance.build_mentions` - JEN NA PRVNÍ volání, druhé
  volání - uvnitř checkpointu samotného - musí projít, jinak by
  checkpoint spadl taky).

- **IMPORTANT (chybí regresní test pro `KeyboardInterrupt` u pre-loop
  kritika):** Souhlasím - kolo 24 rozšířilo `except` klauzuli tam, ale
  zapomnělo přidat odpovídající test (na rozdíl od scénové smyčky a
  revizní smyčky, co testy dostaly). Přidán `test_pre_loop_critic_
  keyboard_interrupt_preserves_scene_translation`.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 25: dva IMPORTANT body. První - checkpoint nepokrýval CELOU
"kontrola" fázi (jen `_run_critic()`, ne `_verified_rendered()`/
`glossary.all_terms()`/`concordance.check_chapter()`) ani "přípravu
transakce B" (poslední místo v celé funkci) - opraveno rozšířením
existující try/except struktury + učiněním `_checkpoint_flagged()`
robustním vůči `glossary_rows` nebound scénáři. Druhý - chybějící
KeyboardInterrupt test pro pre-loop kritika z kola 24, doplněno. Šesté
kolo v řadě ve stejné oblasti - ale POKRYTÍ teď zahrnuje VŠECHNA místa
v `process_chapter()` po `begin_chapter()`, žádné další volání v
téhle funkci není mimo nějaký checkpoint.
