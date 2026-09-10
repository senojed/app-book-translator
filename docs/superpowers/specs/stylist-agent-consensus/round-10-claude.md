# Round 10 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem udělal vlastní grep sweep na
`register_changed`/`VÝZNAM`/`rejstřík` napříč CELÝM dokumentem (ne jen
kolem míst, co Codex citoval), abych ověřil, že nezůstal JEŠTĚ jeden
skrytý výskyt stejné mezery - nic dalšího nenalezeno.

## On Codex's points

### Agreed + fixed
- **BLOCKING - argv test má chybnou indexaci:** ověřil jsem přímo Python
  sémantiku - `sys.argv` UVNITŘ spuštěného skriptu neobsahuje interpret
  (`sys.executable`), jen cestu ke skriptu samotnému jako `argv[0]`.
  `tail = argv[2:]` tak omylem zahazovalo i `"exec"`, `assert tail[0] ==
  "exec"` by VŽDY selhalo. Opraveno na `tail = argv[1:]` a test teď
  porovnává CELÝ seznam přesně (ne piecemeal `in`), včetně vztahu `-o ==
  <-C hodnota>/out.txt`.
- **IMPORTANT - lifecycle snapshotu neuklidí při chybě PŘED prvním
  `try`:** ověřil jsem přímo - `glossary.all_terms`/`guide_mod.load_
  guide`/`state.create_run` ležely PŘED `try/finally`, takže výjimka
  odsud by nechala `.pre-polish-snapshot` osiřelý A navíc by `finally`
  spadl na `NameError` (`rid` nedefinovaný), kdyby padl přímo `create_
  run`. Přepracováno - celý úsek od inicializace `rid = None` je uvnitř
  jednoho `try/finally`, `finish_run` se volá jen když `rid is not None`.
- **IMPORTANT - procentní/mezerová mezera v číselném guardu:** ověřil
  jsem přímo regex `\d+(?:[.,]\d+)?%?` - nepovoloval ŽÁDNOU mezeru před
  `%`, takže běžný český zápis "12 %" (s mezerou, běžná typografie)
  nikdy nezachytil `%` jako součást tokenu - kontrola procenta byla na
  reálném českém textu prakticky mrtvá. Přidán `[ \xa0]?` (mezera i NBSP)
  do regexu a normalizace v `_number_multiset` (mezera se před
  porovnáním odstraní, stejně jako desetinný oddělovač).
- **IMPORTANT - stale próza (guide_block/register bod):** ověřil jsem
  přímo - "Rozhodnutí" bullet u `guide_block` pořád tvrdil (současným
  časem) "`check_meaning_preserved` taky ne (ptá se jen na VÝZNAM)", což
  od kola 7 (stejný dokument, o pár set řádků výš) neplatí -
  `check_meaning_preserved` REJSTŘÍK kontroluje. Přepsáno na přesný popis
  - `guide_block` je teď zdůvodněný jako PREVENCE (instrukce předem),
  ne jako jediná cesta k DETEKCI (tu `check_meaning_preserved` zvládne i
  bez něj).
- **IMPORTANT - stale próza (`_polish_rejected` docstring):** ověřil jsem
  přímo - docstring pořád psal `concordance.check_chapter(en, cz,
  glossary_rows, [])` (prázdný seznam), zatímco skutečný volající kód
  (`_polish_one_chapter`) posílá `rendered_terms` (výsledek kola 5
  BLOCKING opravy). Opraveno, s výslovnou poznámkou, že prázdný seznam by
  byl přesně ta slepá skvrna, co kolo 5 řešilo.

