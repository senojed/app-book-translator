# Plan-consensus log

Plan: docs/superpowers/specs/2026-09-08-stylist-agent-design.md
Start: 2026-09-08
Max rounds: bez limitu (do konsensu), bezpečnostní strop 30 kol (pak stop
- konsensus nebo impasse, cokoli nastane dřív)

## Kolo 1 - 2026-09-08

Codex: CHANGES_NEEDED (3 BLOCKING, 9 IMPORTANT/NITS).
Claude: CHANGES_NEEDED -> po aplikaci oprav CONSENSUS (vlastní verdikt).

Opraveno: argv limit delky (prompt pres soubor), izolovany cwd pro Codex,
deterministicka strukturalni kontrola (odstavce+delka) v stylist.polish,
finish_run lifecycle, interactive=True, prisnejsi _polish_rejected (leak/
omission/inconsistency/fidelity bez ohledu na severity), list[str] codex_cmd,
broad exception handling per-kapitola, idempotence pres notes marker +
--force, rizeny CODEX_MODEL.

Zuzeno s odůvodněním: plna historie prekladu (misto toho hash+delka v
markeru), plny audit zamitnutych/selhanych pokusu (jen konzole, zadna DB
zmena tam nehrozi).

Soubory: round-1-codex.md, round-1-claude.md.
Odkazy: viz oba soubory pro plne zneni.

## Kolo 2 - 2026-09-08

Codex: CHANGES_NEEDED (3 BLOCKING, 5 IMPORTANT, 3 NITS).
Claude: CHANGES_NEEDED -> po aplikaci oprav CONSENSUS (vlastní verdikt).

Opraveno: -o/read-only sandbox kontradikce (agent uz nezapisuje soubor,
-o zachyti posledni zpravu), shutil.which pro Windows codex.cmd, vlastni
testy prepsane at nekoliduji s kontrolou pomeru delky, treti kontrolni
vrstva (check_meaning_preserved, CZ-pred vs CZ-po), per-kapitolovy try
roztazen na celou _polish_one_chapter, FatalRunError propagace mimo
per-kapitolovy except, CODEX_MODEL povinne (zadny None fallback),
_already_styled isinstance guard, _print_usage, poznamka o manualnim
overeni (testy mockuji CLI, nechytnou realne executable/sandbox problemy).

Soubory: round-2-codex.md, round-2-claude.md.

## Kolo 3 - 2026-09-08

Codex: CHANGES_NEEDED (2 BLOCKING, 6 IMPORTANT, 2 NITS).
Claude: CHANGES_NEEDED -> po aplikaci oprav CONSENSUS (vlastni verdikt).

Opraveno: main.py chybejici importy (concordance, glossary, hashlib) -
overeno primym ctenim, kritik.review() verdict/findings nesoulad (oprava
v critic.py, prospiva i run - predexistujici mezera), _polish_rejected
prepsan na baseline-vs-after srovnani (pre-existujici minor nalez uz
kapitolu neblokuje navzdy), detekce styled==cz (unchanged vetev, zadny
marker), preflight (_resolve_codex_cmd na zacatku, ne v loopu),
TemporaryDirectory context manager, normalizace modelu jednou, mrtvy
isinstance(KeyboardInterrupt) kod odstranen.

Nesouhlas (zduvodneno): plna verzovana historie/rollback - nekonzistentni
precedens vuci translator.revise_chapter, ktery taky prepisuje bez historie.

Soubory: round-3-codex.md, round-3-claude.md.

## Kolo 4 - 2026-09-08

Codex: CHANGES_NEEDED (1 BLOCKING, 6 IMPORTANT, 2 NITS).
Claude: CHANGES_NEEDED -> po aplikaci oprav CONSENSUS (vlastni verdikt).

Opraveno: critic.review() isinstance(list) guard pro findings (BLOCKING),
--ephemeral flag pridan (overeno primo `codex exec --help`), vstup
prepsan ze souboru na stdin (overeno ze `-` cte stdin), _polish_rejected
pocita baseline CERSTVE (concordance.check_chapter na cz, ne ze starych
notes), klic rozsiren o actual hodnotu, preflight + nenulovy exit kod pri
"vsechno selhalo", --only hlasi preskocene, markdown-fence guard.

Nesouhlas (zduvodneno, 3 body): deterministicka kontrola cisel/dat (LLM
meaning-check uz to pokryva, konzistentni s architekturou), automaticka
kvalitativni verifikace stylu (mimo zadani, uzivatel je posledni soudce),
plna term_mentions provenience po stylizaci (metadatova ztrata, ne
signalova, plna oprava vyzaduje novou infrastrukturu mimo rozsah).

Soubory: round-4-codex.md, round-4-claude.md.

## Kolo 5 - 2026-09-08

Codex: CHANGES_NEEDED (2 BLOCKING, 4 IMPORTANT, 3 NITS).
Claude: CHANGES_NEEDED -> po aplikaci oprav CONSENSUS (vlastni verdikt).

Opraveno: encoding="utf-8" na Popen (overeno vlastni zkusenosti z teto
session), rendered_terms=[] REVIDOVANO z kola 4 - pridan state.chapter_
mentions() getter, pouzit pro baseline+after+mentions rebuild (skutecna
slepa skvrna, ne jen ztrata metadat), critic.review() validuje verdict
enum, Popen+communicate + _kill_process_tree (taskkill /T /F na Windows
timeout), "vsechno selhalo" -> status="fatal" (opravuje kolo-4 rozpor),
3x oprava zastarale prozy (stdin misto souboru, cerstva baseline misto
notes, (type,term_id,actual) klic).

Nesouhlas (zachovano z kola 4, prohloubene zduvodneni): deterministicka
cisla/data (i uzsi verze by byla nova schopnost bez precedentu),
automaticka kvalita stylu (mimo zadani).

Soubory: round-5-codex.md, round-5-claude.md.

## Kolo 6 - 2026-09-09

