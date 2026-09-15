# Plan-consensus (implementační plán) - discussion log

Plán: docs/superpowers/plans/2026-09-14-batch-polish-reader-workflow.md
Spec: docs/superpowers/specs/2026-09-14-batch-polish-reader-workflow-design.md
Start: 2026-09-14T11:49:29Z
Max kol: 30

## Round 1 - 2026-09-14T12:something (viz timestamp souborů)

Codex: CHANGES_NEEDED (5 BLOCKING, 12 IMPORTANT, 2 NITS)
Claude: CHANGES_NEEDED (1 vlastní nález nad rámec Codexu, souhlas se
VŠEMI Codexovými body kromě jednoho NIT rozhodnutého jako dokumentace,
ne chování)

Opraveno v plánu: chybějící `_snapshot_db` volání (Task 5), rozšíření
`_VALID_HISTORY_SOURCES` o "polish-batch" (Task 5), CAS + `refresh_lock`
v dávkové smyčce (Task 5), zdvojené nálezy notes+historie - sjednoceno
na notes jako jediný zdroj (Task 5/7/8), `--force`/`_already_styled`
marker přidán do sdíleného commitu (Task 5), `app.state.draft_path`
explicitně smazán (Task 13), test fixtures přepsány na skutečné
(`_polish_db`/`_polish_env`, Tasky 3/4/5/6), `POLISH_HISTORY_PATH`
přesměrování v `_polish_env` (Task 5), config reload leak (Task 1),
jednorázová migrace id/resolved (Task 13) + revert assign_ids (Task 13),
`rendered_terms` ze STARŠÍ historie místo zúžené živé DB (Task 9),
server-side `resolved` vyhrává nad zastaralým save (Task 9), zjednodušený
`toggleResolved` (jen scope=notes, správný error handling) (Task 14),
regenerace: `interactive=False` + `require_lock()` bez `write_lock`,
test monkeypatchuje `config.DB_PATH` (Task 10), rozšířené `_EDITABLE_
STATUSES` pro save i regenerate (Task 9/10), export obalený `write_lock`
+ `require_lock()`, zobrazení `skipped` v UI (Task 12/14), validace
jednotlivých nálezů (Task 9), zamčení editoru během regenerace/uložení
(Task 14), oprava `tally['drafted']` už v Tasku 3 (ne až v 5).

Soubory: round-1-codex.md, round-1-claude.md.

## Round 2

Codex: CHANGES_NEEDED (3 BLOCKING, 6 IMPORTANT, 3 NITS)
Claude: CHANGES_NEEDED (1 vlastní nález, souhlas se všemi Codexovými
BLOCKING/NIT body, souhlas se 7/8 IMPORTANT body, nesouhlas na 1 -
Task 10 status="ok" je záměrná existující konvence z _cmd_polish, ne bug)

Opraveno: historie se validuje PŘED DB commitem v _commit_polish_result
(nová HistoryWriteFailedAfterCommit výjimka pro post-commit selhání),
editor se po uložení už neuzamkne navždy (loadChapter vždy odemyká),
_polish_env teď získává skutečný zámek (refresh_lock v testech fungoval
by jinak vždy selhal), toggleResolved rozlišuje persistované/regenerované
nálezy (PERSISTED_IDS), resolved-race oprava rozšířena na OBA směry
(server vždy vyhrává pro známé id), lehká zápisová větev pro
findings/status beze změny textu, rendered_terms sjednoceno do jedné
_preferred_rendered_terms volané interně (dřív dávka/save měly různá
pravidla), EDITOR_BUSY flag + try/finally v regenerate/save/revert
handlerech (dřív možné souběžné přepsání rozepsaného textu), Task 13
teď explicitně jmenuje 4 portované ochranné testy místo tichého mazání,
Task 10's finish_run zabalen proti přebití response, validace nálezů
rozšířena o source/type/issue typy + duplicitní/prázdná id, oprava
stylist->main.stylist typo v testu, přesun DB snapshotu před create_run
+ úklid do finally, commit krok doplněn o polish_store.py.

