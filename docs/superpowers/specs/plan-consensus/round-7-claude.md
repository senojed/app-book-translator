# Round 7 — Claude critique

## Claude's own findings

### NITS
- Změna `term_en PK` → `term_id` musela projet i `Mention`, `DriftFinding`,
  `questions.scope_key`, translator→pipeline mapping. Prošel jsem všechny výskyty
  a sjednotil (`build_mentions`, `check_drift`, pseudokód kroky 7 + drift,
  requeue pravidla). Translator dál pracuje s `term_en` (povrch), pipeline mapuje
  na `term_id` přes `canonical_en`/`aliases`.

Žádné vlastní BLOCKING/IMPORTANT - Codex trefil zbývající schema-precision díry
přesně.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `glossary` bez aliasů / entity ID, `term_en PK` nejde** —
  opraveno: `glossary(term_id PK, canonical_en, aliases JSON, cz, accepted_alt,
  ...)`. `term_mentions`/`questions` odkazují `term_id`. Concordance matchuje
  `canonical_en` + `aliases`. Řeší i "stejný povrch, různé entity".
- **IMPORTANT: `rendered_terms` last-wins ztrácí tvary** — opraveno: seznam
  výskytů `{term_id, cz_as_used, scene_idx}`, bez dedup. Víc tvarů v kapitole
  je signál pro inconsistency/drift.
- **IMPORTANT: `UNIQUE(...scope_key...)` s NULL nededuplikuje** — opraveno:
  `scope_key = ""` sentinel pro style/other, ne NULL.
- **IMPORTANT: drift otázka bez `chapter_idx`, ale UNIQUE je po kapitole** —
  opraveno: `questions.chapter_idx` nullable; drift otázky mají NULL; partial
  `UNIQUE(kind, scope_key, severity) WHERE chapter_idx IS NULL`.
- **IMPORTANT: "log po každém volání" neplatí pro výjimky** — opraveno:
  `PipelineLLMClient` loguje ve `finally`; `status ∈ {ok, truncated, error}`,
  `error_class`, tokeny nullable. Selhaná volání nezmizí z auditu/cost.
- **IMPORTANT: transakční hranice rozporné** — opraveno: explicitně transakce A
  (krok 0: processing + smazání nezodp. otázek), LLM MIMO transakci, transakce B
  (kroky 6-8). Pád mezi/během → rollback, kapitola zůstane `processing`,
  samoopravné.
- **NIT: model validace jako checklist** — opraveno: pilot checklist má první
  položku "ověřit model ID + ceny + limity proti docs, zapsat do config.py".

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 0 vlastních BLOCKING/IMPORTANT. Codexův 1 BLOCKING (glossary
schema) + 5 IMPORTANT byly poslední schema-precision díry. Po nich by mělo být
čisto. Jedno potvrzovací kolo.

## Summary for log
Kolo 7: Codex 1 BLOCKING (glossary term_en PK vs aliasy/entity) + 5 IMPORTANT +
1 NIT, vše schema precision. Claude 0 vlastních. Opraveno: glossary přešel na
`term_id PK` + `canonical_en` + `aliases` (proteklo do term_mentions,
DriftFinding, questions.scope_key, Mention); `rendered_terms` = seznam výskytů
bez last-wins; scope_key="" místo NULL; questions.chapter_idx nullable +
partial unique pro drift; llm_calls log ve finally (i selhaná volání);
transakce A/B explicitně. Sporné: nic. Konvergence: rozsah čistě schema, ne
architektura.