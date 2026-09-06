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