Soubory: round-2-codex.md, round-2-claude.md.

## Round 3

Codex: CHANGES_NEEDED (2 BLOCKING, 6 IMPORTANT, 2 NITS)
Claude: CHANGES_NEEDED (souhlas se všemi body, žádný nesouhlas)

Opraveno: btn-save finally už nemaže rozepsanou práci po chybě (reload
jen po úspěchu), lehká zápisová větev (text beze změny) přepsána na
merge-podle-id místo přepisu celého notes pole (opravuje ZTRÁTU
_stylist_marker/--force I race na sadě nálezů najednou), no-op podmínka
počítá skutečný výsledek merge místo "not raw_findings" heuristiky,
lehká větev teď má _backup_db_once + řízenou 500 chybu, assign_ids
opraveno pro explicitní id:null (setdefault ho nechávalo být),
EDITOR_BUSY teď zamyká i checkboxy nálezů, loadChapter/lockEditor
null-safe + try/catch + počáteční zamčený stav před prvním načtením,
renderHistory vrácen stale/reason warning + .stale-msg CSS (chybělo
úplně), _polish_one_chapter's "půjde k ručnímu review" hlášky opraveny
(Task 3), Task 9 interface popis no-op zpřesněn. Vlastní nález: 2x
poškozený opakující se text ve vlastních komentářích, opraveno při psaní.

Soubory: round-3-codex.md, round-3-claude.md.

## Round 4 - PŘERUŠENO

Codex exec selhal: "You've hit your usage limit... try again at 6:50 PM"
(codex účet, ne tenhle nástroj). round-4-codex.md nevznikl (žádná
finální zpráva). Zastaveno podle plan-consensus skill selhání-protokolu
- nezkoušet slepě znovu, čekat na uživatele.

## Round 4 (po přerušení kvůli Codex usage limitu, pokračováno na žádost uživatele)

Codex: CHANGES_NEEDED (1 BLOCKING, 6 IMPORTANT, 2 NITS)
Claude: CHANGES_NEEDED (souhlas se 5/7 BLOCKING+IMPORTANT body, nesouhlas
se 2 IMPORTANT - rendered_terms sjednocení analýza/zápis je architektonicky
špatný nápad; Task 9 outer try/except je disproporční čtvrtá vrstva
oprav stejného souboru pro velmi vzácný edge case)

Opraveno: sdílená _merge_findings_by_id funkce nahrazuje DVĚ nekonzistentní
implementace (lehká větev merge, normální větev plné přepsání) - obě teď
merge, žádná už nemaže cizí zápis. is_marker + render_findings_html
defenzivní vůči neočekávaným typům z producentů nálezů (kritik/concordance
nejsou validovaní jako klientský vstup). Task 5's _snapshot_db teď má
vlastní try/except (main() zachytává JEN LockError, ne obecnou chybu -
vlastní dřívější tvrzení bylo nepravdivé). Task 13 migrace: zámek +
záloha + tolerance k ne-dict položkám. Task 11 notes-scope zápis dostal
stejný try/except jako history-scope vedle něj. Task 10 client_factory
konstrukce přesunuta dovnitř try, aby run vždy dostal finish_run. Task 14
toggleResolved dostal PENDING_RESOLVE_IDS (síťová chyba/souběžné kliky).
loadChapter/lockEditor sjednoceno na jedno noEdit pravidlo (dřív jen
btn-orig/codex byly null-safe). Dva vlastní nálezy: opraveny 2 vlastní
překlepy v komentářích (cyrilský znak, opakovaný fragment).

Soubory: round-4-codex.md, round-4-claude.md.

## Round 5