Codex: CHANGES_NEEDED (1 BLOCKING, 3 IMPORTANT, 5 NITS).
Claude: CHANGES_NEEDED -> po aplikaci oprav CONSENSUS (vlastni verdikt).

Opraveno: kolo-5 status="fatal" oprava dopromitnuta do testovaci prozy+
tabulky (byla jen v kodu), taskkill fallback na proc.kill() + omezeny
wait(10s), guide_block (tykani/vykani, hlas, rejstrik) predavan
stylistovi - novy silny bod, deterministicka cisla PRIDANA (REVERZOVANO
z kola 4-5 nesouhlasu - novy kvalitativne jiny argument presvedcil),
SHA-256 misto zkraceneho SHA-1, oprava nadsazky o "text nikdy nezapsan
na disk", 6x oprava zastarale prozy.

Nesouhlas (zachovano): automaticka kvalitativni verifikace stylu - mimo
zadani, Codex to v kole 6 nezopakoval.

Soubory: round-6-codex.md, round-6-claude.md.

## Kolo 7 - 2026-09-09

Codex: CHANGES_NEEDED (4 IMPORTANT, 1 NIT).
Claude: CHANGES_NEEDED -> po aplikaci oprav CONSENSUS (vlastni verdikt).

Opraveno: check_meaning_preserved rozsireno o register_changed +
register_drift nalez (registr/tykani jen instrukci bez verifikace),
shutil.copy2 zaloha CELE DB pred prvnim zapisem (skutecna obnovitelnost
misto jen hash-detekce), critic.review() isinstance(data, dict) na
top-level + mixed findings odmitnuty cele (misto ticheho filtru),
taskkill vlastni timeout=10 + except fallback, stary kolo-4 "cisla mimo
rozsah" bullet nahrazen presnym popisem, posledni zbyly status="ok"
vyskyt opraven (unikl kolo-6 oprave).

Zadny novy nesouhlas - vsechny 4 IMPORTANT + 1 NIT prijaty a opraveny.

Soubory: round-7-codex.md, round-7-claude.md.

## Kolo 8 - 2026-09-09

Codex: CHANGES_NEEDED (5 IMPORTANT, 5 NITS, 0 BLOCKING).
Claude: CHANGES_NEEDED -> po aplikaci oprav CONSENSUS (vlastni verdikt).

Opraveno: zaloha DB prevedena z eager na liny (_backup_db_once, tesne
pred prvnim commit_chapter_result, ne bezpodminecne na zacatku - jinak
by prepsala poslednni uzitecnou zalohu behem co nic nezapise), Popen
chyta OSError misto jen FileNotFoundError (PermissionError test pridan),
codex_cmd skutecne reseny jednou (preflight vysledek se posila dal, ne
jen tvrzeni), manualni overeni rozsireno na explicitni checklist (6
polozek), 3x zbyla stale proza opravena (_polish_rejected docstring
notes-baseline, TemporaryDirectory komentar vnitrni rozpor, shrnuti tri
vrstev bez cisel/registru).

Zadny novy nesouhlas.

Soubory: round-8-codex.md, round-8-claude.md.

## Kolo 9

Codex: CHANGES_NEEDED (1 BLOCKING, 5 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci).

Zavedena dvoufázová záloha DB (snapshot PŘED `state.create_run`, atomická
promoce `os.replace` až při prvním skutečném zápisu výsledku) - opravuje
BLOCKING nález, že kolo-8 lazy-backup timing pořád nezachytával skutečný
pre-invocation stav (`create_run`/`llm_calls` z kritika u zamítnutých
kapitol mění DB dřív, než záloha vůbec proběhne). Dál: kritik teď
validuje `severity`/`type` KAŽDÉHO nálezu (ne jen top-level tvar),
`check_meaning_preserved` používá `isinstance(bool)` místo `in (True,
False)` (Python `0==False`/`1==True` mezera), nový test ověřuje přesný
argv Codex volání (fake skript zapíše `sys.argv` do JSON), a `_polish_
one_chapter` teď přeskočí placené `check_meaning_preserved`, když
konkordance/kritik zamítnutí už zaručují. Stale próza: cílený sweep
nenašel nic mimo to, co BLOCKING oprava sama přepsala.

Soubory: round-9-codex.md, round-9-claude.md.


## Kolo 10

Codex: CHANGES_NEEDED (1 BLOCKING, 4 IMPORTANT).
Claude: CONSENSUS (po aplikaci; 1 IMPORTANT bod - znaménko čísel -
zamítnut s odůvodněním, 2 próza-lokace po ověření v kontextu odmítnuty
jako už opravené/legitimní historický log).

Opraven argv test (chybná indexace `argv[2:]` místo `argv[1:]` - `sys.
argv` uvnitř spuštěného skriptu neobsahuje interpret, jen vlastní cestu
jako argv[0] - test by DŘÍV VŽDY spadl). Lifecycle snapshotu DB opraven -
celý úsek od `rid = None` je teď uvnitř jednoho `try/finally`, `finish_
run` se volá jen když `create_run` skutečně proběhl. Číselný guard teď
zachytává českou mezeru/NBSP před "%" (dřív byla kontrola procenta na
reálném textu prakticky mrtvá) - znaménko čísel záměrně odmítnuto
(riziko nových falešných poplachů na přetížené pomlačce). Dvě stale
próza místa opravena (guide_block/register bod, `_polish_rejected`
docstring s `[]` místo `rendered_terms`).

Soubory: round-10-codex.md, round-10-claude.md.


## Kolo 11

Codex: CHANGES_NEEDED (0 BLOCKING, 4 IMPORTANT, 3 NITS).
Claude: CONSENSUS (po aplikaci; 1 NIT rozporován - už opraveno v kole 10).

