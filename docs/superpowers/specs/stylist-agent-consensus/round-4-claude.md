# Round 4 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní - Codex round 4 pokryl to podstatné)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
(žádné vlastní)

## On Codex's points

### Agreed + fixed
- **BLOCKING - `critic.review()` pořád fail-open pro netypový `findings`:**
  přidán `isinstance(raw_findings, list)` guard - netypová hodnota (string,
  číslo) se teď bere jako rozbitá odpověď (retry, pak výjimka), ne
  `AttributeError` z iterace po znacích. Řádky v `findings`, co nejsou
  dict, se přeskočí místo pádu.
- **IMPORTANT - `--ephemeral`/session historie:** OVĚŘENO přímo (`codex
  exec --help` v tomhle prostředí) - flag existuje ("Run without
  persisting session files to disk"). Přidán do příkazu. Navíc ověřeno,
  že `[PROMPT]` čte ze stdin, když je pozicionální argument `-` - celý
  vstupní mechanismus přepsán ze souboru na stdin (`subprocess.run(...,
  input=prompt_text)`), což ZÁROVEŇ řeší i limit délky argv elegantněji
  (žádný teoretický strop) a přidává bonus k privacy (text knihy se
  nikdy nezapíše jako čitelný soubor na disk).
- **IMPORTANT - baseline srovnání ze zastaralých `notes` vs. aktuální
  glosář, klíč bez `actual` hodnoty:** `_polish_rejected` teď dostává
  ČERSTVĚ přepočítanou baseline (`concordance.check_chapter(en, cz, ...)`
  volané přímo v `_polish_one_chapter`, se STEJNÝM `glossary_rows` jako
  `after_findings`) - žádná závislost na tom, co bylo uloženo dřív pod
  jiným glosářem. Klíč pro srovnání teď zahrnuje `actual` hodnotu
  (`_finding_key`), ne jen `(type, term_id)`.
- **IMPORTANT - preflight jen executable, ne auth/model:** vědomě
  zúženo (viz Disagreed), ale doplněno o nenulový exit kód `_cmd_polish`,
  když VŠECHNY kapitoly v dávce selžou - programově zjistitelný symptom.
- **NIT - `--only` tiše přeskakuje chybějící/nevyhovující kapitoly:**
  opraveno, hlásí přeskočené (stejný vzor jako `run --only`), i zvlášť
  pro "už stylizováno bez --force".
- **NIT - markdown fence by mohl projít jako "minor formátování":**
  deterministická kontrola v `stylist.polish` (`styled.startswith("```")`
  atp.) - explicitní odmítnutí, ne spoléhání na poslušnost promptu.

### Agreed but already addressed
(žádné - kolo 4 nálezy jsou nové)

### Disagreed (s odůvodněním)
- **IMPORTANT - deterministická kontrola čísel/dat/jmen:** Nesouhlasím s
  rozsahem. `check_meaning_preserved` (vrstva 3) už výslovně zahrnuje
  "čísla" v seznamu kontrolovaných kategorií - je to LLM kontrola místo
  deterministické extrakce, ale to je KONZISTENTNÍ s tím, jak CELÁ zbylá
  pipeline (translator, kritik) řeší správnost - nikde jinde v aplikaci
  není deterministická extrakce/porovnání číslovek/dat napříč přirozeným
  textem. Budovat spolehlivý extraktor by byla vlastní netriviální NLP
  úloha (falešné pozitivy z přeformátování "5" vs. "pět" atd.), mimo
  rámec téhle funkce.
- **IMPORTANT - žádná verifikace, že se styl SKUTEČNĚ zlepšil:**
  Nesouhlasím s rozsahem. Automatizovaný "je to lepší?" LLM soudce je sám
  subjektivní/nespolehlivý, přidal by další placené volání na kapitolu a
  je mimo explicitní zadání (ochrana proti halucinaci, ne kvalitativní
  brána). Uživatel zůstává posledním soudcem - přesně jako u PRVNÍHO
  pilotního běhu v týhle konverzaci, kde on sám přečetl a posoudil
  výstup, ne automat.
- **IMPORTANT - `term_mentions` rebuild ztrácí "rendered" provenienci:**
  Souhlasím s DIAGNÓZOU (stylista nemá `cz_as_used` mechanismus jako
  translator, takže "rendered" zdroj nejde věrně reprodukovat), ale
  nesouhlasím, že jde o něco, co lze v rozsahu téhle funkce plně opravit.
  Plná oprava vyžaduje buď novou state.py funkci pro čtení mentions JEDNÉ
  kapitoly (dnes neexistuje - `chapters_mentioning_term`/`all_term_mentions`
  jsou agregátní přes VÍC kapitol), nebo mechanismus sebehlášení pro
  stylistu (nová schopnost, kterou návrh Codexu z Task 12/13
  reference-mining plánu nikdy neřešil ani pro translator jinak než
  přes vlastní strukturovaný výstup). Zdokumentováno jako vědomě přijatý,
  METADATOVÝ (ne signálový) kompromis - termín zůstává nalezitelný ve
  VĚTŠINĚ případů, protože všechny tři vrstvy kontroly hlídají, že se
  zavedené termíny nemění.
- **Preflight bez skutečné kontroly přihlášení/modelu:** Souhlasím, že
  preflight NEODHALÍ špatné přihlašovací údaje/nepodporovaný model
  předem - ale skutečná kontrola by vyžadovala placené volání Codexu jen
  na "je systém v pořádku?", což je proti duchu "polish nesmí stát nic
  navíc, když se nic neděje". Nenulový exit kód při "všechno selhalo" je
  vědomě zvolený, levnější kompromis - detekuje symptom BEZ nutnosti
  platit za preflight.

## Claude VERDICT

Po aplikaci opravitelných bodů (1 BLOCKING + 4 IMPORTANT + 2 NITS) a
zdokumentovaném zúžení zbylých 3 IMPORTANT bodů (čísla/data, kvalita stylu,
term_mentions provenience - všechny s konkrétním technickým zdůvodněním,
proč jde o vědomý kompromis, ne přehlédnutí) nenacházím ve vlastním čtení
nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 4: Codex našel 1 nový BLOCKING (`critic.review()` pořád fail-open pro
netypový `findings`) a 6 IMPORTANT + 2 NITS. Klíčová změna: OVĚŘENO přímo
v tomhle prostředí (`codex exec --help`), že existuje `--ephemeral` flag a
že prompt jde číst ze stdinu (`-`) - design přešel z "vstup přes soubor" na
"vstup přes stdin", což je čistší, bez teoretického argv limitu, a lépe
chrání soukromí (žádný plaintext soubor s textem knihy na disku).
`_polish_rejected` teď počítá baseline ČERSTVĚ (ne ze starých `notes`) se
STEJNÝM aktuálním glosářem a bohatším klíčem (`actual` hodnota). 3 body
(deterministické číslo/datum kontroly, automatizovaná kvalitativní
verifikace, plná term_mentions provenience) zůstávají vědomě mimo rozsah s
explicitním zdůvodněním - ne kvůli lenosti, ale kvůli konzistenci s
existující architekturou a hranicím zadání. Design je teď kompletní - čeká
se na kolo 5 Codexu.