### Disagreed
- **IMPORTANT - znaménko čísel (`-12 → 12`) mimo záběr číselného
  guardu:** rozporuji ČÁSTEČNĚ - souhlasím s procentní/mezerovou částí
  (opraveno výš), ALE záměrně NEpřidávám podporu znaménka. Pomlčka je v
  běžné próze silně přetížená (rozsahy stran "12-14", vsuvky, spojovník
  ve složenině) - naivní `[+-]?\d+` by "12-14" rozdělil na tokeny `["12",
  "-14"]` a legitimní stylistickou úpravu "strany 12-14" → "strany 12 až
  14" (dash zmizí, mezerový formát zůstane) by vyhodnotil jako ZMĚNU
  čísla (multiset `{"12","-14"}` vs. `{"12","14"}`), i když se fakticky
  nic nezměnilo - NOVÝ falešný poplach přesně tam, kde dřív žádný nebyl.
  Cena téhle regrese je vyšší než přínos zachycení řídkého úmyslně
  otočeného znaménka - to navíc pořád hlídá `check_meaning_preserved`
  (LLM vrstva), jen ne deterministicky. Stejná "cheap, ne NLP" filozofie,
  co dokument už používá pro slovně vypsaná čísla/data (viz komentář u
  `_NUMBER_RE`). Zdokumentováno přímo v kódovém komentáři, aby
  rozhodnutí nezůstalo jen v tomhle review souboru.
- **IMPORTANT - próza "kolem řádku 625" (žádný soubor s textem knihy):**
  přečetl jsem CELOU větu v kontextu (ne izolovaný řádek) - už obsahuje
  explicitní caveat "pozor - STYLIZOVANÁ verze se stejně zapíše přes
  `-o`", takže tvrzení je přesné (mluví jen o PŮVODNÍM textu, co jde
  stdinem, ne o výstupu). Nenašel jsem žádnou verzi týhle věty bez
  tohohle caveatu nikde v dokumentu - pravděpodobně staré číslo řádku z
  verze dokumentu PŘED mými kolo-9 úpravami (posun o desítky řádků).
- **IMPORTANT - próza "kolem 1576-1583, 1608-1612" (přímé/líné kopírování
  DB):** kolo-7 a kolo-8 bully v "Rozhodnutí" popisují historický vývoj
  mechanismu (kolo 7 eager → kolo 8 lazy) - to je STEJNÝ vzorec, jaký
  dokument používá VŠUDE (chronologický log, novější bod supersedes
  starší, nikdy se zpětně nepřepisuje) a nikdy dřív nebyl namítán jako
  problém, i když kolo 8 samo nechalo kolo-7 bullet nedotčený. Nový
  kolo-9 bullet (přidaný minule) mechanismus zpřesňuje a explicitně
  odkazuje na kolo 8 jako výchozí bod. Jedna z citovaných dvou lokací
  (`guide_block`/register) BYLA skutečně stale a opravena výš - u téhle
  (čistě popis DB zálohy) jsem žádnou verzi popisující mechanismus jako
  KONEČNÝ/aktuální (na rozdíl od "kolo 8 udělalo X") nenašel.

## Claude VERDICT

Po aplikaci 1 BLOCKING + 4 IMPORTANT z kola 10 (1 IMPORTANT částečně
přijat, částečně rozporován s zdůvodněním; 2 IMPORTANT rozporovány úplně
po přímém ověření kontextu) nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 10: Codex našel 1 BLOCKING (argv test měl chybnou indexaci -
`tail = argv[2:]` omylem zahazovalo "exec", protože `sys.argv` uvnitř
skriptu neobsahuje interpret) + 4 IMPORTANT (lifecycle snapshotu
neuklidí při chybě PŘED prvním `try`; číselný guard nezachytává českou
mezeru před "%" - kontrola procenta byla na reálném textu prakticky
mrtvá; 2× stale próza - `guide_block`/register bod a `_polish_rejected`
docstring s `[]` místo `rendered_terms`). Přijato a opraveno vše kromě
znaménka čísel (`-12`→`12`) - záměrně odmítnuto jako riziko NOVÝCH
falešných poplachů na přetížené pomlačce (rozsahy stran, vsuvky), a dvou
próza-lokací, co po přečtení v kontextu buď už měly caveat, nebo jsou
legitimní chronologický log (stejný vzorec jako všude jinde v
dokumentu). Design je teď kompletní - čeká se na kolo 11 Codexu.
