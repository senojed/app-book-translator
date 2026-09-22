# Round 9 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (chybí `--no-session-persistence`):** Souhlasím, ověřeno
  PŘÍMO (`claude --help` skutečně obsahuje `--no-session-persistence -
  Disable session persistence`). Reálné riziko - kritikův prompt
  (kapitola EN+CZ) by se bez tohohle flagu persistoval do lokální
  historie relací, `--safe-mode` řeší jen CLAUDE.md/pluginy/hooky, ne
  perzistenci.

  **Oprava:** flag přidán do `_exec_claude()`'s argv (Task 2) i do
  `_claude_cli_preflight()`'s `_REQUIRED_FLAGS` (Task 3). Spec
  aktualizován stejně. Fixture stdouty (`_fake_help_result` a
  duplicitní fixture) rozšířeny, ať nově neselžou na "chybí
  --no-session-persistence" místo toho, co skutečně testují. Přidána
  assert v `test_exec_claude_calls_popen_with_system_prompt_flag_and_
  stdin_user`.

- **IMPORTANT (substring bug platí i pro DLOUHÉ flagy, ne jen `-p`):**
  Souhlasím, ověřeno PŘÍMO (`claude --help` OPRAVDU obsahuje
  `--system-prompt-snapshot` jako existující, reálný flag) - kolo-7
  fix (regex speciálně jen pro `-p`) byl neúplný, stejná třída bugu
  platí univerzálně pro libovolný flag, co má delšího "sourozence" v
  `--help` výstupu.

  **Oprava:** `_REQUIRED_LONG_FLAGS`/`_SHORT_FLAG_RE` speciální
  rozdělení ZRUŠENO, nahrazeno jednotnou `_flag_present()` helper
  funkcí (hraniční regex `(?<![A-Za-z0-9-])<flag>(?![A-Za-z0-9-])`
  aplikovaná NA VŠECHNY požadované flagy stejně, `-p` i dlouhé).
  Přidán regresní test
  (`test_claude_cli_preflight_system_prompt_snapshot_does_not_satisfy_
  system_prompt`) - `--help` výstup obsahuje `--system-prompt-snapshot`
  MÍSTO holého `--system-prompt`, preflight musí `--system-prompt`
  nahlásit jako chybějící.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 9: dva IMPORTANT, oba ověřeny PŘÍMO proti reálnému `claude --help`
výstupu (ne jen teoreticky) - `--no-session-persistence` skutečně
chybí a `--system-prompt-snapshot` skutečně existuje jako kolizní
dlouhý flag. Druhý bod ukazuje, že kolo-7 fix byl příliš úzký (jen
`-p`) - opraveno zobecněním na jednotnou hraniční kontrolu pro všechny
flagy. Doporučuji do dalšího kola důkladně zkontrolovat, jestli žádný
JINÝ flag v `_REQUIRED_FLAGS` nemá podobného "sourozence" v aktuálním
`--help` výstupu (ověřil jsem `--model`/`--tools`/`--output-format`/
`--safe-mode`/`--no-session-persistence` - žádná kolize nenalezena).
