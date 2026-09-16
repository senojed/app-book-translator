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

## Round 8

- Codex: [round-8-codex.md](round-8-codex.md) — CHANGES_NEEDED
- Claude: [round-8-claude.md](round-8-claude.md) — CHANGES_NEEDED

Opraveno: 3x IMPORTANT. Kolo-3's eager preflight omylem předběhl
recover_processing - --translator codex s nesplněnou podmínkou by
nechalo processing-kapitoly uvízlé navěky (queue_for_run je nevidí);
prohozeno pořadí, recovery zůstává úplně první krok. CodexLLMClient's
FatalRunError zprávy teď jdou přes stylist._redact_detail() (docstring
výslovně jmenuje "str(e) neočekávané výjimky"). Přidán chybějící test
ověřující, že i _guard() (cost-limit, ne jen audit log) použije
effective_model.

## Round 9

- Codex: [round-9-codex.md](round-9-codex.md) — CHANGES_NEEDED
- Claude: [round-9-claude.md](round-9-claude.md) — CHANGES_NEEDED

Opraveno: 2x IMPORTANT, oba odhalily mezery ve VLASTNÍCH dřívějších
fixech. Kolo-2's StylistError->FatalRunError omylem zahrnul i timeout
(per-call/transientní), ne jen systémová selhání - přímo popíralo
kolo-3's slib "revize zachová hotový překlad"; opraveno novou
StylistTimeoutError podtřídou (minimální zásah do stylist.py). Marker
parsing (count/index) hledal substring kdekoli v textu, ne řádek -
legitimní obsah s marker-podobným textem uprostřed by se chybně
odmítl; opraveno řádkově kotveným regexem.

## Round 10

- Codex: [round-10-codex.md](round-10-codex.md) — CHANGES_NEEDED
- Claude: [round-10-claude.md](round-10-claude.md) — CHANGES_NEEDED

Opraveno: BLOCKING (kolo-9's radkove kotvena validace byla spravna, ale
split_sections() delala vlastni nezavisle substring hledani, porad
zranitelne na marker-podobny text uprostred JSON hodnoty - opraveno
primym slicingem podle overenych pozic, split_sections() se uz
nepouziva). IMPORTANT (FatalRunError nechavalo kapitolu v processing
limbu, dalsi run by ji tise zaradil znovu bez explicitniho
--retry-flagged - prijato s vyhradou o nizsi zavaznosti nez kolo 2/6,
oprava je porad realne zlepseni).

## Round 11

- Codex: [round-11-codex.md](round-11-codex.md) — CHANGES_NEEDED
- Claude: [round-11-claude.md](round-11-claude.md) — CHANGES_NEEDED

Opraveno: 3x IMPORTANT + 1 NIT. args.translator=="codex" gate v
_cmd_run reagovalo na nastaveni backendu, ne puvod chyby - kritikova
Claude-side FatalRunError (cost guard) by dostala Codex-specificke
flagged zachazeni; opraveno novou CodexTranslatorFatalError podtridou,
rozliseni podle TYPU. ^marker$ regex neprijme CRLF radky (Windows-
primarni projekt); opraveno explicitni normalizaci. Existujici timeout
test v test_stylist.py overoval jen rodicovsky typ; zprisneno na
StylistTimeoutError. NIT o zdokumentovani preambule-tolerance.

## Round 12

- Codex: [round-12-codex.md](round-12-codex.md) — CHANGES_NEEDED
- Claude: [round-12-claude.md](round-12-claude.md) — CHANGES_NEEDED

Opraveno: 3x IMPORTANT. _client_factory's vlastni lina preflight
kontrola vyhazovala holy FatalRunError, ne CodexTranslatorFatalError -
stejna mezera jako kolo 11 resilo jinde. Task 5's Interfaces dokumentace
nebyla po kole 11 plne prepsana, stale popisovala stary
args.translator-gated mechanismus. _parse() validovala jen JSON syntaxi,
ne tvar - []/{"new_terms":"x"} by unikaly klasifikaci jako format-drift.
Vsechny opraveny, plan je vnitrne konzistentni.

## Round 13

- Codex: [round-13-codex.md](round-13-codex.md) — CHANGES_NEEDED
- Claude: [round-13-claude.md](round-13-claude.md) — CHANGES_NEEDED

Opraveno: IMPORTANT - kolo 10/11's flagged status oprava byla jen
kosmeticka pro revizni-fazi fatalni chybu - pipeline.py's except
FatalRunError: raise nikdy nic necommitoval, translated_text zustaval
ztraceny. Existujici test dokonce assertoval opak zamysleneho chovani
(status != flagged) - dukaz, ze bug byl od kola 10 nezpozorovany.
Opraveno: revizni smycka ulozi posledni platny cz PRED re-raise
fatalni chyby, minimalni transakce B. Existujici test prepsan.

## Round 14

- Codex: [round-14-codex.md](round-14-codex.md) — CHANGES_NEEDED
- Claude: [round-14-claude.md](round-14-claude.md) — CHANGES_NEEDED

Opraveno: 2x IMPORTANT plne (_parse() validuje typ poli UVNITR
new_terms/rendered_terms/questions polozek, ne jen ze polozka je dict;
CodexLLMClient ma vlastni STYLIST_ACCEPT_FS_RISK kontrolu nezavislou
na _client_factory, stejny vzor jako stylist.polish()). 1x IMPORTANT
castecne - DB kopie v Task 6 opravena na SQLite .backup (konzistentni
snapshot), ale tvrzeni "polish odmita flagged kapitolu" overeno proti
main.py a vyvraceno - _cmd_polish EXPLICITNE zahrnuje flagged/
needs_human (zamerny, drivejsi design fix tohohle projektu). Prvni
pripad v tomhle plan-consensus, kdy Codexovo tvrzeni bylo v rozporu se
skutecnym kodem.