Codex: CHANGES_NEEDED (0 BLOCKING poprvé, 5 IMPORTANT, 3 NITS)
Claude: CHANGES_NEEDED (souhlas se všemi body; ZMĚNIL názor na
rendered_terms sjednocení po konkrétním protipříkladu od Codexu -
round-4 nesouhlas byl založen na obecném argumentu, round-5 dal
reprodukovatelný scénář, co ho vyvrátil)

Opraveno: findings.assign_ids normalizuje VŠECHNA string pole (source/
type/issue/severity/cz_excerpt/suggestion) na str - kritik čte issue
přímo z LLM JSON bez typové kontroly, bez tyhle opravy by uživatel po
GET+save cyklu nemohl uložit VŮBEC NIC na kapitole s takovým nálezem.
_polish_one_chapter dostal volitelný rendered_terms parametr, dávka
(Task 5) a regenerace (Task 10) ho počítají jednou a předávají STEJNOU
hodnotu do analýzy i zápisu (dřív mohly nesouhlasit, což mohlo
podhodnotit critical nález na pouhý minor). Task 13 migrace přeuspořádána
- historie se zkouší načíst JAKO PRVNÍ, selhání = čistý stop bez
poloviční migrace (load_history validuje schema PŘED skriptovou
tolerancí, takže ta na poškozenou historii nikdy nedosáhne). Task 10/14
kontrolují translated_text is not None (status='error' ho nezaručuje).
_finding_summary (existující main.py funkce) přepsána na bezpečné
_parse_findings - crashovala na notes='null'/'42'/'[null]', což by
shodilo export CELÉ knihy na jedné špatné kapitole. 2 NIT dokumentační
opravy (merge akumulace, id-invariant).

Soubory: round-5-codex.md, round-5-claude.md.

## Round 6 - PŘERUŠENO (Codex usage limit, delší čekání)

Codex exec selhal podruhé: "try again at Sep 15th, 2026 12:34 AM" (další
den, ne pár hodin jako kolo 4). Round-6-codex.md nevznikl (žádná finální
zpráva), ALE částečný výstup před selháním obsahoval Codexovu vlastní
node.js simulaci `toggleResolved`/`PENDING_RESOLVE_IDS` chování, co
odhalila reálný bug: "f1Disabled: true" po souběžném úspěchu f2 a selhání
f1. Claude ověřil vlastním čtením kódu (ne jen převzal simulaci) -
potvrzen skutečný bug: `checkbox` DOM reference zachycená PŘED prvním
`await` se stane zastaralou/odpojenou, když MEZITÍM jiný souběžný
`toggleResolved` úspěšně doběhne a zavolá `renderFindings()` (přestaví
CELÝ seznam DOM elementů). Zápis do staré `checkbox` reference PO
`await` pak nemá žádný viditelný efekt - aktuálně zobrazený (nový)
checkbox zůstane navždy disabled.

Opraveno (Claude, vlastní nález nad rámec neúplné Codex kritiky):
`toggleResolved` se po `await` už nikdy nedotýká `checkbox` parametru
přímo - vždy jen `finding.resolved` (data) + `renderFindings()` (jediné
místo, co mění viditelný DOM po async operaci).

Zastaveno podle plan-consensus selhání-protokolu - čekání do dalšího
dne je moc dlouhé na blind retry, čeká se na rozhodnutí uživatele.

## Round 6 (dokončeno po druhém pokusu dalšího dne)

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 1 NIT)
Claude: CHANGES_NEEDED (1 vlastní nález nad rámec - toggleResolved
stale-DOM-reference bug, nalezený z NEÚPLNÉHO kola-6 pokusu č.1 výstupu
- Codex tam před selháním stihl vlastní node.js simulaci, co bug
odhalila; Claude ji ověřil čtením kódu, ne převzal na slovo. Souhlas
se všemi 2 Codexovými IMPORTANT + 1 NIT.)

