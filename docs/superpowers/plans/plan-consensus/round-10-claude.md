# Round 10 — Claude critique (plán)

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `check_chapter` konzumuje neověřené `rendered_terms`** (ověření až
  v kroku 6a, po revizní smyčce) — opraveno: `rendered_terms` se filtruje přes
  `concordance.contains_form(cz, cz_as_used)` IHNED v kroku 2 (po překladu scén)
  a znovu po každé revizi, PŘED každým `check_chapter`. Test
  `test_hallucinated_rendered_term_does_not_trigger_revision`.
- **IMPORTANT: slug kolize remap nebezpečný** (mohl by připojit mention na cizí
  entitu) — opraveno: remap JEN když `canonical_en`/alias existujícího řádku
  skutečně odpovídá povrchu kandidáta; jinak deterministický suffix
  `cand_slug_2`, `_3`, retry INSERT.
- **IMPORTANT: re-`init` na jinou/kratší knihu nechá stale kapitoly** — opraveno:
  `init` odmítne neprázdnou DB bez `--reset`; `init --reset` → `state.reset_book`
  (TRUNCATE chapters/questions/term_mentions/drift_reports/glossary/runs/llm_calls).
  Test `test_reinit_refuses_without_reset_and_reset_replaces`.
- **IMPORTANT: prázdná `answer_text` → `parts[0]` IndexError** — opraveno:
  `apply_answer` validuje `answer_text.strip()` neprázdné + `parts` neprázdné →
  `ValueError`; `main` `answer` chytá → print + exit 1. Test
  `test_answer_empty_text_is_controlled_error`.

### Disagreed
- Nic.

## Claude VERDICT
CONSENSUS — po zapracování kola 10 nevidím žádný BLOCKING ani IMPORTANT. Plán
je 122 test funkcí, 17 tasků, každý task samostatně testovatelný. Interfacy
konzistentní, transakce definované, chyby klasifikované. Připraveno k provedení.

## Summary for log
Kolo 10 (finální): Codex 1 BLOCKING (rendered_terms konzumovány neověřené před
check_chapter) + 3 IMPORTANT (slug kolize remap; re-init stale kapitoly; prázdná
answer_text). Claude 0 vlastních, VERDICT CONSENSUS. Vše zapracováno:
rendered_terms filtrované contains_form ihned + po revizi; slug kolize jen
surface-match nebo suffix; init --reset + odmítnutí neprázdné DB; apply_answer
validace prázdné odpovědi. Codex drží CHANGES_NEEDED (instruován nebýt
shovívavý), ale žádný BLOCKING/IMPORTANT po opravě nezůstal nevyřešený.