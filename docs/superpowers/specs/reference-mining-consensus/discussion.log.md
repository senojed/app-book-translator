# Plan-consensus - discussion log

- Plán: `docs/superpowers/specs/2026-09-07-reference-mining-design.md`
- Start: 2026-09-07
- Max kol: 10

## Kolo 1 — 2026-09-07

- Codex: `round-1-codex.md` — VERDICT: CHANGES_NEEDED (4 BLOCKING, 9 IMPORTANT, 2 NITS)
- Claude: `round-1-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní BLOCKING, 3 vlastní IMPORTANT)

Codex našel 4 blokující body, všechny ověřeny proti kódu a přijaty: merge_draft_and_guide
zahazuje vytěžená pole (guide.py:93,111), neověřený návrh by se přes review dostal do
glosáře, globální výskyt v korpusu neprokazuje překladový vztah, důkaz nebyl svázán
s hodnotou. Claude přidal blokující bod, který Codex minul: opakovaný `scan` přepíše
draft celý (main.py:105) a těžbu tiše smaže.

Zásadní změny ve specu: výsledek těžby se stěhuje z draftu do vlastního
`data/reference.json`; `confirmed` smí vzniknout jen z deterministického stupně 0;
neověřené návrhy nechávají `cz` prázdné (invariant vynucen mechanicky, ne kázní);
přibyl test souvýskytu přes EN stranu; `merge_draft_and_guide` se rozšiřuje na
`merge_sources` se třemi zdroji.

Sporné body: žádné.

## Kolo 2 — 2026-09-07

- Codex: `round-2-codex.md` — VERDICT: CHANGES_NEEDED (3 BLOCKING, 7 IMPORTANT, 2 NITS)
- Claude: `round-2-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní IMPORTANT)

Nejzávažnější: oprava case-sensitivity z kola 1 vůbec neřešila problém, kvůli
kterému vznikla — české „na stole" je malými písmeny, takže case-sensitive dotaz
na `stole` ho najde stejně. Obecná slova (malé počáteční písmeno) proto nově
nikdy nedosáhnou `confirmed` automaticky. Ověřeno, že `stole` v draftu opravdu je.

Další blokující: pravidlo o vazbě důkazu (`cz == matched_cz`) zabíjelo metadata
právě u `proposed`/`contradicted`, kde je `cz` prázdné záměrně — vazba se nově
vyžaduje jen u tříd s předvyplněnou hodnotou. A UI nemá kudy reference dostat:
`build_app`/`run_review_server` třetí zdroj nemají (ověřeno, main.py:123).

Doplněno: přesný predikát souvýskytu s poměrem, validace odpovědi lexikografa,
odstranění bloků `reference` před uložením guide.json (server.py:129 dnes ukládá
celý payload), sdílená `normalize_key`, celá CLI a config sekce, přebírání
předchozích nálezů u selhané dávky (`stale`), report jako odvoditelný artefakt
s run_id místo lživého tvrzení o atomicitě dvou souborů.

Claude přidal: stupeň 0 nehledá aliasy, a přichází tak o důkazy u jmen, kde
překlad používá zkrácenou podobu (Dresden místo Harry Dresden).

Sporné body: žádné.

## Kolo 3 — 2026-09-07

- Codex: `round-3-codex.md` — VERDICT: CHANGES_NEEDED (4 BLOCKING, 6 IMPORTANT, 2 NITS)
- Claude: `round-3-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní BLOCKING, 1 IMPORTANT)

Nejcennější námitka: třída `contradicted` byla věcně chybná. Čeština skloňuje,
takže nenalezení jednoho konkrétního tvaru návrh nevyvrací — přejmenováno na
`not_attested` a hledání na CZ straně se nově opře o existující
`concordance.find_form_occurrences` (kmenové porovnání), místo aby se stavěla
vlastní morfologie.

Další blokující: agregace aliasů dvojitě počítala překryvy (`Dresden` uvnitř
`Harry Dresden`) a nález aliasu se vydával za doložení primárního tvaru; identita
přes `term_en` nerozliší stejné jméno v `places` a `terms` (nově `id =
sekce/klíč`); `write_reference` neuměl odlišit selhanou dávku od `unresolved`
a `--limit` by smazal položky mimo limit; a délkové pravidlo si protiřečilo
s vlastním testem `Mab`.

Postavy obcházely invariant: validace dovoluje prázdné `cz` při `render=keep`,
UI má `keep` jako výchozí a seed pak vloží anglické jméno. Nově vyžadována
aktivní volba.

Claude přidal blokující rozpor ve vlastní tabulce hranic (`reference.py` neměl
znát `guide`, ale volat `guide.normalize_key`) — řeší nový `src/textnorm.py`.
A upřesnil, že `--limit` se smí týkat jen stupně 1; stupeň 0 je zdarma.

Spec přepsán celý — po třech kolech se sekce rozcházely.

Sporné body: žádné.

## Kolo 4 — 2026-09-07

- Codex: `round-4-codex.md` — VERDICT: CHANGES_NEEDED (3 BLOCKING, 7 IMPORTANT)
- Claude: `round-4-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní IMPORTANT)