Opraveno: Task 3→Task 4 pořadí - úprava _polish_one_chapter odkazující
na _rendered_terms_for_chapter přesunuta CELÁ do Tasku 4 (kde ta funkce
vzniká), Task 3 už jen vysvětluje a odkazuje dopředu. Task 10's
regenerate test mock rozšířen o rendered_terms kwarg (endpoint ho teď
posílá, starý mock by spadl na TypeError->500). build_findings_report
docstring opraven - dávka notes PŘEPISUJE (ne akumuluje jako editor),
byla chyba tvrdit symetrii. toggleResolved už po await nikdy nesahá na
zachycenou checkbox DOM referenci (mohla se mezitím stát odpojenou přes
souběžný renderFindings() z jiného nálezu) - vždy jen finding.resolved
+ renderFindings().

Soubory: round-6-codex.md, round-6-claude.md.

## Round 7

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 1 NIT)
Claude: CHANGES_NEEDED (souhlas se vším, žádný vlastní nález)

Opraveno: toggleResolved po úspěchu dohledá aktuální finding objekt
podle id v CURRENT_FINDINGS místo mutace zachycené reference (Uložit
nečeká na PENDING_RESOLVE_IDS, může doběhnout dřív a loadChapter()
vymění celé pole za nové objekty - stejná třída bugu jako kolo 6, teď
na datech místo DOM). Task 5 Interfaces popis _commit_polish_result
opraven (rendered_terms parametr chyběl v popisu i po kole 5).

Soubory: round-7-codex.md, round-7-claude.md.

## Round 8

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CONSENSUS (souhlas s Codexem, žádný vlastní nález)

Opraveno: PENDING_RESOLVE_PROMISES (Map id -> Promise) přidán, plněn
v change listeneru checkboxu nálezu. btn-save handler i revertChapter()
teď před vlastním fetchem čekají na doběhnutí všech rozpracovaných
resolve requestů - řeší opačné pořadí ZÁPISŮ na serveru (Save/Revert
vlastní loadChapter() GET mohl na serveru doběhnout PŘED zápisem
resolve, i když klientovi resolve odpověď dorazila dřív; kolo 7 oprava
řešila jen pořadí odpovědí na klientovi, ne pořadí zápisů na serveru).
Třetí kolo v řadě (6, 7, 8) na stejné třídě bugu (stale reference přes
await hranice) ve stejném kódu - Claude verdict poprvé CONSENSUS, čeká
se na kolo 9 zda Codex potvrdí totéž.

Soubory: round-8-codex.md, round-8-claude.md.

## Round 9 - PŘERUŠENO

Codex exec selhal: "You've hit your usage limit... try again at 11:48 AM"
(codex účet, ne tenhle nástroj). round-9-codex.md nevznikl (žádná
finální zpráva). Zastaveno podle plan-consensus skill selhání-protokolu
- nezkoušet slepě znovu, čeká se na uživatele.

## Round 9 (dokončeno po druhém pokusu)

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CONSENSUS (souhlas s Codexem, žádný vlastní nález)

Opraveno: `outcome=="unchanged"` (Codex nenavrhl žádnou úpravu) se dřív
nikam nezapisovalo - `_already_styled` zůstalo `False`, příští `polish`
i bez `--force` by kapitolu znovu (a zbytečně) poslal a zaplatil
Codexu, donekonečna. Přidán `_unchanged_marker` (main.py), `_already_
styled` rozšířeno o `type=="unchanged"`, `_MARKER_TYPES` (Task 2)
rozšířeno, Task 5 Step 8 dostal `elif` větev s lehkým CAS zápisem
markeru (bez historie, bez `_commit_polish_result`), nový test na
druhý běh (přeskočeno) + `--force` (zpracováno znovu). Bug byl
předexistující v main.py, ne vznikl týmhle plánem, ale batch provoz je
scénář, kde se cena znásobí nejvíc - plán ho teď opravuje.

Soubory: round-9-codex.md, round-9-claude.md.

## Round 10

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 2 NIT)
Claude: CONSENSUS (souhlas se vším, žádný vlastní nález)