Lifecycle snapshotu DB dotažen (samotné `shutil.copy2` teď taky uvnitř
`try/finally`, ne jen kód okolo). Číselný guard rozšířen o úzkou
nezalomitelnou mezeru U+202F (vedle obyčejné a NBSP z kola 10). Obnova DB
ze zálohy přepsána na atomickou (dočasný soubor + integrity_check +
os.replace, ne přímý copy2 na aktivní DB). Přidány 4 regresní testové
scénáře pro kolo-9 validaci severity/type v kritikovi. Rozhodnutí sekce
dostala kolo-10 bullet (dřív chyběl) a nadpis aktualizován na "kol 1-11".

Soubory: round-11-codex.md, round-11-claude.md.


## Kolo 12

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci; 1 NIT rozporován podruhé - už opraveno v
kole 6, ověřeno přímo).

Selhání zálohy/DB zápisu (`_backup_db_once`/`state.commit_chapter_
result`) se dřív počítalo jako obyčejná per-kapitolová chyba (`failed`),
což mohlo maskovat rozbitou DB/disk za normální výsledek běhu se
`status="ok"`. Opraveno - zabaleno do `FatalRunError`, zastaví celý běh.
Přidáno 5 nových testových scénářů (selhání copy2/os.replace/commit
uprostřed smíšené dávky, ekvivalence čtyř mezerových variant čísla+%).
"Rozhodnutí" próza u starého backup mechanismu dostala explicitní
poznámky, že je nahrazený kolo-9 snapshot+promote designem (stejný
vzorec jako u dřívějšího kolo-4-čísel bullet). `_fake_codex` teď má
explicitní UTF-8 encoding.

Soubory: round-12-codex.md, round-12-claude.md.


## Kolo 13

Codex: CHANGES_NEEDED (0 BLOCKING, 4 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci; 1 IMPORTANT přijat jen zdůvodněním, ne
změnou chování - normalizace desetinného oddělovače zůstává, jen
zdůvodnění opraveno).

`shutil.copy2` snapshotu zabalen do FatalRunError (dřív by obyčejný
OSError propadl jako nezachycený traceback). `finish_run` ve `finally`
teď nemůže přebít původní chybu/return (vlastní try/except, jen vypíše
varování). `_number_multiset` přejmenován na `_number_sequence`,
odstraněno řazení - seřazená množina nerozliší přehození dvou různých
čísel mezi sebou (bezpečné díky tomu, že stylistův prompt už zakazuje
měnit pořadí). Přidány 2 nové regresní testy (swap dvou čísel,
samostatný register_drift). "Rozhodnutí" sekce dostala kolo-12 i kolo-13
bully (kolo 12 taky chybělo, stejná mezera jako u kola 10).

Soubory: round-13-codex.md, round-13-claude.md.


## Kolo 14

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 3 NITS).
Claude: CONSENSUS (po aplikaci; 1 IMPORTANT přijat jako REVERZE vlastní
kolo-13 pozice po novém, kvalitativně jiném argumentu).

Snapshot DB teď přes `sqlite3.Connection.backup()` + integrity_check,
ne `shutil.copy2` (nekonzistentní stav při cizím zápisu, WAL/SHM sidecar
- teoretické u tohohle projektu, ale obecně řešeno). Top-level try/except
v `_cmd_polish` rozšířen na CELÝ příkaz (dřív chráněný jen samotný
snapshot) - `chapters_by_status`/`glossary.all_terms`/`load_guide`/
`create_run`/`_print_usage` byly bez obecného except. Poznámka: `_cmd_run`
má identickou mezeru, vědomě NEopraveno (mimo rozsah). REVERZOVÁNA
vlastní kolo-13 pozice - normalizace desetinného oddělovače (,/.)
ZRUŠENA po Codexově "Python 3.5" protipříkladu (verzové číslo, ne
desetinná hodnota - normalizace by tiše přijala poškození identifikátoru
jako "jen formátování"). Test invertován. 4 stale próza místa opravena
(3 "multiset"→"sekvence", 1 rozporný bullet o vytváření zálohy).

Soubory: round-14-codex.md, round-14-claude.md.


## Kolo 15

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 4 NITS).
Claude: CONSENSUS (po aplikaci).

`_snapshot_db` dostala časový limit (30s, přes `progress` callback -
`backup()` sama nemá deadline, mohla by viset neomezeně na zamčené DB).
Obnova ze zálohy teď maže případné `-wal`/`-shm` sidecary před
`os.replace` (obrana proti budoucí, ne dnešní, změně journal módu).
Chybová tabulka "jen fluency → přijato" opravena - byla fakticky
nepravdivá (action závisí na severity, ne type; kritický fluency nález
se odmítá). Vedlejší nález: sqlite3.backup() (kolo 14) nekopíruje bajt
po bajtu, "bytově identický" test claim byl nechtěně rozbitý -
přepsáno na logickou rovnocennost. critic.review() docstring rozšířen
o polish-kontext (jiný výsledek stejné výjimky než u run).

PAUZA na žádost uživatele - vypíná codex pluginy kvůli opakovaným
zaseknutím startu (context7 už vypnutý, hang se opakoval i po tom -
podezření na jiné pluginy s network/auth handshake při startu:
google-drive, github, chrome, computer-use).

Soubory: round-15-codex.md, round-15-claude.md.


## Kolo 16

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci; 1 IMPORTANT přijato jen částečně -
jádro ano, plný rozsah "testovaná/zamykaná příkazová obálka pro obnovu"
odmítnuto jako disproporční, přidán bullet do "Mimo rozsah").

`_snapshot_db` dostala `pages=100` - výchozí `pages=-1` znamenal, že
kolo-15 deadline byl fakticky nefunkční (progress callback by se zavolal
až PO dokončení celé kopie, ne uprostřed). `_polish_rejected` teď
srovnává POČTY výskytů konkordančních klíčů (Counter), ne jen jejich
přítomnost - opakovaný pre-existující problém na dalším místě už
neprojde jako "nic nového". Obnova ze zálohy: sidecar soubory (`-wal`/
`-shm`/`-journal`) se mažou AŽ PO úspěšném `os.replace`, ne před ním
(dřívější pořadí otvíralo okno pro poškození aktuální DB při pádu
uprostřed). `_paragraph_count` teď normalizuje CRLF a whitespace-only
prázdné řádky (levná oprava, teoretické riziko).

