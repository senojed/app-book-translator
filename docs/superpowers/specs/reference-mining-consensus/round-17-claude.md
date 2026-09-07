# Round 17 — Claude critique

Jediný nález, přijat. Je to zbytek po mé vlastní opravě z kola 15 - přesně ten
typ chyby, který smyčka opakovaně odhaluje: opravím jedno místo a nezkontroluju,
jestli tvrzení nepřežívá jinde.

## On Codex's points

### Agreed + fixed

- **Definice `E` si protiřečila s pravidlem o aliasech.** V kole 15 jsem
  změnil `books_with_en` na primární povrch (aby aliasy typu `sir` nerozšířily
  `E` skoro na celý korpus), ale definice predikátu o deset řádků výš dál
  říkala „anglický povrch (nebo alias)". Rozdíl mění klasifikaci `proposed`,
  takže to není kosmetika. Sjednoceno na primární povrch, sjednocena i signatura
  (`surface`, ne `surfaces`) a doplněn test, že aliasy `E` neovlivňují.

## Claude's own findings

Žádné. Inventura proti logu i kódu bez nálezu.

## Claude VERDICT

CONSENSUS