Opraveno: Task 13 Step 8 migrace přepsána z "python -c" (nefunkční na
Windows/PowerShell pro víceřádkový skript s uvozovkami) na "ulož do
souboru, spusť jako skript". Task 10 regenerate endpoint - `finally`
teď volá `app.state.require_lock()` znovu TĚSNĚ PŘED `finish_run`
(auditní zápis), přeskočí ho, pokud zámek mezitím (během dlouhého
Codex volání) ztratil - existující heartbeat vlákno riziko z větší
části kryje, ale chyběl explicitní re-check před samotným zápisem.
Global Constraints rozšířeny o přesně zúženou výjimku pro VÝHRADNĚ
auditní zápisy (textová kontradikce s Task 10's zdůvodněným odklonem
odstraněna). 2 NIT: špatný počet testů v Task 2 Step 4 (8→11), osiřelý
duplicitní textový fragment v Task 5 Step 8 smazán. Claude verdict
potřetí za sebou CONSENSUS (kola 8, 9, 10).

Soubory: round-10-codex.md, round-10-claude.md.

## Round 11

Codex: CHANGES_NEEDED (1 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas s BLOCKING, ČÁSTEČNÝ nesouhlas s
navrženou opravou u IMPORTANT bodu - zdůvodněno)

Opraveno (BLOCKING): `require_lock()` kontrola v Task 10 regenerate
endpointu pokrývala jen start handleru + `finish_run` (kolo 10), ne
zápisy `llm_calls` UVNITŘ `_polish_one_chapter` (kritik/stylist_check
přes `PipelineLLMClient`). Přidán volitelný `require_lock` parametr do
`PipelineLLMClient`/`_client_factory` (`None` výchozí, CLI `run`/`polish`
beze změny), server ho vyplní `app.state.require_lock`. Nové testy v
`tests/test_pipeline_client.py` + `tests/test_polish_server.py`.

Opraveno (IMPORTANT, částečně): Task 13 Step 8 migrace - chybějící
`try/except` kolem `save_history` (holý traceback při selhání) opraven.
Navržený AUTOMATICKÝ rollback `chapters.notes` ze zálohy ODMÍTNUT -
zdůvodněno: `assign_ids` je aditivní/idempotentní, "notes migrované,
historie ne" není poškozený stav, jen neúplný a bezpečně dokončitelný
opakovaným spuštěním. Skript místo rollbacku vysvětlí situaci a
doporučí re-run. Automatizovaný test na tenhle scénář se nepřidává
(skript mimo test-pokryté zdrojové soubory).

Soubory: round-11-codex.md, round-11-claude.md.

## Round 12

Codex: CHANGES_NEEDED (1 BLOCKING, 2 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas s BLOCKING i oběma IMPORTANT body -
jeden plně, druhý částečně se zpřesněním vlastního dřívějšího tvrzení)

Opraveno (BLOCKING): `PipelineLLMClient.complete()`'s kolo-11 kontrola
ověřovala zámek jen PŘED síťovým voláním, ne těsně PŘED `record_llm_
call` ve `finally` - přidána druhá kontrola tam, při selhání JEN
vynechá audit zápis (nevyhazuje výjimku - výsledek už existuje, zahodit
ho by bylo horší než chybějící diagnostický řádek). Nový test (lock
ztracen AŽ během volání).