Poznámka: hang codexu se opakoval i po vypnutí pluginů - pravděpodobný
viník: samostatná `[mcp_servers.*]` sekce v config.toml (magic - npx
bez timeoutu, openaiDeveloperDocs - vzdálený server bez timeoutu), ne
`[plugins.*]`. Uživatel restartoval codex, kolo 16 pak proběhlo čistě.

Soubory: round-16-codex.md, round-16-claude.md.


## Kolo 17

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 3 NITS).
Claude: CONSENSUS (po aplikaci).

NEJDŮLEŽITĚJŠÍ nález celého procesu: `--ignore-user-config` (ověřeno
přímo `codex exec --help`) - `-C work_dir` izoluje jen pracovní adresář,
NE uživatelův globální `~/.codex/config.toml` (MCP servery/pluginy). To
přímo vysvětluje VŠECHNY hangy tohohle plan-consensus procesu (context7,
magic MCP - oba v globálním configu) - a bez týhle vlajky by `polish`
V PRODUKCI zdědilo STEJNÉ riziko při každém spuštění. Přidáno do
produkčního argv `stylist.polish()`, testu i manuálního checklistu.
Dál: obnova ze zálohy dostala zdokumentované zbývající riziko (crash
okno po os.replace) + druhý integrity_check jako levná obrana;
`config.STYLIST_TIMEOUT_SECONDS`/`STYLIST_MAX_CHARS` přidány pro dlouhé
kapitoly (rychlé odmítnutí místo čekání na jistý timeout); oprava
fakticky nepravdivé prózy - guide_block dostává translator, NE kritik
(ověřeno přímo v src/pipeline.py).

Poznámka: od teď budu i pro VLASTNÍ review-loop volání používat
--ignore-user-config, mělo by to konečně vyřešit opakované hangy.

Soubory: round-17-codex.md, round-17-claude.md.


## Kolo 18

Codex: CHANGES_NEEDED (0 BLOCKING, 4 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci).

Dva mimořádně hodnotné nálezy: (1) kolo-16 Counter fix v _polish_
rejected řešil scénář ("1× → 2×" duplicitní konkordanční klíč), co je
prokazatelně STRUKTURÁLNĚ nedosažitelný - src/concordance.py sama
dedupuje každý typ nálezu (leak/omission/inconsistency) na úrovni
jednoho volání. Ověřeno přímým čtením zdroje. Vráceno na jednodušší
množinové srovnání + integrační test s REÁLNÝM check_chapter(). (2)
Bezpečnostní otázka "čte read-only sandbox soubory mimo -C?" (otevřená
od kola 17) VYŘEŠENA živým testem přímo v téhle relaci - ANO, čte
(Get-Content na souboru mimo pracovní adresář uspěl, 93ms). Riziko
prompt injection z textu knihy exfiltrující citlivá data je teď
POTVRZENÉ, ne teoretické - zdokumentováno, přidán povinný canary test
do Manuální ověření, plná OS/kontejnerová izolace vědomě mimo rozsah
(infrastrukturní rozhodnutí pro uživatele/vlastníka projektu).

Dál opraveny dva testy, co by po kole 17 (STYLIST_MAX_CHARS guard) tiše
přestaly testovat to, co měly (dlouhý-stdin test, pages=100 timeout
test).

Soubory: round-18-codex.md, round-18-claude.md.


## Kolo 19

Codex: CHANGES_NEEDED (1 BLOCKING, 2 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci).

Codex ESKALOVAL kolo-18 bezpečnostní nález na BLOCKING - agentní `codex
exec` má ověřeně neomezené čtení celého disku, prompt injection z textu
knihy exfiltruje citlivá data DŘÍV, než guardraily proběhnou; samotná
dokumentace + canary test nestačí. UŽIVATEL ROZHODL (AskUserQuestion):
varianta 1 - povinný opt-in `config.STYLIST_ACCEPT_FS_RISK = True`
(default `False`), `_cmd_polish` bez něj rovnou odmítne s hláškou. Nová
spec sekce "Bezpečnostní rozhodnutí (kolo 19)" dokumentuje ověřený
nález, rozhodnutí i migrační cestu na variantu 2 (neagentní OpenAI API
bez nástrojů) / 3 (OS/kontejner) - odložitelné, protože celé riziko je
uvnitř `stylist.polish()`, zbytek systému provider-agnostický.

Dál: `_codex_argv` helper zavedený jako JEDINÉ místo skládání argv
(dřív 3 místa - polish inline, argv test, canary checklist - canary
neměl `--ignore-user-config`). Spy test na `pages=100` přepsán na proxy
connection z monkeypatchnutého `main.sqlite3.connect` (`sqlite3.
Connection` je immutable C typ, jeho metody nejdou monkeypatchnout).

Soubory: round-19-codex.md, round-19-claude.md.


## Kolo 20

Codex: CHANGES_NEEDED (1 BLOCKING, 3 IMPORTANT, 4 NITS).
Claude: CONSENSUS (po aplikaci).

Dva nálezy odhalily chyby v dřívějším Claudově uvažování:
(1) BLOCKING - kolo-19 opt-in gate (STYLIST_ACCEPT_FS_RISK) byl jen v
`_cmd_polish` CLI obálce; přímé volání veřejné `stylist.polish()` ho
obešlo. Gate přesunut PŘÍMO do `polish()` (raise StylistError), CLI si
nechává jen časnou hlášku. Test modul dostal autouse fixture.
(2) IMPORTANT - kolo-18 reverze `Counter` → množina v `_polish_rejected`
byla založená na neúplné analýze. `check_chapter()` dedup znamená, že
scénář "PŮVODNÍ CZ má 1 leak `White Council`, stylista přepíše další
správný výskyt taky na `White Council`" dá PŘED i PO STEJNÝ jediný klíč
- ani množina ani Counter-nad-findings to nezachytí. Přidána DRUHÁ
kontrola: počítá výskyt `actual` povrchu v `cz_before` vs `cz_after` u
pre-existujících leak/inconsistency nálezů. `_polish_rejected` teď bere
i texty.

