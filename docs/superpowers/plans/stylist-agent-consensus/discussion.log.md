# Plan-consensus: discussion log

- Plán: `docs/superpowers/plans/2026-09-10-stylist-agent.md`
- Spec (zdroj): `docs/superpowers/specs/2026-09-08-stylist-agent-design.md` (CONSENSUS po 38 kolech)
- Start: 2026-09-10 19:23:59
- Max kol: 15
- Kritici: Codex (read-only) + Claude, oba hledají problémy, ne shodu

---

## Kolo 1 — 2026-09-10 19:39:03

- Codex: [round-1-codex.md](round-1-codex.md) — CHANGES_NEEDED (3 BLOCKING, 7 IMPORTANT, 3 NITS)
- Claude: [round-1-claude.md](round-1-claude.md) — CHANGES_NEEDED

**Změny v plánu:**
- Task 5: 3 spec-verbatim testy porušují délkový guard (poměr >1.5×) → Step 1a/1b, opravené verze inline. Fake stdin skripty → `sys.stdin.buffer.read().decode("utf-8")`. `long_cz` `.strip()` fix.
- Task 8: keep-untranslated test přepsán (leak nález nedosažitelný přes check_chapter); +case/deklinace test, +real check_chapter integrace, +dedup B-a-A test.
- Task 7: +modulový `from src.agents import stylist`.
- Task 11: lokální import stylistu VYNECHÁN; +critic_failed-skip, +redakční matice, +provenience (real concordance), +no-backup-on-reject.
- Task 12: `_print_usage` → `_say`; `_polish_env` ji nemockuje; +generic-exception-continues, +interrupt po/před commitem, +`--force`+interrupt, +`_client_factory` pád, +`_run_critic` FatalRunError, +zachování staré zálohy.
- Task 13: model/config-suppression/isolace kontroly; POVINNÝ Step 5 revert `STYLIST_ACCEPT_FS_RISK=False`.
- Global Constraints: commit trailer pravidlo; fake stdin pravidlo; délkový guard poznámka.
- Task 1/4: rozsahy řádků opraveny (344-400 / 433-746).

**Sporné:** 0. Sešlo se ~15 nových testů + ~10 editovaných sekcí.

## Kolo 2 — 2026-09-10 19:45:05

- Codex: [round-2-codex.md](round-2-codex.md) — CHANGES_NEEDED (4 IMPORTANT, 2 NITS)
- Claude: [round-2-claude.md](round-2-claude.md) — CHANGES_NEEDED (0 vlastních)

**Změny:**
- Task 5: odchylka `except BaseException` - kill sirotčího codex procesu při Ctrl+C (+test).
- Task 11: provenience test přepsán - 2 různé termíny, spy na check_chapter I build_mentions, přesná rovnost rendered argumentu.
- Task 12: +test `backup_predates_run_bookkeeping` (.pre-polish-backup nemá runs řádek).
- Task 13: přepsán - canary PRVNÍ; reálný běh nad KOPIÍ DB v TMP; config jen runtime atributy, config.py se needituje.
- Task 2: +test null/chybějící findings = [] (ne rozbité).
- Rozsahy: config 345-400, modul 434-746 (fence byl v rozsahu).

**Sporné:** 0. Konvergence: 3 BLOCKING → 0, 7 IMPORTANT → 4.

## Kolo 3 — 2026-09-10 19:45:39 — POZASTAVENO

Codex `exec`: **usage limit vyčerpán** ("try again at 10:04 PM"). Kolo 3 neproběhlo.
Loop pozastaven po kole 2. Reset kvóty ~22:04.

## Kolo 3 — 2026-09-10 22:25:27

- Codex: [round-3-codex.md](round-3-codex.md) — CHANGES_NEEDED (1 BLOCKING, 2 IMPORTANT)
- Claude: [round-3-claude.md](round-3-claude.md) — CHANGES_NEEDED (0 vlastních)

**Změny:**
- Task 5 (BLOCKING): parsující fake stdin → `.decode("utf-8").replace("\r\n","\n")` - `Popen(text=True)` na Windows dělá `\n`→`\r\n` na zápisu, raw čtení to nevrací.
- Task 5: KI test přepsán na plný `FakePopen` (reálný proces = 10s timeout + sirotek), assert pořadí communicate→kill_tree→wait:10.
- Task 13 Step 3: `shutil.copy2` živé DB → `main._snapshot_db` (spec 1333+ copy2 odmítá).

**Sporné:** 0. Vše fallout dřívějších fixů.

## Kolo 4 — 2026-09-10 22:30:31

- Codex: [round-4-codex.md](round-4-codex.md) — CHANGES_NEEDED (3 IMPORTANT)
- Claude: [round-4-claude.md](round-4-claude.md) — CHANGES_NEEDED (0 vlastních)

