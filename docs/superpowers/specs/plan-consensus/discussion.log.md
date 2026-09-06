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