Zrušeno rozhodnutí z kola 3. `concordance.find_form_occurrences` se pro doložení
termínů použít nedá, ověřeno spuštěním:
  form_key("Bílá rada") == form_key("Bída rana")   → True
  find_form_occurrences("Byl to Za-Lord.", "Za-Lord") → []
Kmen zkracuje "bílá" i "bída" na "bí", "rada" i "rana" na "ra"; tokenizace přes
\w+ rozseká Za-Lord na pomlčce. Pro drift v jedné kapitole to stačí, pro doložení
v milionovém korpusu ne. `reference.py` dostává vlastní matcher se dvěma
kontrakty (přesný pro stupeň 0, prefixový pro stupeň 1), `concordance` zůstává
beze změny.

Další blokující: normalize_key vždy casefolduje, takže "case-sensitive hledání"
na normalizovaném textu bylo nemožné — normalizace nově slouží jen k identitě,
hledá se v surovém textu. `reference_path` musí být keyword-only (třetí poziční
parametr build_app je on_saved, server.py:108). `id` z draftu nejsou zaručeně
unikátní — scan_book duplicity nekontroluje, dedup je jen ve scan_chunks.

Důležité: write_reference dostal úplný stavový automat včetně nálezů stupně 0;
chybějící id v odpovědi modelu se nově liší od explicitního null (stale vs
unresolved); fresh:false nesmí předvyplňovat vůbec; prahy confirmed se počítají
jen z primárního tvaru; UI fallback `c.render || "keep"` (index.html:111) se ruší
ve prospěch prázdné volby; report se generuje z finálního slitého payloadu.

Claude přidal: částečný běh přes --limit se tvářil jako úplný, doplněno `coverage`.

Sporné body: žádné.

## Kolo 5 — 2026-09-07

- Codex: `round-5-codex.md` — VERDICT: CHANGES_NEEDED (2 BLOCKING, 2 IMPORTANT)
- Claude: `round-5-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní IMPORTANT,
  1 částečný nesouhlas)

Nejzávažnější: draft obsahuje 11 složených položek (`White Court / Red Court /
Vampire Courts`, `veil/veiling spell`, `Will/Billy`), které nejsou jedním
povrchem. Přesné hledání by je nikdy nenašlo a všechny by skončily jako
not_attested, ačkoli samotný skinwalker má 58 výskytů. Claude o nich věděl
z vlastní úvodní analýzy (přeskakoval je podmínkou na "/"), ale do specu je
nezanesl. Doplněn kanonizační krok + oprava promptu scouta. Mezi položkami jsou
i duplicity v opačném pořadí (skinwalker/naagloshii vs naagloshii/skinwalker).

Dále: `coverage` neuchovával failed ani missing_response, takže po skončení
příkazu nešlo odlišit "model řekl neznám" od "dávka spadla"; testy si
protiřečily (řádky 510 a 512); `fresh` se kontroloval jen proti draftu, ačkoli
fingerprint zahrnuje i korpus a prahy — nově tři samostatné příznaky.

ČÁSTEČNÝ NESOUHLAS: Codex chtěl u alias-only nálezů zakázat předvyplnění `cz`
plošně. Claude přijal princip, ale nahradil plošný zákaz pravidlem "doložený tvar
musí být slovem primárního povrchu" (Dresden ⊂ Harry Dresden ano, Hoss ne).
Důvod: 976 výskytů "Dresden" v deseti dílech je silný důkaz nepřeloženého jména
a u postavy render=keep znamená cz=canonical_en z definice.

Claude přidal: korpusový fingerprint se musí brát z cache manifestu, jinak by
review kvůli formuláři načítal 20 EPUBů (~30 s).

## Kolo 6 — 2026-09-07

- Codex: `round-6-codex.md` — VERDICT: CHANGES_NEEDED (2 BLOCKING, 2 IMPORTANT, 2 NITS)
- Claude: `round-6-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní IMPORTANT)

