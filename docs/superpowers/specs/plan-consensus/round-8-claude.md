# Round 8 — Claude critique

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Všech 8 Codexových bodů je pokračování
`term_id` přechodu z kola 7 + drobné schema mezery. Architektura ani tok se
už 3 kola nemění - jen precizace DB schematu a rozhraní.

## On Codex's points

### Agreed + fixed
- **BLOCKING: translator hlásí `rendered_terms` přes `term_en`** (nedotažení
  z kola 7) — opraveno: `glossary.as_prompt_block()` uvádí `term_id`; translator
  vrací `rendered_terms: [{term_id, cz_as_used}]` pro známé; `term_en` jen
  v `new_terms` pro neznámé povrchy.
- **IMPORTANT: `build_mentions` "1 Mention na termín" vs "1 na výskyt"** —
  opraveno: `term_mentions` = 1 řádek na pozorovaný (term_id, cz_form) výskyt,
  + `scene_idx` + `source ∈ {rendered, detected, omission}`. Víc forem
  v kapitole = víc řádků = viditelná intra-chapter inconsistency.
- **IMPORTANT: UNIQUE kolabuje víc `style`/`other` otázek v kapitole
  (scope_key="")** — opraveno: `scope_key` pro style/other = `hash(text)`.
- **IMPORTANT: globální drift otázka - po zodpovězení nejde založit novou** —
  opraveno: partial UNIQUE jen `WHERE answer IS NULL` (u obou indexů). Dedup jen
  mezi otevřenými otázkami; zodpovězená neblokuje.
- **IMPORTANT: `llm_calls` nemá `error_class`** — opraveno: přidáno
  `error_class NULL`, `status: ok|truncated|error`, tokeny/cost nullable.
- **IMPORTANT: fatal "žádná kapitola" vs kanárek po transakci A** — opraveno:
  wording tabulky Chyby sjednocen s kanárkem ("aktuální může zůstat
  `processing`, další run vrátí na pending").
- **NIT: `promote(term_en,...)` neodpovídá `term_id`** — opraveno: API glosáře
  přepsáno na `term_id`, přidán `resolve_surface(term_en) → term_id`.
- **NIT: CLI ↔ UI signál pro reseed** — opraveno: `POST /api/guide` úspěch →
  `{ok:true}` + server se ukončí exit 0; `review` čeká na konec serveru,
  exit 0 → reseed, jinak ne.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 0 vlastních nálezů. Codexův 1 BLOCKING byl nedotažení kola 7,
zbytek schema mezery. Doporučuji: kolo 9 jako finální sweep konzistence, pak
uzavřít (architektura stabilní od kola 4, rozsah čistě precizace).

## Summary for log
Kolo 8: Codex 1 BLOCKING (translator rendered_terms přes term_en - nedotažení
kola 7) + 5 IMPORTANT + 2 NIT, vše precizace term_id/schema. Claude 0 vlastních.
Opraveno: prompt glosáře nese term_id, translator hlásí rendered_terms přes
term_id; term_mentions = 1 řádek/výskyt + scene_idx + source; scope_key style/
other = hash(text); partial UNIQUE jen WHERE answer IS NULL; llm_calls
+error_class; fatal/kanárek wording; glossary API na term_id; review server
exit-code signál. Sporné: nic. Architektura beze změny 4 kola po sobě.