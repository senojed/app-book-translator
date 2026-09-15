# Round 9 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `outcome=="unchanged"` marker se nikam nepersistuje,
  `_already_styled` po dávce zůstane `False`:** ověřeno čtením
  skutečného main.py (`_polish_one_chapter` main.py:589-591 vrací
  `{"idx", "outcome": "unchanged"}`, `_already_styled` main.py:100-106
  hledá jen `type=="polish"`) - potvrzeno jako reálná mezera, bug
  existuje i v DNEŠNÍM main.py (ne jen v plánu), ale plán ho dědí a
  právě dávkové zpracování 50 kapitol je scénář, kde se cena projeví
  nejvíc (opakovaný `polish` běh přes celou knihu by platil Codexu za
  stejnou "žádná úprava" odpověď pořád dokola). Přidán `_unchanged_
  marker(model)` (main.py, vedle `_stylist_marker`/`_kept_original_
  marker`/`_revert_marker`), `_already_styled` rozšířeno na `type in
  ("polish", "unchanged")`, `_MARKER_TYPES` (Task 2, `src/findings.py`)
  rozšířeno o `("stylist", "unchanged")` ať `is_marker`/`count_unresolved`
  marker správně skryjí z UI nálezů. Task 5 Step 8 batch smyčka dostala
  novou `elif` větev - lehký zápis (CAS na text/status, `refresh_lock`,
  `_backup_db_once`, přímý `UPDATE chapters SET notes=...`) BEZ průchodu
  `_commit_polish_result` (žádná VĚCNÁ změna textu = žádná nová historie
  položka, jinak by `cz_before==cz_after` záznam byl zavádějící). Nový
  end-to-end test ověřuje: 1. běh - marker zapsán, 2. běh bez `--force`
  - kapitola přeskočena (Codex nezavolán podruhé), `--force` běh -
  kapitola i tak zpracována znovu.

## Claude VERDICT

CONSENSUS (žádný vlastní nález, jediný Codexův bod opraven)

## Summary for log

Nová třída nálezu (ne pokračování await-race série z kol 6-8) - cost/
idempotence mezera v batch smyčce, přímo relevantní k uživatelovu
původnímu požadavku "batch polish 50 kapitol" (spec 2026-09-14). Bug je
PŘEDEXISTUJÍCÍ v main.py (ne vznikl týmhle plánem), ale plán ho zdědil
beze změny a dávkový provoz je přesně scénář, kde se cena znásobí.
Claude verdict CONSENSUS - čeká se na kolo 10, jestli Codex potvrdí totéž
(2. kolo v řadě s Claude CONSENSUS, viz kolo 8).
