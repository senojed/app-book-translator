## BLOCKING

- Nové pravidlo není aplikováno na celý existující formulář. `guide.py:127,138` stále předvyplňuje scoutovy odhady pro vztahy a styl; `index.html:80–88` dokonce kopíruje `must_decide.default` do odpovědi vztahu. Tvrzení specu na ř. 464, že `must_decide` již používá prázdné pole, je tedy nepravdivé. Určete rozsah pravidla a požadované změny/testy pro vztahy, styl i všechny druhy `must_decide`.

## IMPORTANT

- `merge_sources` neurčuje explicitní původ zobrazené hodnoty ani samostatné zachování scoutova návrhu. Frontend musí rozlišit `guide`, `reference`, scouta a lexikografa, aby správně zamykal pole a prováděl undo. Položka stupně 1 navíc může mít současně scoutův i lexikografův návrh; spec neurčuje, zda a jak nabídnout oba.
- „Přijmout všechny“ nemá definovanou bezpečnou vratnost. Musí být určeno, že nepřepíše ručně vyplněná pole a že zpět obnoví pouze hodnoty změněné touto hromadnou akcí; jinak odporuje „původní hodnota se nikdy neztratí“.
- Klasifikace nemá výsledek pro vlastní jméno nalezené pouze case-insensitive, které zároveň překročí prahy. Není `confirmed` kvůli chybějící přesné velikosti, není `weak` podle definice „pod prahem“ a nespadá do uvedených případů `evidence_only`.

## NITS

- Ř. 29 stále tvrdí, že scoutův návrh zůstává předvyplněný; ř. 31–34 to bezprostředně ruší. Odstraňte zastaralou větu.
- Po zjednodušení nezůstaly funkční odkazy na odstraněné `coverage`, `stale`, `--limit`, `compound` ani `reference_report`; jejich zbývající výskyty jsou historická vysvětlení.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item