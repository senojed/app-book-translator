# Round 16 — Claude critique

Jediný nález, ověřen v kódu, přijat.

## On Codex's points

### Agreed + fixed

- **Allowlist zahazoval `note`.** Ověřeno: `merge_draft_and_guide` poznámku
  emituje (`guide.py:94,112`) a `_seed_one` ji ukládá do glosářového řádku
  (`glossary.py:139`). Můj allowlist z kola 14 ji vynechal, takže by se
  kontext od scouta ztratil při uložení. Doplněno do allowlistu u postav, míst
  i termínů a přidán test na zachování napříč celou cestou.

## Claude's own findings

Prošel jsem spec vlastní inventurou proti logu rozhodnutí (kola 1-15) a proti
kódu. Nenašel jsem nic, co by způsobilo špatné chování, ztrátu dat nebo
zastavilo implementaci.

Zbývající nejistoty jsou takové, které **má rozhodnout měření, ne další kolo
oponentury**: prahy pro `confirmed`, poměr pro souvýskyt, a jestli je přesná
shoda ve stupni 1 příliš přísná. Všechny tři jsou zapsané jako otevřené otázky
k prvnímu běhu a všechny tři jsou levné změnit v `config.py`.

## Claude VERDICT

CONSENSUS

## Summary for log

Codex: jeden důležitý nález (allowlist zahazoval `note`, ověřeno proti
guide.py:94,112 a glossary.py:139), opraven. Claude: vlastní inventura proti
logu i kódu bez nálezu. Zbývající nejistoty patří měření při prvním běhu, ne
oponentuře. Claude vyhlašuje CONSENSUS; formální shoda vyžaduje totéž od Codexe
v následujícím kole.