Dál: argv test odtautologizován (kolo 19 přehnal DRY - `expected` se
skládal stejnou `_codex_argv` jako produkce; vrácen hardcoded seznam,
`_codex_argv` helper zůstává pro produkci). `rendered_terms` forwarduje
JEN `source == "rendered"` (dřív i `detected`, co se ukládaly s falešnou
proveniencí). Skutečně stale `shutil.copy2` komentář opraven.

Soubory: round-20-codex.md, round-20-claude.md.


## Kolo 21

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci).

Všechny 3 IMPORTANT navazují na kolo-20 opravy: (1) `_polish_rejected`
kolo-20 `str.count(surface)` neodpovídá pravidlům konkordance
(case-sensitive, nezná skloňování) - přepsáno na `concordance.find_form_
occurrences` (stemuje + lowercasuje obě strany stejně); (2) long-input
test měl `_fake_codex`, co stdin vůbec nečetl - přepsán na fake, co CZ
text ze stdinu vytáhne a vrátí, test ověří délku; (3) chybová tabulka
"stejný nález → přijato" po kolo-20 rozdělena na dva řádky (stejný/nižší
počet výskytů = přijato, víc = zahozeno). NITs: docstring nadpis/opt-in
odstavec dotažené na kolo 20, směrový odkaz "výš"→"níže".

Soubory: round-21-codex.md, round-21-claude.md.


## Kolo 22

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 4 NITS).
Claude: CONSENSUS (po aplikaci; 1 IMPORTANT přijat jen z poloviny).

(1) `_polish_rejected` kolo-21 počítal jen `actual` povrch termínu -
nový leak JINÉHO aliasu (`actual`=`leaked[0]` beze změny) by prošel.
Rozšířeno na VŠECHNY zakázané EN povrchy termínu (canonical + aliasy),
`_polish_rejected` bere i `glossary_rows`. Druhá půlka Codexova návrhu
(pokles počtu SCHVÁLENÝCH CZ forem → odmítnout) VĚDOMĚ NEPŘIJATA -
pokles je nejednoznačný (stylista legitimně sloučí věty s opakovaným
termínem), false-reject cena vyšší než úzká zbytková skulina.
(2) `stylist.polish()` veřejné API tiše obcházelo konfigurační
invarianty: `codex_cmd=[]` → produkční `["codex"]` (nebezpečné po
opt-inu), `codex_model=None` → bez povinného modelu, `timeout=180`
natvrdo → obešel STYLIST_TIMEOUT_SECONDS. Všechny 3 teď vynucené PŘÍMO
v `polish()` (None vs [] rozlišeno, prázdný cmd/model = StylistError,
timeout None → config). Autouse fixture nastavuje i CODEX_MODEL.

NITs: preflight próza, sidecar úklid "bezpečnostně nutný" (ne
kosmetický), chybová tabulka omezuje multiplicitu na leak/inconsistency.

Soubory: round-22-codex.md, round-22-claude.md.


## Kolo 23

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci).

Oba IMPORTANT navazují na kolo-22 změny: (1) `codex_model.strip()` se
jen validoval, ne přiřazoval - whitespace-padded model by šel do `-m` s
mezerami; opraveno na přiřazení. (2) kolo-22 `test_polish_config_
invariants` v docstringu tvrdil, že testuje timeout, ale assertci neměl
- přidán `test_polish_uses_config_timeout_and_strips_model` (spy na
`subprocess.Popen.communicate` - regulární Python metoda, na rozdíl od
`sqlite3.Connection` monkeypatchnutelná).

NITs: `--ignore-rules` přidán do `_CODEX_STATIC_FLAGS` (samostatný flag
od `--ignore-user-config`, ověřeno `codex exec --help` - nepokrývá
execpolicy `.rules`; stylista nespouští shell příkazy, nejrestriktivnější
execpolicy je ideální). `polish` doplněn do modulového docstringu
`main.py` ("Fáze běhu:").

Soubory: round-23-codex.md, round-23-claude.md.


## Kolo 24

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci).

IMPORTANT: `_snapshot_db` deadline neměl skutečný test - pages=100 test
ověřuje jen předání argumentu, ne že callback přeruší nebo že se
`TimeoutError` propaguje. Přidán test s proxy `.backup()` (zavolá
`progress` callback) + monkeypatchnutý `main.time.monotonic` za deadline
→ očekává `TimeoutError` z přímého `main._snapshot_db(...)`.

NITs (stale próza): `_codex_argv` docstring + kolo-19 bullet tvrdily,
že argv test `_codex_argv` volá - od kola 20 ho VĚDOMĚ nevolá (ruční
oracle). "Mimo rozsah" backup próza: "nejvýš jedna záloha za běh, jen
před prvním PŘIJATÝM zápisem".

Soubory: round-24-codex.md, round-24-claude.md.


## Kolo 25

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 2 NITS).
Claude: CONSENSUS (po aplikaci).

IMPORTANT: kolo-23 přidání `--ignore-rules` do `_CODEX_STATIC_FLAGS` mělo
obrácené bezpečnostní zdůvodnění. `codex exec --help`: `--ignore-rules` =
"Do not load user or project execpolicy .rules files" - pravidla
ODSTRAŇUJE. Restriktivní `forbidden`/`prompt` v uživatelových `.rules` by
mohla omezit, jaké příkazy Codex spustí → `--ignore-rules` útočnou plochu
ROZŠIŘUJE. A tvrzení "stylista nespouští shell příkazy" je vyvráceno
canary testem kola 18 (Codex spustil `Get-Content`). `--ignore-rules`
odstraněn z argv, argv testu i canary checklistu. `--ignore-user-config`
(hang fix, kolo 17) zůstává - SAMOSTATNÝ flag, execpolicy `.rules`
neřeší, hang byl z MCP/plugin loadingu.

