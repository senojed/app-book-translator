# Plan-consensus - discussion log

Plán: docs/superpowers/specs/2026-09-06-book-translator-design.md
Start: 2026-09-06T15:25:33Z
Max kol: 10

---

## Kolo 1 — $(date -u +%Y-%m-%dT%H:%M:%SZ)
- Codex: CHANGES_NEEDED (2 BLOCKING, 8 IMPORTANT) → plan-consensus/round-1-codex.md
- Claude: CHANGES_NEEDED (1 vlastní BLOCKING, 5 vlastních IMPORTANT) → plan-consensus/round-1-claude.md
- Opraveno: 10+ bodů. Revizní režim translatora dostává EN originál. Scout truncation = fatal + --chunked fallback. Glosář candidate/approved/seeded status. Nová tabulka term_mentions (zdroj dat pro drift). Nová tabulka llm_calls (usage po každém volání). Přepsaná klasifikace chyb: fatal běhu vs recoverable kapitola. Rozšířené questions schema (kind, scope_key, guess_answer) + přesná requeue pravidla. Nová sekce Export (flagged s markerem, chybějící kapitoly hlášené). Nová sekce Prostředí (UTF-8 stdout). Re-scan nikdy nepřepíše guide.json.
- Sporné: nic.
