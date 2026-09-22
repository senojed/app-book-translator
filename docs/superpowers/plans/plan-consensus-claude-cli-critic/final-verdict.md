# Final verdict

**CONSENSUS** (dosaženo v kole 11 z max. 40)

Codex i Claude nezávisle ve stejném kole (11) nenašly žádné BLOCKING
ani IMPORTANT nedostatky v `docs/superpowers/plans/2026-09-21-claude-cli-critic.md`.

## Historie oprav (kola 1-10)

Deset kol postupně opravilo 15+ konkrétních nálezů - shrnutí:

- **Kolo 1 (BLOCKING):** `system`/`user` nesmí jít jedním stdin blobem -
  `system` přes `--system-prompt`, `user` STDINEM.
- **Kolo 2:** payload validace `usage` polí (typ/rozsah), `truncated`
  ze skutečného `stop_reason`.
- **Kolo 3:** `claude_cmd` musí být provlečen z preflightu do
  `_client_factory`, ne znovu-resolvnut líně. Scope-mezera (`stylist_check`
  zůstává na `AnthropicClient`) zdokumentována.
- **Kolo 4:** `_claude_cli_preflight()` přidán, `--help` flag-kompatibilní
  kontrola.
- **Kolo 5:** `returncode` kontroly u obou `subprocess.run` volání v
  preflightu. Testové fixtures pro 4 existující fake factory (regrese
  z předchozího plánu).
- **Kolo 6:** `-p`/`--model` doplněny do required-flags, `encoding="utf-8"`
  + `UnicodeError` handling konzistentně v preflightu.
- **Kolo 7:** substring bug (`-p` vs `--print`), model-autorizace
  zdokumentována jako vědomě přijatý limit, spec sync (`user` stdin).
- **Kolo 8:** spec sync (timeout mechanismus `Popen`+kill-tree, ne
  `subprocess.run(timeout=)`; `TimeoutExpired` NENÍ fatální).
  `ClaudeCliClient.__init__` skeleton ve specu doplněn o `claude_cmd`.
- **Kolo 9:** chybějící `--no-session-persistence` flag (perzistence
  historie relací). Substring bug zobecněn na VŠECHNY flagy
  (`--system-prompt-snapshot` kolize).
- **Kolo 10:** `usage` povinné na úspěšné cestě, `or 1` fallback
  odstraněn (přepisoval validní nulu).

## Stav

Plán je připraven k implementaci (`superpowers:executing-plans` nebo
`superpowers:subagent-driven-development`).
