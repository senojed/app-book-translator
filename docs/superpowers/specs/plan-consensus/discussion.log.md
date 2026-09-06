# Plan-consensus - discussion log

Plán: docs/superpowers/specs/2026-09-06-book-translator-design.md
Start: 2026-09-06T15:25:33Z
Max kol: 10

---

## Kolo 1 — 2026-09-06T15:36:40Z
- Codex: CHANGES_NEEDED (2 BLOCKING, 8 IMPORTANT) → plan-consensus/round-1-codex.md
- Claude: CHANGES_NEEDED (1 vlastní BLOCKING, 5 vlastních IMPORTANT) → plan-consensus/round-1-claude.md
- Opraveno: 10+ bodů. Revizní režim translatora dostává EN originál. Scout truncation = fatal + --chunked fallback. Glosář candidate/approved/seeded status. Nová tabulka term_mentions (zdroj dat pro drift). Nová tabulka llm_calls (usage po každém volání). Přepsaná klasifikace chyb: fatal běhu vs recoverable kapitola. Rozšířené questions schema (kind, scope_key, guess_answer) + přesná requeue pravidla. Nová sekce Export (flagged s markerem, chybějící kapitoly hlášené). Nová sekce Prostředí (UTF-8 stdout). Re-scan nikdy nepřepíše guide.json.
- Sporné: nic.

## Kolo 2 — 2026-09-06T15:41:52Z
- Codex: CHANGES_NEEDED (4 BLOCKING, 8 IMPORTANT) → round-2-codex.md
- Claude: CHANGES_NEEDED (2 vlastní IMPORTANT) → round-2-claude.md
- Většina bodů = díry po velkém přepisu v kole 1 (nedotažené interfacy).
- Opraveno: LLMClient.count_tokens() jako metoda; logging přes LoggedLLMClient wrapper (hranice modulů zachovány, AnthropicClient čistý); translator question metadata = {kind, scope_key, guess_answer, text, severity}; concordance leak jen pro cz!=term_en (keep termíny nehlásí); error=run retry vs needs_human/flagged=skip (rozpor vyřešen); blocking otázka po answer VŽDY pending; must_decide strukturované {kind,scope_key,question,default}; POST /api/guide reseeduje jen seeded (approved/candidate zůstávají); term_mentions DELETE při retranslation; llm_calls +provider/cost/truncated/status; critic truncation = retry+flagged ne tichý pass; kind +relationship.
- Sporné: nic.

## Kolo 3 — 2026-09-06T15:46:55Z
- Codex: CHANGES_NEEDED (1 BLOCKING, 6 IMPORTANT, 2 NIT) → round-3-codex.md
- Claude: CHANGES_NEEDED (1 vlastní IMPORTANT) → round-3-claude.md
- Opraveno: cost guard + logging sloučeny do PipelineLLMClient.complete() (má system/user/max_tokens z Protocolu); translator už nehlásí used_terms - concordance.build_mentions staví term_mentions deterministicky z EN+CZ; přidán stav 'processing' + file lock (.book-translator.lock, PID) - answer/run/scan/init se navzájem vylučují, read-only ne; check_chapter bere EN text + nález 'omission'; cost formula + max_tokens*out_rate; rollback wording; chunked scout merge detailně (casefold klíč, alias union, kolize->must_decide, konfliktní vztahy->null+must_decide). NIT: Stav->v revizi, answer <question_id>.
- Sporné: nic. Rozsah změn klesá (kolo 1: 10+, kolo 2: 12, kolo 3: 8).

## Kolo 4 — 2026-09-06T15:51:20Z
- Codex: CHANGES_NEEDED (1 BLOCKING, 5 IMPORTANT, 2 NIT) → round-4-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-4-claude.md
- Opraveno: answer řeší 1 otázku, needs_human→pending jen když nezbývá blocking otázka; glosář = JEDINÝ zdroj termín→CZ v promptu (guide neemit termíny, approved má přednost); glossary +variants[] (z mentions/kandidátů/odpovědí) - rozlišuje inconsistency vs omission; kanárek/processing transakčně dotažen (processing commit před 1. voláním, fatal→zůstane processing, další run vrátí na pending); used_terms úplně odstraněno; PipelineLLMClient jednotný název, per-volání; nits (model/ceny config+validace, data/ output/ do dir stromu).
- Sporné: nic. Konverguje (kolo 4 = 0 vlastních Claude nálezů).

## Kolo 5 — 2026-09-06T15:55:43Z
- Codex: CHANGES_NEEDED (0 BLOCKING, 4 IMPORTANT, 1 NIT) → round-5-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-5-claude.md
- Vše kolem data modelu concordance/finding. Opraveno: translator hlásí rendered_terms (uzavřená množina termínů co dostal, pipeline ověří substringem, neověřené zahodí) - řeší cirkularitu drift detekce z kola 3; nová sekce Finding {source,type,severity,term_en?,expected?,actual?,cz_excerpt?,issue,suggestion?}; step 7 převádí concordance candidate inconsistency na questions; term_mentions.cz_form nullable (omission=NULL řádek), zahrnuto do affected_chapters; cost_usd (actual) místo estimated_cost_usd.
- Sporné: nic. Codex poprvé bez BLOCKING.