NITs: docstring nadpis "kola 1-6 a 17-20" → "1-6, 17-20 a 25";
rozhodnutí-bullet u timeout testu ukazovalo na špatný test.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-25-codex.md, round-25-claude.md.


## Kolo 26

Codex: CONSENSUS (0 BLOCKING, 0 IMPORTANT, 3 NITS).
Claude: CONSENSUS.

NITs (vše prozaické, opraveno):
- "viz canary výš" (ř. 2080-2083) → POVINNÝ CANARY TEST je NÍŽ.
- Preflight próza tvrdila, že bez preflightu běh skončí `status="ok"` -
  zastaralé, spec jinde (kolo 5/6) říká `fatal` když všechny kapitoly
  `failed`. Přeformulováno na "N hlášek + fatal, drahá cesta ke
  správnému stavu místo jedné jasné hlášky".
- Próza "výstup prochází STEJNOU kontrolou jako originál" (ř. 386-390) -
  číselný guard + odstavce + CZ-před/CZ-po meaning check jsou DODATEČNÉ.
  Přeformulováno na "STEJNÝMI (konkordance + kritik) PLUS DODATEČNÝMI".

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-26-codex.md, round-26-claude.md.

=== SHODA (CONSENSUS) po 26 kolech ===
Oba recenzenti vydali CONSENSUS ve stejném kole. Plán je hotov ke
spuštění. Viz final-verdict.md.

## Post-consensus doplnění (kolo 27, mimo smyčku)

Po dosažení konsensu vlastník projektu vznesl 2 požadavky. Zapracováno
přímo do specu, plan-consensus smyčka to nepřezkoumala:

1. **Pozorovatelnost zamítnutí.** `_rejection_reasons` vrací seznam
   nálezů (ne bool; `_polish_rejected` = tenký bool wrapper, staré testy
   platí). Per-kapitola výpis vyjmenuje důvody. `_write_polish_report`
   zapíše na konci běhu JSON (`polish-reports/run-<rid>-<čas>.json`):
   per kapitola outcome, u rejected/failed plné nálezy, u rejected i
   zamítnutý text od Codexu. Bez zásahu do DB schématu, best-effort.
2. **Granulární přijetí / opravná smyčka:** zváženo, odloženo za v1
   (Codex nevrací rozlišitelné zásahy; opravná smyčka = další placené
   volání bez dat o úspěšnosti; halucinace se surgicky neřeší). v1 =
   all-or-nothing + report jako měřicí přístroj.

Změny jsou aditivní, nezasahují do bezpečnostního jádra. Detaily v spec
sekci "Kolo 27 - post-consensus doplnění".

## Kolo 27 (review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 5 IMPORTANT, 1 NIT).
Claude: CHANGES_NEEDED (po aplikaci).

Všech 5 IMPORTANT bylo ve vlastním kolo-27 dodatku, všechny platné:
1. Report ukládá zamítnutý text = NOVÁ PERZISTENCE potenciálně
   exfiltrovaného obsahu (dřív se zahodil). "Žádná nová expozice" bylo
   nepravdivé. → přiznáno, `config.STYLIST_REPORT_REJECTED_TEXT` opt-out
   (default True), stale próza o dočasnosti výstupu opravena, doplněna
   sekce "Bezpečnostní rozhodnutí (kolo 19)".
2. Report vznikal jen po normálním doběhnutí smyčky - `FatalRunError`/
   `KeyboardInterrupt` ho zahodil i s už nasbíranými zamítnutými texty.
   → `report=[]` před `try`, `_write_polish_report` z `finally`,
   hlavička + `run_status`/`incomplete`.
3. Best-effort chytal jen `OSError` - `json.dump` `TypeError` by unikl,
   shodil běh na fatal. → `except Exception` + `.tmp` cleanup.
4. Próza "u failed plné nálezy" nepravdivá - `failed` je PŘED
   kontrolami, žádné findings. → kontrakt sjednocen: rejected =
   reasons/findings/styled; failed = jen error.
5. Report bez `codex_model`/`schema_version`/timestamp - nejde porovnat
   reject rate mezi konfiguracemi (Codex volání není v `llm_calls`).
   → doplněno.

NIT: "viz Mimo rozsah" odkaz → přesměrován na rozhodovací bod.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-27-codex.md, round-27-claude.md.

## Kolo 28 (2. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 6 IMPORTANT).
Claude: CHANGES_NEEDED (po aplikaci).

6 IMPORTANT v report subsystému (dodatek je reálný subsystém, ne
"aditivní próza"):
1. `STYLIST_REPORT_REJECTED_TEXT=False` netěsnil - volná pole nálezů
   (`issue`, `cz_excerpt`) + konzolový výpis pořád nesly text. →
   `False` teď ukládá/tiskne JEN `reason_types`.
2. `incomplete = run_status != "ok"` chybné - all-failed dávka doběhla
   celá. → `batch_completed` + `planned_count`/`attempted_count`
   samostatně.
3. "report vždy po Fatal" neplatilo pro pád před 1. kapitolou
   (`if not report: return` zrušeno) ani pro fatální commit aktuální
   kapitoly (→ `outcome=="fatal"` záznam + `run_error`).
4. "failed = žádné findings" nepravdivé pro pád uprostřed kontrol. →
   kontrakt: `failed` vždy jen `error`, bez ohledu na fázi.
5. Duplicitní důvod (nový klíč + syntetický nárůst) se agregoval
   dvakrát. → cílený skip v `_rejection_reasons`.
6. Report psán PŘED `finish_run` - `finalization_error` nešel
   zaznamenat. → přehozeno.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-28-codex.md, round-28-claude.md.