Opraveno (IMPORTANT #1, zpřesněno): kolo-11 tvrzení "assign_ids je
čistě aditivní" bylo nepřesné (maže ne-dict položky, koerzuje typy) -
opraveno, ale závěr (žádný automatický rollback) zůstává z přesnějšího
důvodu (mazaná/koerzovaná data jsou vždy garbage). Skutečná, nezávislá
chyba ve STEJNÉM bodě plně opravena: zálohy měly pevné jméno, druhé
spuštění po neúspěchu by přepsalo zálohu prvního běhu - teď `if not
exists` kolem obou zálohovacích kopií.

Opraveno (IMPORTANT #2/NIT): `toggleResolved` komentář tvrdil "Uložit
na resolve nečeká" - zastaralé od kola 8. Opraven na přesné vysvětlení
(čeká jen na JIŽ BĚŽÍCÍ resolve v okamžiku kliknutí).

Soubory: round-12-codex.md, round-12-claude.md.

## Round 13

Codex: CHANGES_NEEDED (0 BLOCKING, 2 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas s oběma, plus 1 vlastní nález navíc)

Opraveno: Task 10 regenerate - `glossary.all_terms()` přesunuto PŘED
`require_lock()` kontrolu (byla mezi kontrolou a `create_run`), nový
test na 503+žádný run řádek. CLI `_cmd_polish` - kolo-11 zdůvodnění
"CLI nepotřebuje require_lock" bylo nedostatečné (refresh_lock běží až
před commitem, ne před LLM voláními uvnitř `_polish_one_chapter`) -
přidána modulová `_lock_still_owned` funkce, `_cmd_polish` ji teď
předává jako `require_lock` do `_client_factory`, symetricky se
serverem. Vlastní nález: `_polish_env` fixtura mockuje `_client_factory`
bez `require_lock` kwarg - oprava signatury + přepsání testu na
`_lock_still_owned` přímo + samostatný drátovací test (mock nikdy
nevytváří skutečný `PipelineLLMClient`, takže end-to-end přes fixturu
nešlo testovat).

Soubory: round-13-codex.md, round-13-claude.md.

## Round 14

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas se všemi 3, žádný vlastní nález)

Opraveno: Task 13/15 kontradikce ohledně `POLISH_DRAFT_PATH` v `_cmd_init
--reset` - ověřeno, je to záměrná harmless výjimka (archivace leftover
souboru), ne přehlédnuté místo - Task 13 Step 7 i Task 15 Step 1
zpřesněny. Task 10 `state.create_run` přesunuto dovnitř `try` (bylo mimo
- selhání propadalo jako holý 500 bez JSON těla), `finally` teď navíc
kontroluje `rid is not None`. `chapters.html`'s `load()` + export
handler dostaly `try/catch` kolem `fetch` (chybělo úplně - síťová chyba
= nezachycená výjimka / navždy visící "Exportuji...").

Soubory: round-14-codex.md, round-14-claude.md.

## Round 15

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas, žádný vlastní nález)

Opraveno: `btn-regen` a `revertChapter()` (editor.html) neměly `catch`
kolem `fetch` - síťová chyba = nezachycená rejection, žádná chybová
hláška. Regenerace (read-only) dostala jednoduchý `catch` s chybovou
hláškou. Revert (zapisuje) dostal `catch`, co NEPŘEDPOKLÁDÁ "nic se
nestalo" (fetch výjimka může nastat i PO serverovém commitu, jen
odpověď se ztratila) - místo toho vynutí `window.location.reload()`
před další úpravou.

Soubory: round-15-codex.md, round-15-claude.md.

## Round 16

Codex: CHANGES_NEEDED (1 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas s oběma, plná implementace)

Opraveno (BLOCKING): `require_lock()` v `PipelineLLMClient.complete()`
byla jen PO `_guard()` - interaktivní cost guard (CLI) může na potvrzení
zapsat `spend_ceiling` bez ověřeného zámku. Přidána druhá kontrola PŘED
`_guard()`, obě zůstávají. Nový test (require_lock=False + přes strop →
_guard se vůbec nespustí).

Opraveno (IMPORTANT): ztráta zámku uvnitř `PipelineLLMClient.complete()`
mapovala se na obecnou 500 místo dokumentovaných 503. Přidána `LockLostError
(FatalRunError)` podtřída - CLI propagace beze změny (dědičnost), server
teď má samostatný `except main.LockLostError` → 503 PŘED obecným `except
Exception`. Nový test ověřuje 503.