## Kolo 6 — 2026-09-06T16:01:43Z
- Codex: CHANGES_NEEDED (2 BLOCKING, 5 IMPORTANT, 3 NIT) → round-6-codex.md
- Claude: CHANGES_NEEDED (2 vlastní IMPORTANT) → round-6-claude.md
- BLOCKING: variants konfliktní ("pozorované" i "akceptované" - regrese kola 5) → zrušeno, glosář má cz + accepted_alt (jen člověk), pozorování jen v term_mentions. Glosář JSON mimo SQLite transakci → glosář přesunut do SQLite tabulky (jedna transakce s commitem kapitoly), guide.json zůstává soubor.
- IMPORTANT: review drží run lock; kind=relationship→guide.relationships, other→rules; drift → questions (actionable, ne jen report); metadata agregace po scénách (union) + revize nahradí; questions UNIQUE(chapter_idx,kind,scope_key,severity)+upsert, rerun maže nezodpovězené.
- NIT: check_chapter signatura sjednocena; concordance zkoumá jen termíny ve scéně ne celý glosář.
- Sporné: nic.

## Kolo 7 — 2026-09-06T16:06:51Z
- Codex: CHANGES_NEEDED (1 BLOCKING, 5 IMPORTANT, 1 NIT) → round-7-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-7-claude.md
- Vše schema precision, ne architektura. Opraveno: glossary term_id PK + canonical_en + aliases JSON (proteklo do term_mentions FK, DriftFinding, questions.scope_key, Mention); rendered_terms = seznam výskytů {term_id,cz_as_used,scene_idx} bez last-wins; questions.scope_key="" sentinel místo NULL (SQL UNIQUE s NULL nefunguje); questions.chapter_idx nullable + partial UNIQUE pro globální drift otázky; PipelineLLMClient loguje ve finally (status ok/truncated/error, error_class, tokeny nullable) - selhaná volání nezmizí z auditu; transakce A (krok 0) / LLM mimo / transakce B (kroky 6-8) explicitně; pilot checklist: ověřit model+ceny proti docs.
- Sporné: nic.

## Kolo 8 — 2026-09-06T16:11:57Z
- Codex: CHANGES_NEEDED (1 BLOCKING, 5 IMPORTANT, 2 NIT) → round-8-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-8-claude.md
- Vše precizace term_id/schema, architektura beze změny 4 kola. Opraveno: prompt glosáře nese term_id + translator hlásí rendered_terms přes term_id (dotažení kola 7); term_mentions = 1 řádek/výskyt + scene_idx + source(rendered|detected|omission); scope_key style/other = hash(text) ne ""; partial UNIQUE jen WHERE answer IS NULL (zodpovězená otázka neblokuje novou); llm_calls +error_class +status ok/truncated/error; fatal/kanárek wording sjednocen; glossary API na term_id + resolve_surface(); review server exit-code jako signál pro reseed.
- Sporné: nic. Doporučeno kolo 9 jako finální sweep, pak uzavřít.

## Kolo 9 — 2026-09-06T16:16:07Z
- Codex: CHANGES_NEEDED (1 BLOCKING, 4 IMPORTANT, 2 NIT) → round-9-codex.md
- Claude: CHANGES_NEEDED (0 vlastních) → round-9-claude.md
- Opraveno: Finding +action(revise|question|note)+term_id s routing tabulkou (kritik/concordance → co s tím); scene_idx doplňuje pipeline ne translator (revizní výstup → NULL); deterministický term_id (slug) + reseed = UPDATE podle term_id ne delete+insert (FK integrita term_mentions/questions); run --retry-flagged doplněn do CLI seznamu/automatu/buildu/testů (reset revision_rounds=0); přiznané v1 omezení: new_terms dedup podle povrchu, split entity je ruční answer; partial unique zapsáno jako CREATE UNIQUE INDEX ... WHERE answer IS NULL.
- Sporné: nic. Architektura beze změny 5 kol po sobě.

## Kolo 10 — 2026-09-06T16:21:38Z (finální)
- Codex: CHANGES_NEEDED (0 BLOCKING, 6 IMPORTANT, 2 NIT) → round-10-codex.md
- Claude: CONSENSUS (0 vlastních) → round-10-claude.md
- Opraveno: candidate/seeded term_id kolize (párování podle povrchu, sdílený term_id); new_terms → garantovaná upsert_open_question; term_mentions přeformulováno na best-effort; relationship_key jedna definice všude; runs.spend_ceiling (cost guard stav po potvrzení); upsert_open_question helper (větví globální/kapitolové); scan --chunked do CLI.
- VÝSLEDEK: MAX_ROUNDS (10/10). Konvergence prakticky dosažena - Claude CONSENSUS, Codex CHANGES (instruován nebýt shovívavý), architektura nezměněna 6 kol, 0 BLOCKING od kola 8. Viz final-verdict.md.