## Kolo 29 (3. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 3 NITS). Konverguje (5→6→2).
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT:
1. `FatalRunError` z kritika / cost guardu padne PŘED commitem →
   `_polish_one_chapter` svůj `fatal` záznam (jen commit-větev) nepřidá →
   `attempted_count` kapitolu chybně počítá jako nezpracovanou. Oprava:
   `_cmd_polish`'s `except FatalRunError` záznam doplní se
   `stage=="pre-commit"` (dedup proti commit-větvi).
2. `STYLIST_REPORT_REJECTED_TEXT=False` netěsnil přes Codex STDERR -
   `polish()` ho dával do `StylistError` (`stderr[:500]`) → konzole +
   `failed.error` v reportu. stderr je jediný Codexem-řízený text v
   chybové cestě `polish()`. Oprava: raw stderr se připojí jen za
   `STYLIST_REPORT_REJECTED_TEXT=True` (u zdroje).

NITs: stale `status="ok"` u preflight bulletu (→ `fatal`); "deduplikovaný
seznam" nepřesné (dedup jen konkordanční překryv); test scénář prázdného
reportu má cílit `_client_factory`, ne `_polish_one_chapter`.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-29-codex.md, round-29-claude.md.

## Kolo 30 (4. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 3 NITS). Konverguje: 5→6→2→1.
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT: `KeyboardInterrupt` (Ctrl+C) během zpracování kapitoly nepřidal
žádný záznam → `attempted_count` kapitolu počítá jako nezpracovanou
(stejná třída bugu jako kolo-29 `FatalRunError`). `KeyboardInterrupt`
není `Exception`, propadne oběma in-loop `except`. Oprava: in-loop
`except KeyboardInterrupt` přidá `outcome=="interrupted"` +
`stage=="processing"`, pak re-raise. `_REPORT_OUTCOMES` rozšířeno.

NITs: (1) report re-readoval `config.CODEX_MODEL` místo skutečně použité
`model` proměnné → `codex_model` kwarg, `_cmd_polish` předá `model`;
(2) prozaický výčet hlavičky reportu vynechával `run_id`/`generated_at`/
`summary` → doplněno; (3) "zamítnutá/selhaná stylizace nic v DB nemění"
nepřesné (`runs`/`llm_calls` vzniknou) → "nemění stav/text kapitoly".

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-30-codex.md, round-30-claude.md.

## Kolo 31 (5. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 3 NITS).
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT:
1. `STYLIST_REPORT_REJECTED_TEXT=True` byl nebezpečný DEFAULT. "Je to
   uvnitř už přijatého FS rizika" NEOBSTÁL: `STYLIST_ACCEPT_FS_RISK` =
   "agent smí číst disk během běhu", NE "exfiltrovaný obsah se smí TRVALE
   uložit do souboru" (navíc `polish-reports/` je vedle repa v
   synchronizované složce - Nextcloud - takže by to teklo dál). Oprava:
   default `False`, plný text = samostatný explicitní opt-in.
   POZN: vlastník projektu si `True` původně přál - teď je to informovaná
   volba (default bezpečný, plný text jedním řádkem).
2. Dedup v `_rejection_reasons` (kolo 29/30) byl na úrovni celého
   `(type, term_id)`. Nový chybný povrch B (nový klíč) by zamaskoval, že
   SOUČASNĚ narostl výskyt povrchu A → report ztratí jednu z příčin.
   Oprava: dedup na `_finding_key` (`(type, term_id, actual)`), per-povrch.

