# Round 2 — Claude critique

## Claude's own findings

### IMPORTANT

- **Stupeň 0 ignoruje aliasy, a tím ztrácí důkazy.** Spec říká „aliasy se netěží
  samostatně, patří k primárnímu klíči" - jenže hledá se pak jen primární povrch.
  Scout u `Harry Dresden` uvádí aliasy `Dresden`, `Harry`, `Hoss`. Když
  profesionální překlad používá `Dresden`, ale celé `Harry Dresden` skoro ne,
  stupeň 0 najde málo výskytů a položka spadne do `weak`, ačkoli je jméno
  prokazatelně ponechané. *Fix:* stupeň 0 hledá primární klíč **i všechny aliasy**;
  `Evidence` nese `matched_en` (který povrch zabral) a výskyty se sčítají přes
  všechny varianty. Aliasy zůstávají součástí jedné položky, jen rozšiřují dotaz.

### NITS

- Klasifikační tabulka a sekce „Stupně řešení" nesou podmínky duplicitně a po
  opravách se rozcházejí. Nechat podmínky jen v tabulce, ve stupních na ni odkázat.

## On Codex's points

### Agreed + fixed

- **`stole` projde i case-sensitive hledáním.** Přijímám a je to moje chyba:
  české „na stole" je malými písmeny, takže case-sensitive dotaz na `stole` ho
  najde stejně dobře. Ošetřil jsem varianty `Stole`/`STOLE`, které v textu nikdy
  nejsou. Navržený test měl chybné očekávání. Ověřeno, že `stole` v draftu
  opravdu je (jako termín „štóla"). *Oprava:* povrch začínající malým písmenem
  **nikdy** nedosáhne `confirmed` automaticky - končí nejvýš `weak` a jde před
  oči člověku. Case-sensitivita zůstává jako slabý filtr, ne jako záruka.
- **Pravidlo o `matched_cz` zabíjelo blok u `proposed`/`contradicted`.** Přijímám:
  jejich `cz` je záměrně prázdné, takže podmínka `cz == matched_cz` by metadata
  vždy zahodila a UI by nemělo co zobrazit. *Oprava:* vazba se vyžaduje jen
  u tříd s předvyplněnou hodnotou (`confirmed`, `weak`); návrhový blok se
  zobrazuje nezávisle.
- **UI reference vůbec nedostane.** Ověřeno: `build_app(draft_path, guide_path,
  on_saved)` a `run_review_server(draft_path, guide_path)` třetí zdroj nemají a
  `main.py:123` je volá po staru. *Oprava:* spec nově předepisuje `REFERENCE_PATH`,
  rozšíření obou signatur o `reference_path=None` a úpravu `_cmd_review`.
- **Predikát souvýskytu nebyl definován.** *Oprava:* přesný vzorec s poměrem
  a hraničními testy.
- **Selhaná dávka smaže dříve platné nálezy.** *Oprava:* pro položky selhané
  dávky se přebírají předchozí nálezy z existujícího `reference.json` a označí
  se `stale`.
- **Tvrzení o atomicitě reportu bylo nepravdivé.** Pád mezi dvěma `os.replace`
  přesně ten stav vyrobí. *Oprava:* report je odvoditelný artefakt, nese `run_id`
  a neshoda s daty znamená „zastaralý, spusť znovu" - žádná atomicita se netvrdí.
- **CLI a konfigurace nebyly určeny.** *Oprava:* doplněna syntaxe příkazu, všechny
  nové klíče v `config.py` a zařazení do `_MUTATING`.
- **Výstup lexikografa se nevalidoval.** *Oprava:* mapování přes normalizovaný
  klíč, odmítnutí duplicit a cizích položek, chybějící položka → `unresolved`.
- **POST by uložil bloky `reference` do `guide.json`.** Ověřeno na
  `server.py:129` (`save_guide(guide_path, payload)`). *Oprava:* server metadata
  před uložením odstraní; `guide.json` zůstává čistě lidský model.
- **Dvojí normalizace.** Ověřeno: `guide.normalize()` je `strip().lower()`,
  těžba měla mít NFC + `casefold()`. *Oprava:* jedna sdílená funkce
  `guide.normalize_key()` pro těžbu, slití i upsert v UI.
- **NITS** - escapování metaznaků, apostrofy a pomlčky, detekce začátku věty
  a zacházení s `OutputTruncated` u agenta doplněny.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex našel 3 blokující a 7 důležitých bodů, všechny ověřeny proti kódu a přijaty.
Nejzávažnější: oprava case-sensitivity z kola 1 vůbec neřešila problém, kvůli
kterému vznikla - české „na stole" je malými písmeny. Obecná slova proto nově
nikdy nedosáhnou `confirmed` automaticky. Dále: pravidlo o vazbě důkazu zabíjelo
metadata u návrhů, UI nemá kudy reference dostat, a POST by metadata uložil mezi
lidská rozhodnutí. Claude přidal jeden důležitý bod: stupeň 0 nehledá aliasy,
a přichází tak o důkazy u jmen, kde překlad používá zkrácenou podobu.
