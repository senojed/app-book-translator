# Round 22 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (první `_run_critic()` před revizní smyčkou bez
  checkpointu):** Souhlasím a ověřil jsem přesně - checkpoint z kol
  13/18/20/21 obaluje jen `revise_chapter()`+`_run_critic()` UVNITŘ
  `while` smyčky. PRVNÍ `_run_critic()` volání (architektonicky MIMO a
  PŘED smyčkou, po scénovém překladu) žádnou ochranu nikdy nemělo -
  jeho `FatalRunError` (kritik VŽDY Claude, i při `--translator codex`)
  by propagoval z CELÉ `process_chapter()`, zahodil hotový `cz`,
  kapitola zůstala `processing`.

  **Oprava:** Vytažena sdílená `_checkpoint_flagged(cz_now, findings_now,
  questions_now, rounds_now, error)` pomocná funkce (nahrazuje kol-13/18/
  20's nastřádanou inline logiku ~50 řádků třemi voláními). Pre-loop
  `_run_critic()` teď obalen `try/except FatalRunError`, co checkpoint
  zavolá a re-raisne. Přidány dva regresní testy: úspěšný scénový
  překlad + kritikův `FatalRunError` zachová `cz`; a stejný scénář s
  NOVOU otázkou ze scénového překladu ověří, že se otázka taky uloží
  (pokrývá zároveň třetí bod níž).

- **IMPORTANT (eager preflight neověří ANTHROPIC_API_KEY pro kritika):**
  Souhlasím - `_polish_preflight()` ověří jen Codex stranu
  (FS_RISK/CODEX_MODEL/CLI), `AnthropicClient` se konstruuje líně až
  při prvním `client_factory("critic")` volání, PO dokončení (zaplaceného)
  Codex scénového překladu. Bez eager kontroly by chybějící klíč nechal
  proběhnout celý překlad zbytečně.

  **Oprava:** Přidána eager kontrola `if not config.ANTHROPIC_API_KEY:`
  hned za Codex FS-risk preflight v `_cmd_run`. ZVÁŽIL jsem dvě varianty -
  konstrukci skutečného `AnthropicClient()` (čitelnější, ale zavádí
  závislost na klíči do ~7 existujících testů, co dnes mockují
  `pipeline.process_chapter` a klíč nikdy reálně nepotřebují) vs. přímou
  kontrolu `config.ANTHROPIC_API_KEY` (stejná podmínka jako
  `AnthropicClient.__init__`, žádná nová závislost). Zvolil jsem přímou
  kontrolu - nulový dopad na existující testy, stejné chování. I tak
  jsem do 7 existujících testů (co mockují `_polish_preflight` na
  úspěch, tedy by mou eager kontrolu nově zasáhly) přidal
  `monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")`, aby
  zůstaly deterministické nezávisle na skutečném prostředí (stejný vzor,
  co už Task 4's `test_client_factory_translator_backend_codex_critic_
  stays_claude` používal). Přidán nový regresní test
  `test_run_translator_codex_missing_anthropic_key_fails_eager` (ověřuje
  `== 1`, hláška s "ANTHROPIC_API_KEY", a že se `process_chapter`
  VŮBEC nezavolá - žádný zaplacený Codex překlad naprázdno).

- **IMPORTANT (`questions=existing_questions` v checkpointu zahazuje
  otázky z POSLEDNÍHO platného `cz`):** Souhlasím a ověřil jsem přesně -
  kolo-20's snapshot nese jen otázky z PŘEDCHOZÍHO DB běhu (pořízený
  PŘED `begin_chapter()`), ale checkpoint posílá `existing_questions`
  BEZ ohledu na to, co scénový překlad/revize PRÁVĚ vygenerovaly (lokální
  `questions` proměnná) - ty by se ztratily, i když se jejich `cz` uloží.

  **Oprava:** `_checkpoint_flagged()` staví `fresh_db_questions` z
  předaného `questions_now` (STEJNÁ transformace jako normální commit
  cesta) a posílá `questions=existing_questions + fresh_db_questions` -
  sloučení STARÝCH (snapshot) a NOVÝCH (aktuální pokus) otázek.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 22: tři IMPORTANT body, všechny potvrzené. (1) checkpoint
rozšířen i na PRVNÍ `_run_critic()` volání před revizní smyčkou přes
sdílenou `_checkpoint_flagged()` pomocnou funkci (eliminuje třetí kopii
duplikované logiky). (2) eager preflight teď ověří i `ANTHROPIC_API_KEY`
pro kritika - zvolena lehčí varianta (přímá kontrola `config.
ANTHROPIC_API_KEY`, ne konstrukce `AnthropicClient()`) kvůli nulovému
dopadu na existující testy; přesto 7 existujících testů dostalo
`ANTHROPIC_API_KEY` mock, protože moje nová kontrola je nově zasáhne.
(3) checkpoint's obnovené otázky teď slučují starý snapshot s otázkami
z posledního platného `cz`, ne jen snapshot samotný. Čtvrté kolo v řadě
"kolo N našlo mezeru v kole M's fixu" pro stejnou oblast (revizní/
checkpoint logika) - konzistentně se zužuje, žádný nový nález mimo
Codexovy tři body.
