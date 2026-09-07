# Round 3 — Claude critique

## Claude's own findings

### BLOCKING

- **Spec si protiřečí v hranicích modulů.** Tabulka říká, že `src/reference.py`
  „nezná `guide`", a o dva odstavce dál mu ukládá volat `guide.normalize_key()`.
  Buď hranice, nebo funkce. *Fix:* normalizace je obecná textová operace, ne
  součást návodu - stěhuje se do nového `src/textnorm.py` (bez závislostí),
  odkud ji berou `guide`, `reference` i `review_ui`. Tabulka hranic se opraví.

### IMPORTANT

- **`--limit` nesmí omezovat stupeň 0.** Stupeň 0 je zdarma a deterministický;
  omezovat ho nemá důvod a jen by to vyrobilo nekompletní data. *Fix:* `--limit`
  se vztahuje výhradně na stupeň 1 (tedy na počet povrchů poslaných modelu).

### NITS

- Sekce „Stupně řešení" a klasifikační tabulka nesou podmínky duplicitně; po
  třech kolech oprav se rozcházejí. Podmínky nechat jen v tabulce.

## On Codex's points

### Agreed + fixed

- **Agregace aliasů je nedomyšlená.** Přijímám celé. Překryv `Harry Dresden`
  a `Dresden` započítá tentýž výskyt dvakrát; krátký alias by obešel délková
  omezení primárního povrchu; a nález aliasu neprokazuje, že byl ponechán
  primární tvar. *Oprava:* důkaz se vede **po jednotlivých tvarech**, výskyty se
  sčítají jako sjednocení rozsahů (žádné dvojí započtení), způsobilost ke
  `confirmed` se posuzuje u každého tvaru zvlášť, a `confirmed` vyžaduje doložení
  **primárního** povrchu. Doložený jen alias → `weak` s uvedením, který tvar zabral.
- **Identita vs. `propose()`.** Přijímám: dvě položky téhož jména v `places`
  a `terms` nelze spárovat přes `term_en`. *Oprava:* dotaz i odpověď nesou
  `id = "{section}/{normalizovaný klíč}"` a validace jde přes něj.
- **`write_reference` nerozliší selhání od `unresolved`, `--limit` maže data.**
  Přijímám, je to díra po mé vlastní opravě z kola 2. *Oprava:* `resolve()` vrací
  strukturu s `attempted` / `failed` / `not_attempted`; `write_reference` slévá
  s předchozím souborem podle těchto množin, `stale` je součástí schématu,
  a položky, které v aktuálním draftu už nejsou, se odstraní.
- **Délkové pravidlo si protiřečí s testem `Mab`.** Přijímám - je to můj rozpor.
  *Oprava:* délka omezuje jen povrchy začínající **malým** písmenem. Vlastní
  jméno od 3 znaků výš smí být `confirmed`, pokud projde pravidlem o začátku
  věty. 1-2 znaky nikdy. Tabulka, pravidla i testy sjednoceny.
- **Čerstvost reference vůči draftu.** Přijímám: opakovaný `scan` může změnit
  klíče i aliasy a `run_id` čerstvost neprokazuje. *Oprava:* `reference.json`
  nese fingerprint draftu, manifestu korpusu a prahů; při neshodě UI reference
  označí jako zastaralou a číselné důkazy nezobrazí.
- **`contradicted` je věcně chybné označení.** Nejlepší bod tohohle kola.
  Čeština skloňuje - zavedený termín se v nominativu vyskytovat nemusí, a přesné
  hledání jediného tvaru ho pak „vyvrátí", ačkoli v textu běžně je. *Oprava:*
  třída se přejmenovává na `not_attested` („v tomhle tvaru nedoloženo"), nikoli
  vyvrácení. Navíc se hledání na CZ straně opře o **už existující**
  `concordance.find_form_occurrences`, které porovnává na kmeni a skloňování
  snese; nevymýšlí se nová morfologie.
- **Postavy invariant obcházejí.** Přijímám a je to vážné: validace dovoluje
  prázdné `cz`, když `render == keep`, UI má `keep` jako výchozí a
  `seed_from_guide` pak vloží anglické jméno do glosáře. Nedoložená postava by
  tak prošla i s prázdným polem. *Oprava:* u postav s třídou `proposed` /
  `not_attested` se `render` nepředvyplňuje a UI vyžaduje **aktivní volbu**;
  bez ní validace neprojde.
- **Schéma `reference.json` a jeho načítání.** *Oprava:* doplněn přesný tvar
  souboru a `load_reference()` s chováním pro chybějící, poškozený i
  nepodporovaný soubor.
- **`ValueError` vs `FatalRunError`.** *Oprava:* modul vyhazuje `ValueError`,
  převod na `FatalRunError` dělá `_cmd_reference`; pokryto testem, že se výstup
  zachová.
- **Začátek věty přes hranice dokumentů.** *Oprava:* díly se skládají
  z dokumentů s explicitním oddělovačem, který se počítá jako začátek věty.
- **NITS** - „idempotentní" nahrazeno za „neakumuluje předchozí výstup";
  názvy `matched_en` (dotazovaný anglický tvar) a `matched_cz` (doložený český
  tvar) sjednoceny, `Evidence.matched` zrušeno.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex našel 4 blokující a 6 důležitých bodů, všechny přijaty. Nejcennější je
námitka proti třídě `contradicted`: čeština skloňuje, takže nenalezení jednoho
konkrétního tvaru návrh nevyvrací - třída se přejmenovala na `not_attested`
a hledání se opře o existující kmenové porovnání v `concordance`. Dále: agregace
aliasů dvojitě počítala výskyty a nález aliasu se vydával za doložení primárního
tvaru; postavy obcházely invariant přes `render=keep` s prázdným `cz`; `--limit`
by smazal data mimo limit. Claude přidal blokující rozpor ve vlastní tabulce
hranic (`reference.py` nezná `guide`, ale volá `guide.normalize_key`) - řeší se
novým `src/textnorm.py`.
