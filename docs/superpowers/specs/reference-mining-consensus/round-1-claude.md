# Round 1 — Claude critique

## Claude's own findings

### BLOCKING

- **`scan` tiše smaže výsledek těžby.** `main.py:105` volá
  `guide_mod.save_draft(GUIDE_DRAFT_PATH, result)` — přepíše draft celý. Kdo po
  `reference` pustí `scan` znovu (třeba s `--chunked`), přijde o všechno vytěžené
  bez varování. Spec pořadí příkazů popisuje, ale tuhle interakci neřeší.
  *Fix:* těžba nesmí žít jen v draftu. Zapisovat ji do vlastního souboru
  `data/reference.json`, který `scan` nemá důvod přepisovat, a slévat ji do
  podkladu pro UI až v `merge_draft_and_guide`. Vedlejší efekt: opakovaná těžba
  je pak triviálně idempotentní (soubor se nahradí celý).

### IMPORTANT

- **EN korpus se načítá, ale k ničemu se nepoužívá.** Stupně 0 i 1 sahají jen na
  CZ stranu. Načíst 1,2 M slov navíc do paměti a do cache je čirá režie — buď to
  zahodit, nebo z toho mít užitek. Užitek existuje: EN strana umožní ověřit, že
  se navržený český tvar vyskytuje **právě v těch dílech**, kde je v originále
  příslušný anglický termín. To je ta chybějící vazba, kterou Codex vytýká ve
  svém třetím blokujícím bodu.
- **Prahy ztrácejí smysl, jakmile `confirmed` smí vzniknout jen ze stupně 0.**
  Tabulka klasifikace to po opravě musí říct znovu a jinak.
- **Riziko falešného „ponecháno" u krátkých jmen, která jsou českými slovy.**
  Pravidlo rozlišuje jen podle velikosti prvního písmene povrchu, ne podle
  pozice ve větě. Jméno `Bob` na začátku české věty je nerozeznatelné od luštěniny.
  U `stole` to řeší malé písmeno, tady ne. *Fix:* u povrchů kratších než 5 znaků
  vyžadovat výskyt i mimo začátek věty.

### NITS

- Spec tvrdí „ověřeno: všech 20 souborů se načte", ale neuvádí, že kapitoly
  nesedí kvůli členění EPUBu — to je dál v textu. Spojit na jedno místo.

## On Codex's points

### Agreed + fixed

- **`merge_draft_and_guide` zahazuje vytěžená pole** — ověřeno v `guide.py:93`
  (`"cz": g.get("cz") or ""`) a `:111` (čte jen `suggested_cz`). Spec nově
  definuje přesné schéma a předepisuje změnu funkce včetně testů.
- **Neověřený návrh by se dostal do glosáře.** Ověřeno: validace kontroluje jen
  neprázdnost, `review` pak seeduje. Barevné zvýraznění tomu nezabrání. Spec nově
  nechává `cz` u neověřených **prázdné**; návrh se ukazuje jen jako text vedle
  pole. Tím je invariant vynucen mechanicky, ne kázní uživatele.
- **Globální výskyt neprokazuje překladový vztah.** Nejsilnější bod recenze a
  přijímám ho celý. „Rada" je běžné české slovo; počet výskytů o vazbě na
  *White Council* nevypovídá. Spec nově: `confirmed` smí vzniknout **jen ze
  stupně 0** (anglický povrch doslova v českém textu — to je přímý důkaz).
  Návrhy modelu končí nejvýš jako `proposed` a vždy jdou před oči člověku.
  Navíc přibyl doložitelný test souvýskytu přes EN stranu korpusu.
- **Důkaz nebyl svázán s hodnotou, ke které patří.** Blok `reference` nově nese
  `matched_cz`; liší-li se od zobrazované hodnoty, UI důkaz nezobrazí.
- **Duplicitní čísla dílů, minimální korpus** — spec nově odmítá dvojznačné
  číslování a vyžaduje minimální počet spárovaných dílů.
- **Platnost cache** — nově klíčovaná schéma verzí, kořenem a velikostmi/časy
  souborů; při neshodě se staví znovu.
- **Idempotence opakovaného běhu** — vyřešeno vlastním souborem místo připisování
  do `note` (viz můj blokující bod). `note` se už nemodifikuje vůbec.
- **Sémantika hledání** — spec nově předepisuje NFC normalizaci, hranice slov
  přes Unicode a chování pro každou délku povrchu včetně tříznakových.
- **Tvar odpovědi agenta** — ověřeno, `extract_json` regexem `\{.*\}` vrací jen
  objekt. Spec nově předepisuje obálku `{"proposals": [...]}`.
- **Identita povrchu** — nově `(sekce, normalizovaný klíč)`, s pravidlem pro
  aliasy a kolize napříč sekcemi.
- **Atomicita reportu** — report se zapisuje až po úspěšném zápisu dat.
- **Rozpor „nesahá na DB vůbec"** — pravda, `create_run`/`finish_run` a
  `llm_calls` do DB píšou. Formulace opravena a doplněn výčet tabulek.
- **Chybějící end-to-end test** — doplněn do testovací sekce.

### Disagreed

Nic. Všechny body obstály při ověření proti kódu.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex našel 4 blokující a 9 důležitých bodů; všechny ověřeny proti kódu a přijaty.
Claude přidal jeden blokující (opakovaný `scan` přepíše draft a smaže těžbu) a tři
důležité (nevyužitý EN korpus, prahy po opravě ztrácejí smysl, krátká jména jako
česká slova). Zásadní změny: výsledek těžby se stěhuje z draftu do vlastního
`data/reference.json`, `confirmed` smí vzniknout jen z deterministického stupně 0,
neověřené návrhy nechávají `cz` prázdné. Sporných bodů nezůstalo žádných.