Soubory: round-16-codex.md, round-16-claude.md.

## Round 17

Codex: CHANGES_NEEDED (1 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas s oběma, plná implementace)

Opraveno (BLOCKING): `_polish_one_chapter`'s existující `except FatalRun
Error` (main.py:620-624) přebaloval `LockLostError` na obyčejný `FatalRun
Error` - kolo-16 fix (`except main.LockLostError` v endpointu) by ho
nikdy nechytil. Přidán `except LockLostError: raise` PŘED obecnou větev.
Vlastní kolo-16 test byl navíc vadný (mockoval `_polish_one_chapter`
přímo, obcházel bug) - přepsán na reálný běh přes `PipelineLLMClient`.

Opraveno (IMPORTANT): `scope="history"` v `/api/findings/resolve`
odstraněna - mrtvý kód (žádný UI prvek ji nikdy nevolal), editovala
historii nezávisle na notes (co UI/report čtou), mohla způsobit
divergentní resolved hodnoty. Endpoint teď akceptuje jen scope="notes".

Soubory: round-17-codex.md, round-17-claude.md.

## Round 18

Codex: CHANGES_NEEDED (1 BLOCKING, 0 IMPORTANT, 1 NIT)
Claude: CHANGES_NEEDED (souhlas s oběma, plná implementace)

Opraveno (BLOCKING): kolo-16 kontroly PŘED/PO `_guard()` nepokrývaly
`_guard()`'s VLASTNÍ interní zápis `set_run_spend_ceiling`, co se
odehrává AŽ PO potenciálně dlouhém `self._ask()` (blokuje na uživatelský
vstup). Přidána TŘETÍ kontrola přímo uvnitř `_guard()`, těsně před
zápisem. Nový test rozlišuje od kolo-16 testu (confirm SE zavolá, zápis
stejně neproběhne).

Opraveno (NIT): Task 11's UPDATE chapters SET notes=? nenastavovalo
updated_at - přidáno.

Soubory: round-18-codex.md, round-18-claude.md.

## Round 19

Codex: CHANGES_NEEDED (1 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas s oběma, plná implementace)

Opraveno (BLOCKING): `assign_ids` dává KAŽDÉ analýze nové náhodné `id` -
"Znovu polish" → "Uložit" cyklus proto hromadil duplicitní nálezy
(starý vyřešený osiřelý vedle nového nevyřešeného) při každém opakování,
protože `_merge_findings_by_id` nikdy nic nemazala. Přidán `drop_stale_
non_markers` parametr (jen na text-měnící větvi Task 9, ne lehké -
bezpečné díky existující CAS ochraně) - staré non-marker nálezy bez
shody v čerstvé sadě se teď zahodí, markery zůstávají vždy. Nový
integrační test regenerate→save.

Opraveno (IMPORTANT): `btn-save`/`toggleResolved` léčily síťovou chybu
jako "neuloženo", i když server mohl zápis dokončit dřív, než se
odpověď ztratila. Aplikován stejný vzor jako `revertChapter` (kolo 15) -
přiznej nejistotu, vynuť reload.

Soubory: round-19-codex.md, round-19-claude.md.

## Round 20

Codex: CHANGES_NEEDED (1 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas s oběma - kolo-19 vlastní oprava byla
chybná, přepracováno)

Opraveno (BLOCKING): kolo-19 `drop_stale_non_markers=True` odporovalo
existujícímu kolo-4 testu (karta-B-přidala-nález race). Přepracováno na
`known_ids` parametr (z klientova `PERSISTED_IDS`, nové pole v save
payloadu) - rozlišuje "klient znal, superseduje" (smaž) od "klient
nikdy neznal, přidal někdo jiný" (zachovej vždy). Oba testy (kolo 4 i
kolo 19) teď vychází správně současně.

Opraveno (IMPORTANT): migrace (Task 13 Step 8) zálohovala DB přes
`shutil.copy2` - odporuje existující `_snapshot_db` dokumentaci (WAL/
konzistence riziko). Nahrazeno `main._snapshot_db`, selhání zastaví
migraci PŘED jakýmkoli zápisem.

Soubory: round-20-codex.md, round-20-claude.md.

## Round 21

Codex: CHANGES_NEEDED (2 BLOCKING, 0 IMPORTANT, 1 NIT)
Claude: CHANGES_NEEDED (souhlas se vším, plná implementace)

Opraveno (BLOCKING #1): lehká větev (text beze změny) v Task 9
nepředávala `known_ids` vůbec - "Znovu polish" → kandidát nepřijat →
uložit i tak = stejná duplicitní chyba jako kolo 19/20. Sjednoceno -
`known_ids` se teď posílá VŽDY, do obou větví (prázdná množina je
bezpečný no-op, žádná regrese). Zjednodušena i `_merge_findings_by_id`.

Opraveno (BLOCKING #2): migrace (Task 13 Step 8) zapisovala zálohy
přímo na finální cestu - přerušení by nechalo neúplný, ale "existující"
soubor, co by další spuštění mylně považovalo za platnou zálohu.
Opraveno - obě zálohy (DB i historie) přes dočasný soubor + atomický
`os.replace`, historie backup dostala vlastní except s recovery zprávou.

Opraveno (NIT): `payload.get("known_ids") or []` tiše propouštělo
přítomné-ale-nesprávné hodnoty (false/0/""/{}) - opraveno na explicitní
None/chybějící rozlišení.

Soubory: round-21-codex.md, round-21-claude.md.

## Round 22

Codex: CHANGES_NEEDED (0 BLOCKING, 3 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas se vším, plná implementace)

Opraveno: `toggleResolved`'s catch (kolo 19) volalo `window.location.
reload()` a pak `return` - navigace je asynchronní, Promise doběhla
vyřešená dřív, Uložit/revert mohly poslat vlastní request nad nejistým
stavem. Opraveno na `await new Promise(() => {})` (navždy visící).
`loadChapter()` teď vrací true/false, `btn-save`/`revertChapter`
reagují na selhání POST-commit reloadu tvrdým `window.location.reload()`
místo tichého pokračování nad starými daty. Task 11 resolve endpoint
nevolal `_backup_db_once` (na rozdíl od obou větví Tasku 9) - přidáno,
nový test ověřuje backup_state["done"] po prvním resolve.

Soubory: round-22-codex.md, round-22-claude.md.

## Round 23

Codex: CHANGES_NEEDED (0 BLOCKING, 1 IMPORTANT, 0 NIT)
Claude: CHANGES_NEEDED (souhlas, plná implementace)

Opraveno: `assign_ids` nechávala truthy-ale-ne-string `id` (např. `123`)
i duplicitní `id` v jedné dávce beze změny - zdroj: pre-Task-2 data v
`chapters.notes`, migrace je nefiltruje na shape. Takový nález by GET
vrátil, ale resolve/save by ho navždy odmítly (str required) - trvalý
mrtvý nález. Opraveno - `seen_ids` (lokální na dávku) vynucuje str +
neprázdné + unikátní, jinak nové uuid4. 2 nové testy v test_findings.py.

Soubory: round-23-codex.md, round-23-claude.md.

## Round 24 - CONSENSUS

Codex: CONSENSUS (0 BLOCKING, 0 IMPORTANT, 1 NIT)
Claude: CONSENSUS (vlastní nezávislý přezkum Tasků 6/7/8/12/15 přes
subagenta - žádný nový nález, jen Codexův NIT opraven)

Opraveno: migrace (Task 13 Step 8) UPDATE chapters SET notes=?
nenastavovalo updated_at - doplněno, stejná disciplína jako Task 11.

OBA recenzenti CONSENSUS ve STEJNÉM kole - podmínka ukončení splněna.

Soubory: round-24-codex.md, round-24-claude.md.