SPOR Z KOLA 5 VYŘEŠEN — Claude svou námitku stáhl. Codexův protiargument je
silnější: výskyt "Dresden" nedokládá tvar "Harry Dresden", protože překlad může
příjmení ponechat a křestní jméno počeštit. Praktická stránka rozhodla: weak
položka je ve formuláři rozbalená i s důkazem, takže se doplní za dvě vteřiny —
cena za nepředvyplnění nulová, za špatné předvyplnění chybný termín v celé knize.
Alias-only nález nově nepředvyplní cz ani render.

Kanonizace z kola 5 byla datově chybná: White Court / Red Court / Vampire Courts
jsou tři různé entity, ne aliasy jedné. Výčty se nově rozdělují na samostatné
položky bez jakéhokoli slučování podle interpunkce; synonyma tím dostanou dva
řádky, což je správně (dva anglické povrchy = dva záznamy pro concordance).

Prefixový matcher z kola 5 nefungoval — ověřeno spuštěním, že max(4, len-2)
nespáruje ani bílá/bílé, ani rada/radě. Opraveno na max(3, len-2); ověřeno, že
skloňování zvládne a kolizi bílá/bída pořád odmítne.

corpus_fresh porovnával dva historické údaje (otisk v reference.json proti
manifestu v téže cache) — nově se manifest sestaví znovu z disku přes os.stat.

Claude přidal: rozdělení výčtů musí vidět i formulář, jinak nemá kam pověsit tři
nálezy na jeden řádek draftu — sdílená guide.canonical_items() volaná těžbou
i merge_sources.

## Kolo 7 — 2026-09-07

- Codex: `round-7-codex.md` — VERDICT: CHANGES_NEEDED (4 BLOCKING, 2 IMPORTANT)
- Claude: `round-7-claude.md` — VERDICT: CHANGES_NEEDED (2 vlastní BLOCKING)

PROCESNÍ CHYBA CLAUDEA: dvě opravy z kola 6 (corpus_fresh, alias-only) se do
specu vůbec nezapsaly — textová náhrada neseděla na vzor změněný v kole 5
a proběhla naprázdno, což nebylo ověřeno. V shrnutí kola 6 byly přesto hlášeny
jako hotové. Od tohoto kola se každá změna specu ověřuje grepem; kolo 7 má
verifikační výpis všech sedmi změn.

Matcher specifikován potřetí neúspěšně. Změřeno na 270 000 slovech korpusu:
prefix-3 dává u "práh" 54 tvarů (práce, právo, prázdný), u "rada" 25 (radost,
raději). Varianta s uzavřenou množinou koncovek propadá na plášť/pláště.
Spec proto přechází z algoritmu na PŘEJÍMACÍ KRITÉRIA + povinné měření
v implementaci; volba algoritmu patří do plánu.

Automatické rozdělování složených položek zrušeno (zavedeno v kole 5, opraveno
v kole 6, nyní zamítnuto celé). Důvod: migrace suggested_cz, aliasů,
must_decide a guide.json plus kolize s glossary._seed_one, který páruje přes
aliasy — ověřeno, že Billy Borden má aliasy Billy i Will, takže rozdělené
položky by mu přepsaly kanonický tvar. Nově rozděluje člověk ve formuláři.

Doplněn guard v seed_from_guide proti přepsání řádku nalezeného jen přes alias —
latentní chyba stávajícího kódu, kterou by rozdělené položky spustily.

Opraveno i to, že freshness nesmí potlačit lidská rozhodnutí z guide.json.

## Kolo 8 — 2026-09-07

