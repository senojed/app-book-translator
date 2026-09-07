## BLOCKING

- **Řádky 197–213 — kanonizace složených položek je datově chybná.** `White Court / Red Court / Vampire Courts` ani `Flickum bicus / Forzare / Aparturum` nejsou aliasy jedné entity; potřebují samostatné překlady. Zachování jediného `surface`, jednoho `cz` a jednoho řádku v UI/glosáři problém neřeší. Navíc sloučení obrácených duplicit nelze současně provést a zachovat oba původní řetězce jako klíče. Rozdělit skutečné výčty na samostatné položky; jako aliasy slučovat pouze synonyma a explicitně definovat mapování původních ID na výsledné položky.

- **Řádky 190–195 — refinement pro alias-only předvyplnění je stále neplatný.** Výskyt `Dresden` nedokládá hodnotu `Harry Dresden` ani rozhodnutí `render=keep`; překlad může zachovat příjmení a lokalizovat křestní jméno. Při `cz="Harry Dresden"` navíc selže vlastní vazba `cz == matched_cz`; při `cz="Dresden"` jde o chybnou hodnotu celé položky. Alias-only nález nesmí předvyplnit `cz` ani `render`; má být pouze zobrazen jako podpůrný důkaz.

## IMPORTANT

- **Řádky 158–164 — prefixový matcher nesplňuje deklarovanou podporu skloňování.** `Bílá rada` se podle uvedeného algoritmu nespáruje s `Bílé radě`: první dvojice sdílí jen tříznakový prefix a čtyřznakové `rada` musí sedět přesně. Upravit matcher nebo přiznat přesné hledání krátkých slov a doplnit konkrétní pozitivní test této dvojice.

- **Řádky 428–432 — kontrola `corpus_fresh` může porovnávat dva historické údaje.** Shoda fingerprintu v `reference.json` s manifestem uloženým ve stejné cache nezjistí pozdější změnu EPUBů. Při review levně znovu sestavit aktuální manifest pomocí seznamu souborů, velikostí a mtime, včetně rootu, a teprve ten porovnat; EPUBy není nutné parsovat.

## NITS

- **Řádek 15 — počet nesedí.** `54 + 59 + 19 = 132`, nikoli 121.
- **Řádky 416–432 — výstupní schéma čerstvosti není jednotné.** Příklad obsahuje jen `fresh`, zatímco text a testy vyžadují tři samostatné příznaky. Vyjmenovat přesná pole a případný odvozený agregát.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item.