# Round 25 — Claude critique

## Claude's own findings
(žádné vlastní nad rámec Codexových)

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `--ignore-rules` zdůvodnění obrácené:** ověřeno. Kolo 23
  přidalo `--ignore-rules` do `_CODEX_STATIC_FLAGS` s odůvodněním
  "stylista nespouští žádné shell příkazy, nejrestriktivnější execpolicy
  je ideální". Obojí špatně:
  1. `codex exec --help`: `--ignore-rules` = "Do not load user or project
     execpolicy .rules files" - flag pravidla ODSTRAŇUJE, nepřidává
     restrikci. Uživatelova `.rules` s `forbidden`/`prompt` patterny by
     mohla omezit, jaké příkazy Codex spustí → `--ignore-rules` útočnou
     plochu ROZŠIŘUJE.
  2. "stylista nespouští shell příkazy" je věcně chybné - canary test
     kola 18 (bod 6 v `polish` docstringu) ukázal, že `codex exec` jako
     agentní nástroj SPUSTIL `Get-Content` pro čtení souboru mimo `-C`.
  Opt-in `STYLIST_ACCEPT_FS_RISK` přiznává plný FS risk, ale není důvod
  navrch rušit uživatelovy restriktivní pravidla. `--ignore-rules`
  odstraněn z `_CODEX_STATIC_FLAGS`, argv testu i canary checklistu.
  `--ignore-user-config` (hang fix, kolo 17) ZŮSTÁVÁ - je SAMOSTATNÝ flag
  a execpolicy `.rules` neřeší; hang pocházel z MCP/plugin loadingu v
  `config.toml`, ne z `.rules`.

### Agreed but already addressed / NITS
- **NIT - docstring nadpis "kola 1-6 a 17-20" zastaralý:** opraveno na
  "kola 1-6, 17-20 a 25".
- **NIT - rozhodnutí ř. 2985 tvrdí, že `test_polish_config_invariants`
  testuje timeout:** správně - timeout ověřuje samostatný
  `test_polish_uses_config_timeout_and_strips_model`. Bullet přeformulován.

## Claude VERDICT

Kolo 25 IMPORTANT byl reálný - kolo-23 změna (moje) měla obrácené
bezpečnostní zdůvodnění a opírala se o věcně chybné tvrzení vyvrácené
vlastním canary testem dokumentu. Vráceno. Po opravě + 2 NITS nenacházím
nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 25: Codex našel 1 IMPORTANT + 2 NITS (0 BLOCKING, šesté kolo v řadě).
IMPORTANT: kolo-23 přidání `--ignore-rules` mělo obrácené zdůvodnění -
flag NEnačte user/project execpolicy `.rules`, čímž útočnou plochu
ROZŠIŘUJE (restriktivní `forbidden`/`prompt` pravidla by exfiltraci
omezila), a tvrzení "stylista nespouští shell příkazy" je vyvráceno
canary testem (Codex spustil `Get-Content`). `--ignore-rules` odstraněn
z argv/testů/checklistu; `--ignore-user-config` (hang fix) zůstává.
NITs: docstring nadpis, stale próza u timeout testu. Čeká se na kolo 26
(25/30 stropu).
