# Round 11 — Claude critique (čerstvé oči, bez logu)

Formát kola byl změněn schválně: Codex dostal spec bez historie a s výslovnou
otázkou na proporce. Vyneslo to 3 blokující, 13 důležitých a 5 nálezů
o překombinovanosti - víc než tři předchozí kola dohromady.

## Claude's own findings

### BLOCKING

- **Validace kolizí z kola 8 by znemožnila uložení formuláře.** Ověřeno na
  reálném draftu: **15 kolizí**, ne jedna. `Morgan`/`Donald Morgan`,
  `Thomas`/`Thomas Raith`, `Karrin Murphy`/`Murphy`, `Rashid`/`the Gatekeeper`,
  `Will`/`Billy Borden` a další. Většina jsou **duplicity od scouta** - táž
  entita vedená dvakrát. Moje pravidlo „kolize = chyba validace" by uživateli
  zabránilo uložit cokoli, dokud ručně nesrovná patnáct dvojic v UI, které na
  kanonická jména nemá ani editaci, ani mazání.

### Zásadní důsledek

Codexovy nálezy o překombinovanosti a většina jeho „důležitých" bodů mají
**společnou příčinu**: draft od scouta má vadná data (11 výčtů + 15 duplicit)
a spec kolem té vady postavil tři podsystémy - editor složených položek,
přemapování otázek a validaci kolizí. Odstranit příčinu je levnější než
obsluhovat následek.

Přijímám proto Codexovo doporučení a rozšiřuji ho: **jednorázová normalizace
draftu jako samostatný krok před těžbou.** Tím padá 8 z 13 „důležitých" nálezů,
protože se ptají na kontrakty podsystémů, které přestanou existovat.

## On Codex's points

### Agreed + fixed (BLOCKING)

- **Stupeň 0 nedokazuje ponechání u obecných slov, a přesto předvyplňuje.**
  Přijímám, je to díra, kterou jsem si sám nechal: `stole` skončí jako `weak`,
  `weak` předvyplňuje, a položka se navíc do stupně 1 už nedostane. *Oprava:*
  shoda obecného slova je **jen důkaz** (`cz` prázdné) a položka **zůstává
  způsobilá pro stupeň 1**.
- **Case-insensitive shoda může dát `confirmed` na nesouvisejícím slově.**
  *Oprava:* `confirmed` vyžaduje alespoň jeden výskyt shodný **i ve velikosti
  písmen** s hledaným povrchem.
- **Validace kolizí blokuje uložení** - viz můj nález výše. *Oprava:* validace
  se ruší, kolize řeší normalizace draftu; ve formuláři zůstane jen varování.

### Agreed + fixed (OVER-ENGINEERED - všechny čtyři přijaty)

- **Editor složených položek** → zrušen, nahrazen normalizací draftu.
- **`stale`, čtyři stavy `coverage`, obnova po položkách, `--limit`** → zrušeno
  ve prospěch **atomického selhání**: selže-li cokoli, předchozí
  `reference.json` zůstane a spustí se znovu. Celý běh stojí ~$0.15.
- **Tři příznaky čerstvosti** → jeden `fresh`.
- **Morfologie v kontraktu B, fixture 40 dvojic, checkpoint na 20 dotazech** →
  zrušeno. Stupeň 1 nikdy nic nepředvyplňuje, takže tolerance skloňování kupuje
  málo. Nahrazeno **přesnou shodou celého slova**, výslovně označenou jako slabý
  důkaz. Tím padá i tříkolová sága s matcherem.
- **`reference_report.md`** → zrušen, souhrn na konzoli.

### Agreed + fixed (IMPORTANT, které přežily zjednodušení)

- **Invariant byl formulovaný nepravdivě** - člověk může návrh opsat ručně.
  Přeformulován na „žádná nedoložená hodnota se **nepředvyplní automaticky**".
- **`books_with_en` neměl kontrakt** - doplněn (kontrakt A na EN straně,
  case-insensitive, bez pravidla o začátku věty).
- **Duplicitní položky se konsolidovaly jen před těžbou, `merge_sources` dostával
  původní draft** - po normalizaci draftu problém zaniká.
- **Částečné selhání EPUBu** - doplněno: selže-li jedna strana dvojice, vypadne
  celý díl a kontrola minima běží až potom.
- **Guard v glosáři „nahlásí konflikt", ale funkce nic nevrací** - doplněno,
  že vrací seznam konfliktů, který CLI vypíše.

### Agreed (NITS)

`klasifikace` → `classification`; detekce `" or "` normalizovaná; otisk prahů
jen z hodnot, které ovlivňují důkaz.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Změna formátu kola se vyplatila: fresh-eyes review bez logu našel víc než tři
předchozí kola dohromady. Nejzávažnější je nález, který jsem ověřil a rozšířil -
validace kolizí z kola 8 by znemožnila uložit formulář, protože reálný draft
obsahuje 15 kolizí, ne jednu, a většinou jde o duplicity od scouta.

Z toho plyne zásadní obrat: příčinou většiny složitosti specu jsou vadná data
draftu (11 výčtů + 15 duplicit), kolem nichž spec postavil tři podsystémy.
Nově se draft **jednou normalizuje** a podsystémy se ruší. Přijaty všechny čtyři
nálezy o překombinovanosti: pryč je `stale`, čtyři stavy `coverage`, `--limit`,
tři příznaky čerstvosti, morfologie v kontraktu B i samostatný report.

Opraveny dvě reálné chyby ve stupni 0: obecné slovo předvyplňovalo a zároveň se
nedostalo do stupně 1; case-insensitive shoda mohla dát `confirmed`.
