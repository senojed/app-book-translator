## BLOCKING

- **Řádky 446–450, 490–495 — oprava `corpus_fresh` z kola 6 není ve specu provedena.** Text stále požaduje porovnání s manifestem uloženým v cache, tedy dvou historických údajů. Navíc `merge_sources(draft, guide, reference)` ani `build_app(..., reference_path=...)` nedostávají `REFERENCE_DIR` či aktuální manifest. Definovat výpočet aktuálního manifestu přes `os.stat` a jeho předání do merge vrstvy.

- **Řádky 195, 240–247, 581–588 — alias-only pravidlo si odporuje.** Rozhodnutí říká nikdy nepředvyplnit `cz` ani `render`; tabulka tvrdí, že každý `weak` předvyplňuje `cz`, a test stále povoluje staré pravidlo „alias je slovem primárního povrchu“. Test i klasifikační kontrakt musí jednoznačně vyžadovat prázdné `cz` a `render` pro každý alias-only nález.

- **Řádky 212–236 — `canonical_items` neřeší související data.** Rozdělit pouze klíč nestačí. Složené položky mají složené `suggested_cz`, aliasy a někdy `must_decide.scope_key`. Stávající `apply_must_decide` pak původní složený klíč znovu vloží jako nový řádek. Není definováno ani mapování existujícího `guide.json`. Kanonizace musí vracet mapování původní položky na potomky a určit migraci návrhů, aliasů, `must_decide` a lidských rozhodnutí.

- **Řádky 215–220 — předpoklad „dva povrchy = dva záznamy v glosáři“ neodpovídá existujícímu rozhraní.** `glossary._seed_one` slučuje nový kanonický povrch s existujícím aliasem a následně přepisuje `canonical_en`, `cz` a `type`. Konkrétně `Billy Borden` již obsahuje aliasy `Billy` a `Will`; rozdělené řádky `Will` a `Billy` proto mohou podle pořadí přepsat jeho schválenou hodnotu. Je nutné sladit identitu kanonizovaných položek se `seed_from_guide` a přidat end-to-end test aliasových kolizí.

## IMPORTANT

- **Řádky 159–175 — nový prefixový matcher má zjevné falešné shody.** Pro čtyřpísmenné dotazy porovnává jen tři znaky: `práh` se shoduje s běžným slovem `práce`, `rada` s `radost`. Souvýskyt po celých knihách tyto chyby spíše potvrdí. Matcher potřebuje vyhodnocení na reálném korpusu a konzervativnější pravidlo nebo explicitní koncovky.

- **Řádky 430–445 — freshness nesmí potlačit lidský `guide`.** Formulace „`cz` i `render` se použijí jen když sedí všechny tři“ odporuje prioritě `guide > reference > draft`. Výslovně určit, že freshness omezuje pouze hodnoty a důkazy pocházející z `reference`; uložená lidská rozhodnutí zůstávají vždy.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item.