**Změny:**
- Task 12: odchylka - append do `finally` (uzavře KI okno mezi návratem helperu a appendem) + identitní stráž; +test úplnosti reportu.
- Task 5 Step 1c: parametrizovaná redakční matice (stderr/číslo/odstavce/poměr × False/1/"False"/None/True) + `_fake_codex_stderr`.
- Task 13: Codex pozorování (MCP/config/kontext) → přímý Step 2; Step 3 `force=True` + `REPORT_REJECTED_TEXT=True` v TMP + assert attempted_count>=1.

**Sporné:** 0.

## Kolo 5 — 2026-09-10 22:34:32

- Codex: [round-5-codex.md](round-5-codex.md) — CHANGES_NEEDED (2 IMPORTANT, 2 NITS)
- Claude: [round-5-claude.md](round-5-claude.md) — CHANGES_NEEDED (0 vlastních)

**Změny (vše fallout kolo 4):**
- Task 12: kolo-4 append fix měl vlastní KI mezeru (během `_say` v error handleru) → kolo-5: JEDEN `finally`, bezpodmínečný append, rec dopočítán z DB. Identitní stráž pryč. +test KI-během-`_say`.
- Task 13 Step 2: přímý `codex exec` → konkrétní Popen runner s timeout + `_kill_process_tree`.
- Task 13 Step 3: `unchanged` uznán jako legitimní výsledek.

**Sporné:** 0. Vzorec "přídavek plodí přídavek".

## Kolo 6 — 2026-09-10 22:36:35

- Codex: [round-6-codex.md](round-6-codex.md) — CHANGES_NEEDED (1 IMPORTANT)
- Claude: [round-6-claude.md](round-6-claude.md) — CHANGES_NEEDED (0 vlastních)

**Změna:** `counts` slovník zrušen (kolo-5 ho dal do `else`, nezapočítal `failed` z neočekávané výjimky → all-failed dávka vracela `ok`). Souhrn i all-failed podmínka se počítají z `report` po smyčce. +test s generickou výjimkou.

**Sporné:** 0. Append-invariant refactoring usazený (4→5→6).

## Kolo 7 — 2026-09-10 22:39:14

- Codex: [round-7-codex.md](round-7-codex.md) — CHANGES_NEEDED (1 IMPORTANT, 3 NITS)
- Claude: [round-7-claude.md](round-7-claude.md) — CHANGES_NEEDED (0 vlastních)

**Změny:**
- Task 11: +integrační test skutečný critic.review/_run_critic s verdict="SECRET123", opt-in OFF → secret neuniká (default-safe pojistka).
- Task 11 Step 3: druhá odchylka - docstring "tři append větve" → "jeden ve finally".
- Task 13 Step 2 canary runner: `except BaseException` + `finally` úklid T1/T2 + utf-8 encoding.

**Sporné:** 0. 0 BLOCKING už 4 kola, IMPORTANT klesá.

## Kolo 8 — 2026-09-10 22:40:40

- Codex: [round-8-codex.md](round-8-codex.md) — CHANGES_NEEDED (1 IMPORTANT, 1 NIT)
- Claude: [round-8-claude.md](round-8-claude.md) — CHANGES_NEEDED (0 vlastních)

**Změny (test-rigor):**
- Task 13 canary runner: token do proměnné, `leaked` vyhodnocen před `finally` úklidem, +`returncode` check.
- Task 8 integrační test: assert předpokladů (1 leak baseline i after, shodný `_finding_key`) → `True` dokazuje JEN větev počtu výskytů.

**Sporné:** 0. 0 BLOCKING 5 kol za sebou, IMPORTANT jen o rigoru testů.

## Kolo 9 — 2026-09-10 22:42:15

- Codex: [round-9-codex.md](round-9-codex.md) — CHANGES_NEEDED (1 IMPORTANT)
- Claude: [round-9-claude.md](round-9-claude.md) — CHANGES_NEEDED (0 vlastních)

**Změna:** `guide_block` předání netestované → +test Task 5 (stdin) + Task 12 (kwarg spy). Rejstříková pravidla by šla tiše odstranit.

**Sporné:** 0. 0 BLOCKING 6 kol. IMPORTANT už jen "chybí test X".

## Kolo 10 — 2026-09-10 22:45:39 — CONSENSUS

- Codex: [round-10-codex.md](round-10-codex.md) — **CONSENSUS** (1 NIT)
- Claude: [round-10-claude.md](round-10-claude.md) — **CONSENSUS** (0 vlastních)

Nezávislý průchod celého plánu 0 BLOCKING/IMPORTANT. NIT: komentářová záměna čísla řádku (spec 171 vs src/concordance.py). Task 12 deviation zjednodušen na jeden try/except/finally.

**SHODA po 10 kolech. Viz [final-verdict.md](final-verdict.md).**
