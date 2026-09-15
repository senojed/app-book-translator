# Round 4 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo - průchod přes vlastní
opravy z kol 1-3 (hlavně editor.html jako celek, ne jen diffy) potvrdil,
že Codexovy nálezy pokrývají to podstatné. Všimnul jsem si při opravách
dvou VLASTNÍCH překlepů ve svých komentářích (jeden cyrilský znak
místo "b", jeden nesmyslně opakovaný fragment) - opraveno při psaní.

## On Codex's points

### Agreed + fixed
- **BLOCKING - obě větve ukládání mají neslučitelnou sémantiku nálezů:**
  ověřeno na obou scénářích (empty-list-jako-clear nefunguje v lehké
  větvi; normální větev PŘEPISUJE celou sadu, takže karta-B-přidala-
  nález-při-nezměněném-textu race zůstal otevřený pro SKUTEČNOU změnu
  textu). Sjednoceno - `_merge_findings_by_id` sdílená OBĚMA větvemi.
  Vědomě NEpodporováno: explicitní "smaž všechny nálezy" (merge z
  principu nic nemaže) - zdokumentováno jako přijatá mezera, ne bug (UI
  na hromadné mazání nemá tlačítko).
- **IMPORTANT - `toggleResolved` bez vlastního pending stavu:** souhlas,
  ověřil jsem všechny tři dílčí body (síťová výjimka nechává checkbox
  navždy disabled, re-render povolí cizí probíhající request, dvě
  kliknutí na týž checkbox mohou běžet souběžně). `PENDING_RESOLVE_IDS`
  set + `try/catch` opravuje všechny tři.
- **IMPORTANT - `loadChapter`/`lockEditor` první načtení neúplné:**
  ověřeno - `text-area`/`btn-regen`/`btn-save` se ODEMKLY i s `CH===
  null` po neúspěšném prvním GET (kolo 3 opravilo jen btn-orig/btn-
  codex). Sjednoceno na jedno `noEdit` pravidlo pro všechny prvky +
  status-aware (`EDITABLE_STATUSES`).
- **IMPORTANT - validace nepokrývá PRODUCENTY nálezů:** souhlas -
  kritik/concordance nejsou validované jako klientský save vstup,
  `render_findings_html`/`is_marker` by na jejich výstupu mohly spadnout.
  Opraveno DEFENZIVNĚ v `is_marker` (isinstance kontrola) a `render_
  findings_html` (`str()` před `escape`) místo validace u každého
  producenta zvlášť - jednodušší, robustnější, míň míst k údržbě.
- **IMPORTANT - Task 5 snapshot může ukončit CLI neošetřenou výjimkou:**
  ověřeno PŘÍMO v `main.py:1333-1347` - `main()` zachytává VÝHRADNĚ
  `state.LockError`. Moje dřívější tvrzení "zachytí jako obecnou chybu"
  bylo nepravdivé, opraveno na vlastní `try/except` kolem `_snapshot_db`.
- **IMPORTANT - Task 13 migrace bez zámku/zálohy/validace:** souhlas na
  všech třech bodech. Přidán `state.acquire_lock`/`release_lock`,
  `shutil.copy2` zálohy PŘED zápisem, a filtr ne-dict položek (stejná
  tolerance jako `main._parse_findings`, ne přísnější).
- **IMPORTANT - Tasky 9-11 chybové hranice neúplné (Task 11 notes zápis
  bez try/except, Task 10 create_run/factory před try):** ověřeno na
  obou konkrétních bodech, opraveno (Task 11's `notes` větev teď má
  STEJNÝ try/except jako `history` větev vedle ní; Task 10's `cf`
  konstrukce přesunuta dovnitř `try`, aby `finally` vždy dostal šanci
  run uzavřít).
- **NIT - `renderHistory` komentář neodpovídá zdroji:** ověřeno přímo v
  `_annotate_history` (přečteno na začátku session) - `can_revert_*`
  SKUTEČNĚ nezávisí na `stale`. Opraven vlastní nepřesný komentář z
  kola 3, vysvětleno PROČ je to bezpečné i tak (revert endpoint má
  vlastní CAS).
- **NIT - Task 15 Step 1 popisuje starou no-op podmínku:** souhlas,
  opraveno na aktuální "lehkou větev" popis.

### Disagreed
- **IMPORTANT - Task 4 vs Task 5, `_polish_one_chapter` a `_commit_
  polish_result` používají odlišné `rendered_terms`:** technicky platné
  pozorování, ale NESOUHLASÍM, že je to bug k opravě sjednocením.
  `_polish_one_chapter`'s concordance kontrola se ptá "sedí TENHLE
  kandidátní text na to, co je AKTUÁLNĚ v `term_mentions`" - živá DB je
  pro tuhle otázku SPRÁVNÝ zdroj, ne historický. `_commit_polish_
  result`'s preference historie řeší JINOU otázku (co archivovat pro
  BUDOUCÍ editace, aby se neztratily starší nahlášené tvary). Nucené
  sjednocení by mohlo konkordanci nechat kontrolovat proti ZASTARALÝM
  historickým datům místo aktuálního stavu DB - to by bylo HŮŘ, ne líp.
  Necháno beze změny; nejhorší důsledek dnešního stavu je jeden
  příležitostný falešně pozitivní "omission" nález, co uživatel může
  odškrtnout, ne ztráta dat.
- **IMPORTANT - Task 9 chybové hranice (`state.get_chapter`/merge-prep
  před `try`):** souhlasím technicky (unhandled exception by dala
  obecnou FastAPI 500 bez JSON těla, ne moji hezčí zprávu), ale
  NEIMPLEMENTOVAL jsem restrukturalizaci celého handleru - `state.
  get_chapter` je prostý SELECT nad lokálním SQLite souborem, co v
  praxi selže jen při katastrofickém selhání disku (stejná třída
  zbytkového rizika, jakou `2026-09-11` spec už jinde vědomě přijímá).
  FastAPI i BEZ mého vlastního try/except pořád vrátí 500 (jen bez
  hezkého JSON těla) - ne tichý pád/zavěšení. Přidávat další vrstvu
  try/except v tomhle bodě čtvrtého kola opravování stejného souboru
  riskuje víc nových chyb, než kolik reálné hodnoty přidá.

## Claude VERDICT

CHANGES_NEEDED (BLOCKING bod byl reálný a opravený; zbytek IMPORTANT
taky, kromě dvou vědomě nepřijatých bodů výš)

## Summary for log

Kolo 4 dokončilo poslední velkou třídu chyby (nekonzistentní sémantika
nálezů mezi dvěma zápisovými cestami) sdílenou `_merge_findings_by_id`
funkcí - stejný vzorec jako předchozí kola: jedna sdílená funkce
zavolaná ze VŠECH míst je spolehlivější než dvě nezávislé, postupně
rozcházející se implementace. Zbylé opravy byly menší, izolované
(chybějící try/except na jednotlivých místech, migrace bez zámku).
Poprvé v tomhle procesu jsem nesouhlasil se dvěma Codexovými IMPORTANT
body se skutečným zdůvodněním (ne jen "už opraveno jinde") - jeden o
architektonickém rozdílu, co dává smysl NEsjednocovat, druhý o
proporcionalitě dalšího zásahu do stejného kódu ve čtvrtém kole.
