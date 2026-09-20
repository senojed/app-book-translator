# Round 26 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`_checkpoint_flagged()`'s `gl_rows=[]` fallback maže
  existující mentions):** Souhlasím - MOJE VLASTNÍ kolo-25 oprava
  (fetchovat `glossary_rows` znovu uvnitř, bezpečně zabalené) zavedla
  přesně tu samou třídu chyby, co kolo 18 už jednou opravilo jinde:
  `gl_rows=[]` → `concordance.build_mentions()` vrátí prázdný seznam →
  `commit_chapter_result()` (VŽDY smaže existující `term_mentions` PŘED
  vložením) → nenávratná ztráta. Subtilní regrese vlastního fixu -
  přesně proto tenhle plan-consensus proces existuje.

  **Oprava:** Přidán `existing_mentions = state.chapter_mentions(
  db_path, idx)` snapshot PŘED `begin_chapter()` (stejný vzor jako
  `existing_questions`, kolo 20) - `state.chapter_mentions()` je
  existující veřejná funkce (`src/state.py:569-579`), žádná nová DB
  logika. `_checkpoint_flagged()`'s `except Exception:` větev teď
  používá `existing_mentions` jako fallback MÍSTO `[]` - horší než
  čerstvý rebuild (nemusí odrážet TENHLE run), ale nekonečně lepší než
  totální ztráta. Přidán regresní test `test_checkpoint_glossary_
  fetch_failure_preserves_existing_mentions`.

- **IMPORTANT (checkpoint nepřeklápí `findings`-otázky, jen `questions_
  now` z translatoru):** Souhlasím - ověřil jsem přesně proti reálné
  transakci B (`src/pipeline.py:157-169`) - `for f in findings: if
  f.get("action") != "question": continue; db_questions.append(...)`
  je DRUHÝ, nezávislý zdroj otázek (z `concordance.check_chapter()`,
  ne z translatoru), co `_checkpoint_flagged()` ignorovalo úplně.
  Zachráněný `cz` by tak mohl mít nález v `notes` bez odpovídající
  otázky v `questions` tabulce.

  **Oprava:** `fresh_db_questions` teď navíc obsahuje transformaci
  `findings_now` položek s `action=="question"` (stejná logika jako
  transakce B, včetně `_scope_key_for()` fallbacku na hash textu pro
  prázdný `term_id` - partial unique index by jinak s prázdným klíčem
  nefungoval). Přidán regresní test `test_checkpoint_preserves_
  question_from_concordance_finding`.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 26: dva IMPORTANT body, OBA nálezy v kódu, co jsem napsal MINULÉ
kolo (25) - `gl_rows=[]` fallback by nenávratně smazal existující
mentions (stejná třída chyby jako kolo 18, teď uvnitř checkpointu
samotného), a checkpoint ignoroval `findings`-odvozené otázky (druhý
zdroj otázek v normální transakci B). Opraveno snapshotem `existing_
mentions` (fallback místo `[]`) a rozšířením `fresh_db_questions` o
`findings_now`'s question-action položky. Sedmé kolo v řadě ve
checkpoint oblasti - tentokrát šlo o VLASTNÍ regresi z předchozího kola,
ne o novou nekrytou fázi funkce.
