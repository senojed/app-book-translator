# Plan-consensus discussion log

- Plan: `docs/superpowers/plans/2026-09-16-codex-translator-backend.md`
- Start: 2026-09-16T09:13:52Z
- Max rounds: 30

## Round 1 — 2026-09-16T09:13:52Z (odhad)

- Codex: [round-1-codex.md](round-1-codex.md) — CHANGES_NEEDED
- Claude: [round-1-claude.md](round-1-claude.md) — CHANGES_NEEDED

Opraveno: BLOCKING (model propagace - CodexLLMClient dostal `billed_model`,
PipelineLLMClient.complete() opraven používat effective_model pro
cenu/audit), IMPORTANT (chybějící CODEX_TRANSLATE_MAX_CHARS guard přidán),
IMPORTANT (Task 5 Step 2 přepsán na reálný BOOK_TRANSLATOR_PROJECT_DIR
postup). Odmítnuto s odůvodněním: IMPORTANT "StylistError vždy fatal" -
existující precedent (_polish_one_chapter) už stejnou třídu chyby řeší
jako per-kapitolovou.

## Round 2

- Codex: [round-2-codex.md](round-2-codex.md) — CHANGES_NEEDED
- Claude: [round-2-claude.md](round-2-claude.md) — CHANGES_NEEDED

Opraveno: OBRÁCENO kolo-1 rozhodnutí o StylistError (nový fakt -
state.queue_for_run automaticky retryuje 'error' kapitoly - CodexLLMClient
teď přebaluje StylistError na FatalRunError, celý běh se zastaví).
CODEX_TRANSLATE_MAX_CHARS guard z kola 1 ZRUŠEN (mohl by zahodit hotovou
scénovou práci při selhání revizní fáze - pipeline.process_chapter nemá
checkpoint před revizí). Task 5 Step 2 doplněn o PowerShell variantu.

## Round 3

- Codex: [round-3-codex.md](round-3-codex.md) — CHANGES_NEEDED
- Claude: [round-3-claude.md](round-3-claude.md) — CHANGES_NEEDED

Opraveno: BLOCKING (translator._parse() tiše přijalo useknutý Codex výstup
jako hotový překlad, protože CodexLLMClient.truncated je vždy False a
chybějící ===METADATA=== marker split_sections nezachytí - nová Task 2,
povinný ===KONEC=== marker, backend-agnostické). IMPORTANT (revizní smyčka
v pipeline.py teď zachová poslední platný překlad při chybě revize -
mirror _run_critic()'s vzoru, součást Task 2 - fix výš zvýšil
pravděpodobnost týhle cesty). IMPORTANT (--translator codex preflight
se ověřuje eager PŘED frontou, ne líně - prázdná fronta by ho jinak
obešla). IMPORTANT (chybové hlášky z --translator codex jdou přes
stylist._redact_detail() jako u _cmd_polish - extract_json()'s ValueError
nese až 2000 raw znaků do chapters.notes bez redakce). Plán přeuspořádán:
nová Task 2, staré Task 2-5 posunuté na Task 3-6.

## Round 4

- Codex: [round-4-codex.md](round-4-codex.md) — CHANGES_NEEDED
- Claude: [round-4-claude.md](round-4-claude.md) — CHANGES_NEEDED

Opraveno: 2× BLOCKING, oba v Claudově vlastním kolo-3 kódu. (1)
`MARK_END not in raw` kontrolovalo jen přítomnost markeru, ne pozici/
počet - chybějící METADATA marker by nechal ===KONEC=== zapečený jako
součást přeloženého textu; opraveno přesnou strukturální kontrolou
(počet==1 každého markeru, pořadí, raw.rstrip().endswith). (2) Task 5's
test_run_translator_flag_passed_to_client_factory nemockoval eager
preflight z kola 3 - v CI bez codex binárky by spadl dřív, než se spy
factory zavolá; opraveno přidáním mocku. Přidány negativní testy pro
duplicitní/špatně umístěný marker a text po markeru.

## Round 5

- Codex: [round-5-codex.md](round-5-codex.md) — CHANGES_NEEDED
- Claude: [round-5-claude.md](round-5-claude.md) — CHANGES_NEEDED

Opraveno: IMPORTANT (CodexLLMClient.complete() vracelo input_tokens=0,
output_tokens=0 natvrdo - main._print_usage() by po zpracování celé
knihy ukázalo "0 tokenů" i přes reálnou práci; opraveno konzervativním
odhadem, stejný vzorec jako count_tokens()). NIT (přidán regresní test,
že oba systémové prompty obsahují ===KONEC=== instrukci).

## Round 6

- Codex: [round-6-codex.md](round-6-codex.md) — CHANGES_NEEDED
- Claude: [round-6-claude.md](round-6-claude.md) — CHANGES_NEEDED

Opraveno: BLOCKING (kolo 5's token-odhad test měl špatný vzorec vs.
implementace - opraven test, implementace byla správně). IMPORTANT
(translator._parse()'s ValueError ze SCÉNOVÉ smyčky, na rozdíl od
revizní, propadal jako obyčejný per-kapitolový error - state.
queue_for_run by ho tiše retryoval navěky při formát-driftu Codexu;
nová InvalidTranslationOutput podtřída ValueError, --translator codex
ji dělá fatální stejně jako kolo-2's StylistError fix). Přidány
negativní testy pro duplicitní PREKLAD/METADATA marker a špatné pořadí.

## Round 7

- Codex: [round-7-codex.md](round-7-codex.md) — CHANGES_NEEDED
- Claude: [round-7-claude.md](round-7-claude.md) — CHANGES_NEEDED

Opraveno: 3x IMPORTANT. CodexLLMClient.complete() teď zachytává i
OSError/UnicodeError (_exec_codex()'s výstupní-soubor čtení není kryté
vlastním try/except, stejná díra jako kolo 6 řešilo jinde). Task 3's
klíčový test opraven - používal stejnou hodnotu pro model i codex_model,
nezachytil by regresi při záměně. Task 6's manuální ověření zpřesněno -
explicitní pending-kapitola instrukce + llm_calls SQL kontrola
provider='codex'/cost_usd=0.0.
