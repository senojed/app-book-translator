# Round 5 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu. Nezávislý průchod přes zbylé
nedotčené Tasky (1, 6, 12) tohle kolo Codexovy IMPORTANT body sám
potvrdil dřív, než jsem si přečetl jeho verdikt na `rendered_terms`
spor (viz níž - dospěl jsem ke stejnému závěru nezávisle při ověřování
`_finding_summary`/exportu).

## On Codex's points

### Agreed + fixed
- **IMPORTANT - nález lze zobrazit, ale nelze uložit (`issue: 123` typu):**
  ověřeno přímo v `src/agents/critic.py:45` (`raw.get("issue") or ""`
  čte z LLM JSON bez typové kontroly). Kolo 4 moje defenzivní `str()`
  coerce byla JEN v `render_findings_html` (display-time) - nepomohla
  by, protože blokující bod je SAVE validace (`_valid_finding_shape`),
  ne zobrazení. Oprava přesunuta na skutečný choke-point -
  `findings.assign_ids` teď normalizuje VŠECHNA string pole (`source`/
  `type`/`issue`/`severity`/`cz_excerpt`/`suggestion`) hned při vzniku
  nálezu, ne až při zobrazení.
- **IMPORTANT - `rendered_terms` sjednocení (revize mého kola-4
  nesouhlasu):** Codex dal KONKRÉTNÍ reprodukovatelný scénář (schválený
  tvar termínu "zapomenutý" jen v živé DB, ale platný podle historie -
  kontrola s prázdnou množinou nahlásí slabý `omission/minor` tam, kde
  by se STEJNÝM vstupem jako zápis viděla `inconsistency/critical`) a
  ukázal, že `_commit_polish_result`'s `rendered_terms` volba OVLIVŇUJE
  živou DB přes `concordance.build_mentions`, ne jen archiv. To je
  silnější důkaz, než jsem měl v kole 4 (kdy jsem to hodnotil jako
  kosmetickou nekonzistenci) - MĚNÍM POZICI. `_polish_one_chapter`
  dostal volitelný `rendered_terms` parametr, dávka (Task 5) a
  regenerace (Task 10) ho teď počítají JEDNOU a předávají STEJNOU
  hodnotu do analýzy i zápisu.
- **IMPORTANT - Task 13 migrace: tolerance na historii nefunguje:**
  ověřeno - `polish_store.load_history`'s schema validace běží PŘED
  skriptovou vlastní tolerancí, takže `[null]` uvnitř `findings` nechá
  CELÝ soubor neúspěšně načíst, dřív než se k tomu skript dostane.
  Přeuspořádáno - historie se zkouší načíst JAKO PRVNÍ (před jakýmkoli
  zápisem), selhání = čistý STOP bez zápisu, ne poloviční migrace.
  Opravena i mrtvá porovnávací podmínka (`entry["findings"] = valid`
  PŘED porovnáním se sebou samým).
- **IMPORTANT - `error` status nezaručuje `translated_text`:** ověřeno
  (potvrzeno i vlastním nezávislým průchodem). Task 10 (regenerate)
  teď navíc kontroluje `translated_text is not None` - Task 9 (save)
  tohle už měl zadarmo (typová validace `cz_before` odmítne `null`).
  Task 14 (`lockEditor`) dostal stejnou kontrolu na klientské straně.
- **IMPORTANT - export obchází bezpečné parsování nálezů:** ověřeno -
  `_finding_summary` (main.py, EXISTUJÍCÍ funkce) má vlastní ruční
  parsování, co spadne na `notes='null'/'42'/'[null]'` - `except`
  pokrývá jen `json.loads`, ne následnou iteraci. Jedna taková
  `flagged` kapitola by shodila export CELÉ knihy. Přepsáno na sdílené
  `_parse_findings`.
- **NIT - merge důsledky nezdokumentované:** souhlas, opraven zastaralý
  docstring v `build_findings_report` (tvrdil "polish/editor nahradí
  run nálezy", teď akumulace).
- **NIT - "NIKDY nic nemaže" potřebuje předpoklad platných id:** souhlas,
  doplněn invariant (nálezy bez `id` z DOBY PŘED migrací by se z merge
  tiše ztratily - motivace, proč migraci (Task 13) spustit VČAS).
- **NIT - Task 9 outer try/except - "nepovažuji to za IMPORTANT":**
  potvrzeno, žádná další akce (shoda s mým kolem-4 rozhodnutím, i když
  Codex nesouhlasí s mým zdůvodněním "jen katastrofické selhání disku"
  - přesto se mnou souhlasí na výsledné prioritě).

## Claude VERDICT

CHANGES_NEEDED (5 reálných IMPORTANT oprav, žádné BLOCKING tohle kolo -
poprvé)

## Summary for log

Kolo 5 bylo první BEZ blokující chyby - jen IMPORTANT. Nejvýznamnější
posun: přehodnotil jsem vlastní kolo-4 nesouhlas o `rendered_terms`
poté, co Codex dodal konkrétní, ověřitelný scénář místo obecného
tvrzení - správný postup je změnit názor, když se objeví lepší důkaz,
ne trvat na dřívějším rozhodnutí. Zbytek oprav byl mechanický (chybějící
normalizace na jednom choke-pointu, mrtvý kód v migračním skriptu,
existující-ale-křehká funkce `_finding_summary`, co dosavadní kola
nezkontrolovala).