NITs: úvodní shrnutí "zahodí se" (→ "nepřijme se; report jen za
opt-inem"); próza "vnější KeyboardInterrupt handler stačí sám o sobě"
(kolo 30 to vyvrátilo pro report); nadpis "Kolo 27-29" → "Kolo 27+".

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-31-codex.md, round-31-claude.md.

## Kolo 32 (6. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 3 NITS). Obojí fallout z kola 31.
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT:
1. `STYLIST_REPORT_REJECTED_TEXT` se testoval obecnou truthiness - `1`/
   `"False"`/`None` by aktivovaly plný detail (perzistenci potenciálně
   exfiltrovaného textu), přestože kontrakt žádá explicitní `True`.
   Oprava: `is True` na obou kódových místech (`polish()` stderr větev,
   `_polish_one_chapter`). Stejný vzor jako `STYLIST_ACCEPT_FS_RISK is
   not True`.
2. `_write_polish_report` docstring pořád opakoval "uvnitř přijatého FS
   rizika" - rationale výslovně odmítnutý v kole 31. Přepsáno na
   "samostatné riziko, samostatný opt-in".

NITs: komentář "za opt-outem" → "opt-in" (default `False`); sekce
"Kolo 27+" pořád popisovala dedup přes `(type, term_id)` → `_finding_
key`; chybová tabulka vynechávala `run_id` v hlavičce reportu.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-32-codex.md, round-32-claude.md.

## Kolo 33 (7. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 2 NITS).
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT:
1. Tvrzení "stderr je JEDINÝ Codexem-řízený text v chybové cestě
   polish()" bylo nepravdivé - číselný guard vloží celý `after_nums`
   (čísla ze STYLIZOVANÉHO textu) do `StylistError` → konzole +
   `failed.error` i za `False`. Prompt injection by přes to
   exfiltrovala číselný obsah. Oprava: hodnoty číselných sekvencí jen
   za `STYLIST_REPORT_REJECTED_TEXT is True`, jinak obecná hláška.
2. Kolo-30 `KeyboardInterrupt` fix nezaručoval JEDEN pravdivý záznam:
   interrupt po commitu ALE před `report.append({polished})` → jen
   `interrupted` (DB má přijatou stylizaci); interrupt po appendu → DVA
   záznamy → `attempted_count` přeteče. Oprava: `polished` append HNED
   po commitu (před `print`) + in-loop `except KeyboardInterrupt` dedup
   podle `idx`.

NITs: próza `interrupted` = `stage`+`error` (kód má jen `stage`);
config komentář "žádný volný text" moc obecný.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-33-codex.md, round-33-claude.md.

## Kolo 34 (8. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 1 NIT). STRUKTURNÍ přepis.
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT:
1. Redakční hranice `STYLIST_REPORT_REJECTED_TEXT=False` pořád netěsnila
   - i počet odstavců / poměr délky nesou hodnoty ze `styled`, obecný
   `except` ukládal libovolné `str(e)` do `failed.error`. Oprava: jeden
   helper `stylist._redact_detail(detail)` (`detail` jen za `is True`,
   jinak `_REDACTED`), aplikovaný na VŠECHNY Codexem-odvozené hodnoty v
   chybových hláškách.
2+3. Invariant "1 report záznam / kapitolu" byl křehký - držel jen
   dedupem a padal na výjimce z `print()` po commitu (`BrokenPipeError`
   → dva záznamy) a na commit-then-interrupt okně. Oprava (Codexův
   návrh): `_polish_one_chapter` `report` NEMUTUJE, vrací jeden `dict`;
   `_cmd_polish` appendne přesně jednou za iteraci (invariant
   STRUKTURNÍ). `KeyboardInterrupt` handler zjistí STAV DB (marker
   `_already_styled`) a zapíše `polished`/`interrupted` podle
   skutečnosti. `fatal` `stage` zrušen (hláška rozliší commit vs guard).

NIT: `generated_at` timezone-aware ISO 8601 (`import datetime as _dt`),
filename + `os.urandom(4).hex()` suffix.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-34-codex.md, round-34-claude.md.

## Kolo 35 (9. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 1 NIT). Fallout z kola 34.
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT:
1. Commit-detekce v `KeyboardInterrupt` handleru přes `_already_styled`
   je špatná pro `--force` (marker z DŘÍVĚJŠÍHO běhu). Oprava: detekce
   přes `state.get_chapter(...)["translated_text"] != c["translated_
   text"]`.
2. `print("...vylepšeno.")` po commitu může hodit → generic `except` →
   `failed`/`fatal` navzdory zapsané stylizaci. Oprava: helper `_say()`
   = `try: print except Exception: pass` pro VŠECHNY per-kapitolové
   výpisy.
3. `_redact_detail(str(fe))` v in-loop handleru redigoval, ale top-level
   `run_error`/`print(e)` uložily/vytiskly STEJNOU výjimku nezměněnou.
   Oprava: `FatalRunError` z commitu redigovaná U ZDROJE
   (`_polish_one_chapter`), pak `str(fe)` bezpečné všude.

NIT: test próza "stderr Codexu potlačen" → aktuální `_REDACTED` string.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-35-codex.md, round-35-claude.md.

## Kolo 36 (10. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, prose-vs-code sweep).
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT (oba = dokončení kolo-35 `_say` změny):
1. `_backup_db_once` má `print` po `os.replace` PŘED `done = True` →
   `BrokenPipeError` udělá z úspěšné promoce `FatalRunError`. Oprava:
   `done = True` HNED po `os.replace`, pak `_say`.
2. `_write_polish_report` úspěchový `print` + jeho `except`-warning +
   `finish_run`-failure warning můžou vyhodit a uniknout z `finally`.
   Oprava: všechny `_say`. + VŠECHNY zbylé raw `print` v main.py runtime
   kódu (preflight, výběr kapitol, "všechno selhalo") → `_say`.

Stale próza: commit-detekce marker→`translated_text`; `print("...
vylepšeno.")` → obecně; redakce "in-loop"→"u zdroje"; filename hex suffix.

ast.parse sweep: 9 bloků, 0 chyb. Jediný raw `print` je uvnitř `_say`.
Soubory: round-36-codex.md, round-36-claude.md.

## Kolo 37 (11. review kola-27 dodatku)

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 5 prose NITs). Klesá 3→2→1.
Claude: CHANGES_NEEDED (po aplikaci).

IMPORTANT: `FatalRunError` z KONTROL (kritik / meaning-check) nebyl
redigovaný. Kolo-35 tvrzení "z kritika/cost guardu Codexův obsah nenese"
NEPLATILO - `_run_critic`/`check_meaning_preserved` volají Anthropic
klienta S `styled`, klientův `FatalRunError` (400, cost guard) může
pojmout část requestu = obsah `styled`. Oprava: `_polish_one_chapter`
obalí `try/except FatalRunError` kolem kontrolní sekce, re-raise s
hláškou redigovanou u zdroje (`_redact_detail`). Teď VŠECHNY
`FatalRunError` nesoucí `styled` jsou redigované u zdroje.

NITs: KeyboardInterrupt prose "vždy interrupted" → podle DB; 3× stale
marker→`translated_text`; filename bez hex suffixu; config tag.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-37-codex.md, round-37-claude.md.

## Kolo 38 (12. review kola-27 dodatku)

Codex: CONSENSUS (0 BLOCKING, 0 IMPORTANT, 3 prose NITs).
Claude: CONSENSUS.

NITs (vše prozaické, opraveno):
- komentář u top-level `except FatalRunError` pořád tvrdil "cost guard
  běží před/mimo stylizaci" - kolo 37 to vyvrátilo → "redakce u zdroje".
- "jediné místo pro `report.append`" → "PRÁVĚ JEDNOU ZA ITERACI" (3
  větve, ale na každé cestě jedna).
- test bullet s "patchnutým `report`" na starou signaturu → test
  návratového `dict` + `len(report) == N` nad `_cmd_polish`.

ast.parse sweep: 9 bloků, 0 chyb.
Soubory: round-38-codex.md, round-38-claude.md.

=== SHODA (CONSENSUS) na kolo-27+ dodatku po 12 review kolech ===
Oba recenzenti CONSENSUS ve stejném kole (38). Report subsystém pro
pozorovatelnost zamítnutí je hotový. Aktualizace final-verdict.md.
