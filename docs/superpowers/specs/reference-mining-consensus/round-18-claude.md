# Round 18 — Claude critique

Kolo bylo zaměřené na jeden vzorec: pravidlo změněné na jednom místě, staré
znění přežívající jinde. Vyneslo **pět skutečných protimluvů**, všechny moje.

## On Codex's points

### Agreed + fixed

- **Homonyma napříč sekcemi.** Krok 0 je zakazuje (postpodmínka 5), ale sekce
  o identitě lexikografa je stále odůvodňovala tím, že „stejné jméno může být
  v `places` i `terms`". Sjednoceno: sekce je v klíči kvůli stabilitě, ne proto,
  že by homonyma byla povolená.
- **Test nevynucoval všech šest postpodmínek.** Spec tvrdil, že je test
  vynucuje, ale vyjmenovával jen čtyři. Doplněny všechny.
- **Globální pravidlo o předvyplňování vs. rozsah.** Úvod tvrdil, že se
  nepředvyplňuje ani jeden návrh, zatímco rozsah v Review UI vztahy a styl
  z pravidla vyjímá. Úvod nově mluví výslovně o **glosářových polích**.
- **`evidence_only` by nikdy nepřežilo úplný běh.** Nejostřejší nález kola:
  položka s důkazem ze stupně 0 jde do stupně 1, ten vrátí `proposed` /
  `not_attested` / `unresolved` a třídu přepíše - přitom formulář i end-to-end
  test s `evidence_only` počítají jako s konečnou. Doplněna **precedence
  klasifikace** (pět pravidel v pořadí) a řečeno, že důkazy ze stupně 0 se drží
  vždy, bez ohledu na výslednou třídu.
- **Formulace end-to-end testu odporovala vlastnímu návrhu UI.** Test žádal,
  aby se hodnota nedostala do glosáře „bez ručního vypsání", ale tlačítko
  „použít návrh" ji tam dostane bez psaní. Přeformulováno na „výslovné přijetí
  člověkem nebo ruční vypsání".

## Claude's own findings

Žádné nad rámec Codexových.

## Claude VERDICT

CONSENSUS
