# Plan-consensus — finální verdikt

**Výsledek: MAX_ROUNDS** (10 z 10 kol vyčerpáno)

## Proč ne CONSENSUS

Shoda vyžaduje `CONSENSUS` od obou kritiků ve stejném kole. V kole 10 vyhlásil
Codex `CONSENSUS` bez nálezů, ale Claude při inventuře rozhodnutí proti logu
našel jeden důležitý nedostatek (viz níže), takže za sebe hlásí `CHANGES_NEEDED`.

## Nedořešené body

**Žádné.** Jediný nález kola 10 byl v témže kole opraven a ověřen:

- Konsolidační přepis z kola 8 zrušil sekci „Stupně řešení" a s ní pravidlo, že
  stupeň 1 dostává jen povrchy, které stupeň 0 nedoložil (a odhad ceny). Sekce
  obnovena, ověřeno třemi kontrolami.

## Sporné body

**Žádné.** Za celou smyčku vznikl jeden spor (kolo 5: předvyplnění hodnoty
u nálezu doloženého jen aliasem). Claude nejprve Codexův plošný zákaz odmítl
a nahradil ho užším pravidlem, v kole 6 svou námitku po silnějším protiargumentu
stáhl a přijal původní Codexovo řešení.

## Statistika

| Kolo | Codex | Claude | Opraveno |
|---|---|---|---|
| 1 | CHANGES_NEEDED (4B, 9I) | CHANGES_NEEDED | 17 |
| 2 | CHANGES_NEEDED (3B, 7I) | CHANGES_NEEDED | 11 |
| 3 | CHANGES_NEEDED (4B, 6I) | CHANGES_NEEDED | 12 |
| 4 | CHANGES_NEEDED (3B, 7I) | CHANGES_NEEDED | 11 |
| 5 | CHANGES_NEEDED (2B, 2I) | CHANGES_NEEDED | 5 |
| 6 | CHANGES_NEEDED (2B, 2I) | CHANGES_NEEDED | 6 |
| 7 | CHANGES_NEEDED (4B, 2I) | CHANGES_NEEDED | 9 |
| 8 | CHANGES_NEEDED (6B, 1I) | CHANGES_NEEDED | 7 |
| 9 | CHANGES_NEEDED (2B, 2I) | CHANGES_NEEDED | 4 |
| 10 | **CONSENSUS** | CHANGES_NEEDED | 1 |

Celkem 83 přijatých oprav, 1 spor (vyřešen), 0 nedořešených bodů.

## Poznámka k průběhu

Kola 7-9 z velké části opravovala nikoli návrh, ale **neúplně provedené opravy
z předchozích kol**. Dvakrát se ukázalo, že ohlášená oprava se do dokumentu
vůbec nezapsala (textová náhrada neseděla na vzor), a konsolidační přepis
v kole 8 ztratil tři dříve přijatá rozhodnutí. Od kola 7 se proto každá změna
verifikuje grepem a od kola 9 se navíc dělá inventura proti logu rozhodnutí.

Tři pokusy specifikovat český matcher od stolu selhaly a všechny tři vyvrátilo
měření na skutečném korpusu. Spec proto u téhle jediné věci nepředepisuje
algoritmus, ale přejímací kritéria s číselným prahem.
