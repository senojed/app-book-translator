# Round 13 — Claude critique

## On Codex's points

### Agreed + fixed (BLOCKING)

- **Nové pravidlo nebylo aplikováno na celý formulář, a spec o tom lhal.**
  Ověřeno v kódu: `guide.py:127` předvyplňuje `address` ze scoutova `suggested`,
  `guide.py:138` styl ze `style_notes`, a `index.html:80-88` předvyplňuje
  i odpověď na vztahovou otázku z `md.default` - vlastní komentář v tom souboru
  přitom říká „schválně NEpředvyplňujeme", což platí jen pro textovou větev.
  Tvrzení specu, že formulář ten vzor už používá u `must_decide`, bylo
  **nepravdivé**.

  *Oprava:* doplněn **rozsah pravidla**. Platí pro hodnoty, které se stanou
  závazným glosářovým termínem (postavy, místa, termíny). Pro vztahy a styl
  těžba žádný důkaz neposkytuje, takže se řeší jinak:
  - **vztahy**: scoutův návrh zůstane předvyplněný, ale sekce vyžaduje jedno
    zaškrtnutí „zkontrolováno" před uložením. Vztahy jsou vyšší sázka, než jsem
    si původně myslel - špatné vykání se táhne celou knihou. Vynutit 34 roletek
    je ale nepřiměřené k binární volbě, kterou lze přehlédnout v tabulce.
  - **styl**: předvyplněn bez ceremonie, člověk ho čte celý.
  - **vztahové `must_decide`**: roletka dostane prázdnou volbu, návrh vedle.

### Agreed + fixed (IMPORTANT)

- **`merge_sources` neurčoval původ zobrazené hodnoty.** Bez toho frontend neví,
  co zamknout a co umí vrátit. Doplněno pole `provenance`
  (`human` / `reference` / `none`) a **oddělené držení obou návrhů**
  (`scout_suggestion`, `lexicographer_suggestion`) - položka může mít oba
  a formulář nabídne každý zvlášť.
- **„Přijmout všechny" nemělo definovanou bezpečnou vratnost.** Doplněno:
  nepřepíše ručně vyplněná ani referencemi doložená pole a „zpět" vrátí jen ta
  pole, která sama změnila. Jinak by hromadná akce porušila zásadu, že se
  původní hodnota nikdy neztratí.
- **Klasifikační mezera:** vlastní jméno nalezené jen shodou bez ohledu na
  velikost písmen, ale nad prahem, nespadalo do žádné třídy. Doplněno do
  `evidence_only`.

### Agreed (NITS)

- Zastaralá věta tvrdící, že scoutův návrh zůstává předvyplněný, odstraněna -
  o tři řádky níž ji spec sám rušil.
- Potvrzeno, že po zjednodušení nezůstaly funkční odkazy na zrušené `coverage`,
  `stale`, `--limit`, `compound` ani `reference_report`; zbývající výskyty jsou
  historická vysvětlení, proč ty věci zmizely.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex 1 blokující, 3 důležité, 2 drobnosti — vše přijato. Blokující nález opět
mířil na nepravdivé tvrzení ve specu: napsal jsem, že formulář už používá vzor
"prázdné pole + návrh vedle" u must_decide, ale platí to jen pro textové otázky;
vztahové se předvyplňují (index.html:80-88) a guide.py:127,138 předvyplňuje
i oslovení a styl. Doplněn explicitní rozsah nového pravidla se zvláštním
zacházením pro vztahy (zaškrtnutí za sekci) a styl (bez ceremonie).
Dále doplněna provenience hodnoty a oddělené držení scoutova a lexikografova
návrhu, bezpečná vratnost hromadné akce a chybějící klasifikační případ.
