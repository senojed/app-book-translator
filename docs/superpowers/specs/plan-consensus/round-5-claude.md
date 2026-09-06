# Round 5 — Claude critique

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Spec je po 4 kolech stabilní. Codexovy 4
IMPORTANT jsou přesné a týkají se jednoho tématu (data model concordance /
finding), ne architektury.

Jedna vlastní poznámka: rozhodnutí z kola 3 "translator NEhlásí term_mentions"
bylo příliš striktní a způsobilo cirkularitu, kterou Codex teď trefil. Správné
řešení je střední cesta (ověřený `rendered_terms`), ne úplné odmítnutí LLM
signálu.

## On Codex's points

### Agreed + fixed
- **IMPORTANT: drift detekce cirkulární** (`variants` z `term_mentions`,
  `build_mentions` zapisuje jen známé tvary → novotvar tam nikdy není) —
  opraveno: translator hlásí `rendered_terms` (uzavřená množina termínů, které
  dostal; pipeline každý ověří substringem proti CZ textu, neověřené zahodí).
  `build_mentions` je použije → `term_mentions` má i tvary mimo glosář →
  novotvar se přidá do `variants` a drift ho vidí. Není to "věř LLM
  prohledávání", je to "ukaž na co jsi sáhl, kód ověří".
- **IMPORTANT: `Finding` tvar nedefinovaný** ("sjednocené do jednoho tvaru") —
  opraveno: nová sekce Finding se schematem
  `{source, type, severity, term_en?, expected?, actual?, cz_excerpt?, issue, suggestion?}`.
  Kritik i concordance ho produkují, revizor konzumuje.
- **IMPORTANT: concordance candidate `inconsistency` → "otázka", ale step 7
  bere jen translatorovy otázky** — opraveno: step 7 explicitně převádí
  concordance candidate inconsistency na `question` (kind=term, scope_key=term_en,
  guess_answer=nalezený tvar, severity=guess).
- **IMPORTANT: requeue přes `term_mentions` míjí omission kapitoly** — opraveno:
  `term_mentions.cz_form` je nullable; omission = řádek s `cz_form = NULL`;
  `affected_chapters` NULL řádky zahrnuje.
- **NIT: `estimated_cost_usd` vs actual** — opraveno: přejmenováno na `cost_usd`
  (skutečná cena z reálných tokenů, zápis po volání); pre-flight odhad guardu
  se nepersistuje.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 0 vlastních nálezů, ale Codexovy 4 IMPORTANT byly reálné díry
v data modelu. Po jejich opravě je concordance/finding vrstva uzavřená. Čekám
1 potvrzovací kolo.

## Summary for log
Kolo 5: Codex 0 BLOCKING, 4 IMPORTANT + 1 NIT, vše kolem data modelu
concordance. Claude 0 vlastních. Opraveno: `rendered_terms` (ověřená uzavřená
množina) řeší cirkularitu drift detekce; nová sekce `Finding` (společný tvar
nálezu kritik+concordance); step 7 převádí concordance candidate issues na
questions; `term_mentions.cz_form` nullable (omission řádky) + zahrnuty do
requeue; `cost_usd` (actual) místo `estimated_cost_usd`. Sporné: nic. Codex
poprvé bez BLOCKING - blízko konsenzu.