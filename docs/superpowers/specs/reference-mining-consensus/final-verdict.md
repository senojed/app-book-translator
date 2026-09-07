# Plan-consensus — finální verdikt

**Výsledek: CONSENSUS** (kolo 23 z 23)

Oba kritici vyhlásili `CONSENSUS` ve stejném kole. Nedořešené ani sporné body
žádné.

## Průběh

| Kola | Formát | Charakter nálezů |
|---|---|---|
| 1-10 | standardní křížová kritika | věcné chyby návrhu; skončilo MAX_ROUNDS s 0 nedořešenými |
| 11 | **čerstvé oči** (bez historie, s otázkou na proporce) | 3 blok. + 13 důl. + 5 o překombinovanosti; spec 619 → 484 řádků |
| 12 | **zkouška proveditelnosti** (psát z toho plán, vést seznam dohadů) | invariant byl v rozporu s chováním existujícího kódu |
| 13-17 | standardní | vady v datech draftu, postupně 4 → 7 → 5 → 1 → 1 |
| 18 | **sonda na protimluvy** | 5 protimluvů |
| 19-21 | ověření předchozí opravy | každé kolo našlo defekt zavedený opravou z předchozího |
| 22-23 | standardní | 1 → 0; shoda |

## Co smyčka změnila

**Zjednodušení.** Kolo 11 zrušilo tři podsystémy (editor složených položek,
per-položkovou obnovu po selhání, morfologický matcher) a spec zkrátilo
o pětinu. Příčinou složitosti byla vadná data draftu, ne obtížnost úkolu -
levnější bylo přidat jednorázovou normalizaci než stavět aparát kolem vady.

**Dvě chyby, které by prošly do kódu.** Invariant specu byl v rozporu s tím, co
formulář dělá už dnes (`guide.py:92,111` předvyplňují modelové odhady).
A obecné slovo `stole` se předvyplňovalo a zároveň nedostávalo do stupně 1 -
nejhorší možná kombinace.

**Tři neúspěšné pokusy napsat český matcher od stolu**, všechny vyvrácené
měřením na skutečném korpusu. Spec u něj proto nepředepisuje algoritmus, ale
přejímací kritéria s číselným prahem.

## Poučení k procesu

- **Změna formátu kola vynesla víc než opakování téhož.** Kola 11, 12 a 18
  (čerstvé oči / zkouška proveditelnosti / sonda na protimluvy) našla dohromady
  víc než šest standardních kol kolem nich.
- **Oprava je nejrizikovější operace smyčky.** Kola 19-21 našla pokaždé defekt
  zavedený opravou z předchozího kola. Od kola 7 se proto každá změna specu
  ověřuje grepem, od kola 9 se dělá inventura proti logu rozhodnutí, a od kola
  19 každé kolo nejdřív kontroluje předchozí opravu.
- **Dvakrát se ukázalo, že ohlášená oprava se do dokumentu vůbec nezapsala**
  (textová náhrada neseděla na vzor změněný dřívějším kolem).
- **Konsolidační přepis ztratil tři dříve přijatá rozhodnutí.** Odhalila to až
  cílená inventura proti logu, ne čtení dokumentu.

## Otevřené otázky - patří měření, ne oponentuře

- prahy `REFERENCE_MIN_HITS` / `MIN_BOOKS` pro `confirmed`
- `REFERENCE_COOCCUR_RATIO` pro souvýskyt
- jestli je přesná shoda ve stupni 1 příliš přísná

Všechny tři jsou levně změnitelné v `config.py` a první běh je má rozhodnout.