- Codex: `round-8-codex.md` — VERDICT: CHANGES_NEEDED (6 BLOCKING, 1 IMPORTANT)
- Claude: `round-8-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní BLOCKING)

Pět z šesti Codexových nálezů nebyly nové chyby v návrhu, ale ZBYTKY PO NEÚPLNĚ
PROVEDENÝCH OPRAVÁCH z kol 6 a 7: zrušený prefixový algoritmus zůstal na pěti
místech, `compound` chyběl ve Finding i v klasifikační tabulce, tok pro složené
položky si protiřečil ve třech sekcích, klasifikační tabulka odporovala pravidlu
o alias-only. Verifikace jednotlivých náhrad (zavedená v kole 7) je nutná, ale
nestačí — je třeba kontrolovat i to, že po opravě nikde nezůstalo staré tvrzení.
Spec proto KONSOLIDOVÁN CELÝ a doplněn verifikační seznam osmi kontrol.

Věcné nálezy kola:
- Alias guard z kola 7 by zahodil ručně vytvořenou položku: `Billy` už alias
  `Billy Borden` je, takže "přidání k aliasům" je no-op a nový řádek nevznikne.
  Nově je kolize povrchu s cizím aliasem CHYBOU VALIDACE, kterou řeší člověk.
- `--dir` override by `review` neznal (výchozí REFERENCE_DIR=""), takže by
  čerstvou těžbu označil za zastaralou. reference.json proto nese `source_root`
  a UI staví otisk z něj; odpadá protahování reference_dir třemi vrstvami.
- Ověřeno v draftu, že must_decide opravdu obsahuje složené klíče
  (naagloshii/skinwalker, Shagnasty/skinwalker) — POST je musí rozbalit PŘED
  apply_must_decide a validace odmítnout zbylý klíč se "/".
- Předvyplnění se nově řídí příznakem `primary_attested`, ne třídou.
- Matcher dostal měřitelná kritéria: eval fixture >=40 anotovaných dvojic,
  100 % na negativní množině, >=90 % na pozitivní.

## Kolo 9 — 2026-09-07

- Codex: `round-9-codex.md` — VERDICT: CHANGES_NEEDED (2 BLOCKING, 2 IMPORTANT)
- Claude: `round-9-claude.md` — VERDICT: CHANGES_NEEDED (0 vlastních)

Kolo bylo zaměřeno na ověření, že konsolidační přepis z kola 8 neztratil žádné
rozhodnutí z logu. Ukázalo se, že ztratil dvě a jedno rozbil:

1. ZTRACENO: validace identity z kola 4 (prázdné klíče, duplicitní (section,
   klíč)). Ověřeno grepem — nula výskytů v konsolidovaném dokumentu. Obnoveno.
2. ZTRACENO: význam coverage v UI. Ukládání zůstalo, ale formulář ukazoval
   všechny čtyři důvody prázdné položky stejně. Doplněno včetně testu.
3. REGRESE: nové pořadí POSTu vypustilo _check_must_decide_answered. Ověřeno
   v kódu, že apply_must_decide (server.py:43) prázdné odpovědi přeskočí a pak
   seznam vymaže, takže dnešní kód tu kontrolu volá PŘED ní (:122 před :125).
   Bez ní by nezodpovězená otázka tiše propadla. Pořadí opraveno na šest
   očíslovaných kroků.
4. Doplněno: přemapování must_decide u složené položky s více ponechanými
   variantami potřebuje explicitní cílové id v payloadu — u naagloshii/skinwalker
   se z textu odvodit nedá, komu odpověď patří.

Poučení: konsolidační přepis je nejrizikovější operace celé smyčky a patří k němu
kontrola proti logu rozhodnutí, ne jen kontrola vnitřní soudržnosti.

## Kolo 10 — 2026-09-07 (finální)

- Codex: `round-10-codex.md` — VERDICT: **CONSENSUS** (bez nálezů)
- Claude: `round-10-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní IMPORTANT)

Claude při inventuře všech 22 rozhodnutí proti specu našel třetí ztrátu po
konsolidačním přepisu z kola 8, kterou nezachytilo ani cílené kolo 9: zrušená
sekce "Stupně řešení" obsahovala pravidlo, že stupeň 1 dostává jen povrchy
nedoložené stupněm 0, a odhad ceny. Bez toho by implementátor musel hádat,
jestli se modelu posílá všech 132 povrchů. Obnoveno a ověřeno.

