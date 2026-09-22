# Round 7 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (model-authorization gap - `auth status` neověří
  oprávnění na `config.MODEL_CRITIC`):** Souhlasím, že mezera je
  reálná. Nesouhlasím s navrhovanou opravou (skutečný zkušební
  `claude -p` v preflightu) - stálo by reálné předplatné-usage při
  KAŽDÉM `run`/`polish` spuštění kvůli ochraně před úzkým, vzácným
  selháním, co navíc NENÍ tiché (`ClaudeCliFatalError` +
  `_checkpoint_flagged()` z předchozího plánu bezpečně uchová poslední
  platný `cz`). Proporcionalitní úsudek stejný jako u prvního
  plan-consensus (kolo 20) - náklad opravy neúměrný riziku.

  **Oprava:** zdokumentováno jako VĚDOMĚ PŘIJATÝ LIMIT -
  `_claude_cli_preflight()`'s docstring rozšířen o "Kolo 7" odstavec,
  stejný bod přidán do Global Constraints.

- **IMPORTANT (`-p` substring bug - `"-p" in help_result.stdout`
  projde i na `--print`):** Souhlasím, ověřeno character-by-character
  (`"-p"` je substring `"--print"`, pozice 1-2). Reálný, ne
  hypotetický bug.

  **Oprava:** `_REQUIRED_FLAGS` rozděleno na `_REQUIRED_LONG_FLAGS`
  (5 dlouhých/unikátních flagů, substring OK) + samostatná regex
  kontrola pro `-p` (`(?<![A-Za-z-])-p(?![A-Za-z-])`, hraniční
  kontrola místo substring). Přidán regresní test
  (`test_claude_cli_preflight_print_alias_does_not_satisfy_dash_p`) -
  `--help` výstup obsahuje `--print` MÍSTO `-p`, preflight musí
  `-p` nahlásit jako chybějící.

- **IMPORTANT (spec vs. plán - `user` jako poziční argv vs. stdin):**
  Souhlasím, potvrzeno přímým čtením
  `docs/superpowers/specs/2026-09-21-claude-cli-critic-design.md`.

  **Oprava:** spec aktualizován (dva bloky - "Ověřeno spikem" a
  "Subprocess volání") - `user` teď explicitně STDINEM, `system` přes
  `--system-prompt`, stejný tvar jako plán.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 7: tři IMPORTANT, všechny potvrzené jako reálné. Dva opraveny
(regex fix pro `-p`/`--print` kolize + regresní test; spec
sesynchronizován s plánem na stdin-based `user`). Třetí (model-
autorizace) zdokumentován jako vědomě přijatý limit s odůvodněním
(proporcionalita - stejný precedent jako první plán-konsensus kolo 20),
ne oprava kódu. Hustota nálezů zůstává nenulová i v sedmém kole -
substring bug byl skutečně přehlédnutý (ne re-hash staršího bodu).