VÝSLEDEK: MAX_ROUNDS. Shoda vyžaduje CONSENSUS od obou ve stejném kole; Codex
hodnotil verzi před touto opravou. Nedořešené body: žádné. Sporné body: žádné.
Viz `final-verdict.md`.
## Kolo 11 — 2026-09-07 (fresh-eyes, změněný formát)

- Codex: `round-11-codex.md` — VERDICT: CHANGES_NEEDED (3 BLOCKING, 13 IMPORTANT,
  5 OVER-ENGINEERED)
- Claude: `round-11-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní BLOCKING)

ZMĚNA FORMÁTU: Codex dostal spec BEZ historie a s výslovnou otázkou na proporce
("je to na osobní nástroj překombinované? co bys škrtl?"). Vyneslo to víc než
tři předchozí kola dohromady.

Nejzávažnější (Claude ověřil a rozšířil): validace kolizí z kola 8 by znemožnila
uložit formulář. Reálný draft má 15 kolizí, ne jednu — Morgan/Donald Morgan,
Thomas/Thomas Raith, Karrin Murphy/Murphy, Rashid/the Gatekeeper... a většinou
jde o DUPLICITY OD SCOUTA, ne o skutečné konflikty. UI nemá na kanonická jména
editaci ani mazání, takže by nešlo uložit nic.

ZÁSADNÍ OBRAT: příčinou většiny složitosti specu byla vadná data draftu
(11 výčtů + 15 duplicit), kolem nichž spec postavil tři podsystémy. Nově se
draft JEDNOU normalizuje (samostatný krok 0, rozhoduje člověk) a podsystémy se
ruší. Levnější odstranit příčinu než obsluhovat následek.

Přijaty všechny čtyři nálezy o překombinovanosti:
- editor složených položek, dočasná id, přemapování must_decide → pryč
- stale, čtyři stavy coverage, obnova po položkách, --limit → pryč, nahrazeno
  ATOMICKÝM SELHÁNÍM (selže cokoli → předchozí soubor zůstane, spusť znovu)
- tři příznaky čerstvosti → jeden
- morfologie v kontraktu B, fixture 40 dvojic, checkpoint na 20 dotazech → pryč,
  nahrazeno přesnou shodou celého slova; stupeň 1 stejně nikdy nepředvyplňuje,
  takže tolerance skloňování kupovala málo za tři neúspěšné pokusy o matcher
- samostatný reference_report.md → pryč, souhrn na konzoli

Opraveny dvě reálné chyby stupně 0: obecné slovo (stole) se předvyplňovalo
a zároveň se nedostalo do stupně 1 — nejhorší kombinace; a case-insensitive
shoda mohla dát confirmed na nesouvisejícím českém slově.

Spec: 619 → 484 řádků.

## Kolo 12 — 2026-09-07 (zkouška proveditelnosti)

- Codex: `round-12-codex.md` — VERDICT: CHANGES_NEEDED (10 dohadů, 2 zásadní;
  2 rozpory se stávajícím kódem)
- Claude: `round-12-claude.md` — VERDICT: CHANGES_NEEDED

FORMÁT: Codex měl ze specu napsat první tři úkoly implementačního plánu a vést
seznam všeho, co musel dohadovat. Jiný druh kontroly než kritika.

NEJZÁVAŽNĚJŠÍ NÁLEZ CELÉ OPONENTURY: invariant specu byl jedenáct kol v rozporu
s chováním, které nástroj má už dnes. Ověřeno — guide.py:92 předvyplňuje
`render` ze scoutova `suggested` a :111 `cz` ze `suggested_cz`, tedy modelové
odhady bez jakéhokoli doložení, které uložením jdou do glosáře jako závazné.
Invariant byl psaný jen pro těžbu, takže rozpor zůstal skrytý; deset kol
oponentury ho nenašlo, protože všichni posuzovali těžbu izolovaně.

Invariant přeformulován: "odhad se nikdy nesmí tvářit jako důkaz" — každá
předvyplněná hodnota nese viditelnou provenienci. Návrh lexikografa se
nepředvyplňuje proto, že by byl nerozeznatelný od hodnoty podložené
referencemi; scoutův návrh zůstává, ale označený.
OTEVŘENÁ OTÁZKA PRO ČLOVĚKA: zrušit i předvyplňování scoutových návrhů?
Bezpečnější, ale znamená vypsat ~59 termínů ručně. Spec to nerozhoduje.

Dále: doplněn typ SurfaceItem jako vstup resolve() (zásadní, veřejná hranice
orchestru), určeno rozhraní normalizačního kroku (report-only, ne interaktivní),
kontrakt spojování dokumentů (raw_text bez title), st_mtime_ns, zúžení bílých
znaků. Opraveno nepravdivé tvrzení, že extract_json neumí top-level seznam.

## Rozhodnutí uživatele o předvyplňování (mezi koly 12 a 13)

Otevřená otázka z kola 12 zodpovězena uživatelem a zanesena do specu:

- předvyplňuje se **jen to, co je doloženo referencemi**; scoutův odhad
  a návrh lexikografa se ukazují vedle prázdného pole jako text
- **každá akce je vratná a původní hodnota se nikdy neztratí:**
  - doloženo referencemi → předvyplněno a zamčeno; "změnit předvyplněné"
    odemkne, "vrátit zpět předvyplněné" obnoví
  - odhad → prázdné pole + "použít návrh"; po použití se tlačítko změní na
    "zpět", které pole zase vyprázdní
- tlačítko "přijmout všechny scoutovy návrhy" pro toho, kdo nechce klikat po
  jednom — jedno vědomé rozhodnutí místo sta třiceti nevědomých
- návrh se nikdy nedává do editovatelného pole, aby po přepsání nezmizel
  a šlo porovnat, co navrhl model a co říká referenční překlad

Claude upozornil na cenu zamčených polí (klik navíc při každé legitimní změně);
uživatel to potvrdil jako záměr. Vzor je konzistentní s tím, co formulář už
používá u must_decide.

## Kolo 13 — 2026-09-07

- Codex: `round-13-codex.md` — VERDICT: CHANGES_NEEDED (1 BLOCKING, 3 IMPORTANT, 2 NITS)
- Claude: `round-13-claude.md` — VERDICT: CHANGES_NEEDED

BLOKUJÍCÍ: nové pravidlo o předvyplňování nebylo aplikováno na celý formulář
a spec o tom obsahoval nepravdivé tvrzení. Ověřeno: guide.py:127 předvyplňuje
oslovení ze scoutova suggested, :138 styl ze style_notes, index.html:80-88
předvyplňuje odpověď na vztahovou otázku z md.default — vlastní komentář v tom
souboru přitom říká "schválně NEpředvyplňujeme", což platí jen pro textovou větev.

Doplněn explicitní ROZSAH pravidla: platí pro hodnoty, které se stanou závazným
glosářovým termínem (postavy, místa, termíny). Vztahy dostanou scoutův návrh
předvyplněný, ale sekce vyžaduje zaškrtnutí "zkontrolováno" (vztahy jsou vyšší
sázka — špatné vykání se táhne celou knihou — ale 34 vynucených roletek je
nepřiměřené k binární volbě). Styl bez ceremonie. Vztahová must_decide dostanou
prázdnou volbu.

Dále: merge_sources doplněn o provenance (human/reference/none) a oddělené
držení scoutova i lexikografova návrhu (položka může mít oba); "přijmout
všechny" nepřepíše ručně vyplněná ani doložená pole a zpět vrátí jen jím
změněná; doplněn chybějící klasifikační případ (vlastní jméno nalezené jen
case-insensitive nad prahem → evidence_only).

Potvrzeno, že po zjednodušení nezůstaly viset odkazy na zrušené podsystémy.

## Kolo 14 — 2026-09-07

- Codex: `round-14-codex.md` — VERDICT: CHANGES_NEEDED (3 BLOCKING, 4 IMPORTANT)
- Claude: `round-14-claude.md` — VERDICT: CHANGES_NEEDED

Všech sedm ověřeno MĚŘENÍM na skutečném draftu. Krok 0 byl specifikovaný proti
neúplnému obrazu poškození dat:
- 9 must_decide klíčů neukazuje na žádnou položku ve své sekci (Warden,
  the Nevernever, Mouse (pes), grasshopper_nickname, ...). apply_must_decide
  při nenalezení klíče ZALOŽÍ NOVÝ ŘÁDEK → duplicitní/špatně zařazené položky.
- 4 vztahy mají lomítko ve jméně (Will/Georgia jsou dva různí lidé).
- Alias s vlastním překladem se do glosářového řádku nevejde (jedno cz pro
  kanonický tvar i aliasy) — Injun Joe je alias Listens-to-Wind a zároveň má
  vlastní otázku na překlad. Nově se takové položky povyšují na samostatné.

Celkem ~39 řádků k ruční opravě místo původně uváděných 26.

Dále: POST musí čistit allowlistem (provenance, scout_suggestion,
lexicographer_suggestion a relationships_reviewed by jinak zůstaly v guide.json);
Finding.source doplněn o none pro unresolved; sjednoceno chování při nečerstvé
referenci (jen poznámka, nic jiného); zaškrtnutí vztahů dostalo payload kontrakt.

## Kolo 15 — 2026-09-07

- Codex: `round-15-codex.md` — VERDICT: CHANGES_NEEDED (0 BLOCKING, 5 IMPORTANT, 2 NITS)
- Claude: `round-15-claude.md` — VERDICT: CHANGES_NEEDED

Poprvé po devíti kolech ŽÁDNÝ BLOKUJÍCÍ NÁLEZ.

Krok 0 nekontroloval všechny postpodmínky, které slibuje. Doplněno šest
očíslovaných; k tabulce vad přibyly čtyři kategorie, všechny ověřené měřením:
- 6 povrchů s poznámkou v závorce (Warden(s), the Merlin (title)) — přesné
  hledání je u nich z principu nefunkční
- 1 homonymum napříč sekcemi: Demonreach je postava I místo. Sekční id před tím
  nechrání, protože glosář má identitu GLOBÁLNÍ (_seed_one hledá přes celou
  tabulku) — druhý seed by první tiše přepsal
- 9 neidentifikujících aliasů (sir, kid, apprentice, Captain, Bob) — v predikátu
  souvýskytu by E rozšířily skoro na celý korpus
- 2 vztahy odkazující zkráceným jménem (Ebenezar vs Ebenezar McCoy)

books_with_en nově používá JEN PRIMÁRNÍ POVRCH, aby predikát nestál na tom, že
normalizace proběhla dobře. Aliasy míst a termínů doplněny do merge i allowlistu.

Vedlejší nález: do specu se dostal skutečný NUL bajt (neescapovaný oddělovač
dokumentů v textové náhradě přes shell) a soubor se stal binárním. Opraveno.

## Kolo 16 — 2026-09-07

- Codex: `round-16-codex.md` — VERDICT: CHANGES_NEEDED (1 IMPORTANT)
- Claude: `round-16-claude.md` — VERDICT: **CONSENSUS**

Codexův jediný nález: POST allowlist zahazoval `note`. Ověřeno, že
merge_draft_and_guide poznámku emituje (guide.py:94,112) a _seed_one ji ukládá
do glosářového řádku (glossary.py:139), takže by se kontext od scouta při
uložení ztratil. Doplněno do allowlistu a přidán test na zachování napříč
celou cestou draft → GET → POST → guide.json → glosář.

Claude prošel spec vlastní inventurou proti logu rozhodnutí i proti kódu a nenašel
nic, co by způsobilo špatné chování, ztrátu dat nebo zastavilo implementaci —
vyhlašuje CONSENSUS. Zbývající nejistoty (prahy, poměr souvýskytu, přísnost
přesné shody) patří měření při prvním běhu, ne oponentuře, a všechny jsou
levně změnitelné v config.py.

## Kolo 17 — 2026-09-07

- Codex: `round-17-codex.md` — VERDICT: CHANGES_NEEDED (1 IMPORTANT)
- Claude: `round-17-claude.md` — VERDICT: CONSENSUS

Codexův jediný nález byl zbytek po opravě z kola 15: změnil jsem books_with_en
na primární povrch, ale definice predikátu souvýskytu o deset řádků výš dál
říkala "anglický povrch (nebo alias)". Rozdíl mění klasifikaci proposed.
Sjednoceno, opravena i signatura (surface místo surfaces), doplněn test.

