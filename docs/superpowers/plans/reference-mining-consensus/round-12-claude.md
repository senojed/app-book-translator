# Round 12 — Claude critique

## Claude's own findings

Codex vrátil CONSENSUS (poprvé, žádný BLOCKING/IMPORTANT/NIT). Udělal jsem
vlastní čerstvý průchod - celý JS blok Tasku 12 (582 řádků) znovu přečten
vcelku (ne jen diffy jednotlivých kol) a `merge_sources`/`_merge_section`
v `guide.py` taky.

### IMPORTANT (vlastní)

- **Task 12: přidání vztahu tlačítkem "Přidej dvojici" nemaže zaškrtnutí
  "zkontroloval/a jsem tykání/vykání".** Nová dvojice dostane výchozí
  `address: "vyka"` (řádek `add.onclick`), ale nikdo ho nezkontroloval -
  zůstane-li checkbox zaškrtnutý ze DŘÍVĚJŠKA (než se dvojice přidala),
  `_check_relationships_reviewed` na serveru ho vezme jako platné potvrzení
  i pro tenhle nový, nezkontrolovaný řádek. Přesně ten scénář, kterému má
  checkbox zabránit ("špatné vykání se táhne celou knihou", spec). *Fix:*
  `add.onclick` teď nastaví `data.relationships_reviewed = false` při
  přidání každé nové dvojice. Přidáno do ručního checklistu (krok 5).

  Prošel jsem i sousední otázku - odpověď na VZTAHOVOU `must_decide` otázku
  (server-side `apply_must_decide`) stejný problém nemá, protože adresu
  (`tyka`/`vyka`) pro tenhle řádek uživatel zadal PŘÍMO při zodpovězení
  otázky, ne jako tichý default - "kontrola" už proběhla jinou cestou.

### Disagreed

Nic - Codexova (prázdná) kritika beze zbytku.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex podal CONSENSUS (poprvé, prázdný - žádné nálezy vůbec). Já jsem při
vlastním čerstvém průchodu (celý 582řádkový JS blok vcelku, ne po kolech)
našel jeden reálný, byť menší, gap: tlačítko "Přidej dvojici" nemazalo
zaškrtnutí kontroly vztahů, takže nová dvojice s tichým defaultem "vyka"
mohla proklouznout jako "zkontrolovaná". Opraveno. Shoda tedy tohle kolo
NENÍ (potřebuje ji Codex vidět a souhlasit ve STEJNÉM kole) - pokračuje
kolo 13, kde Codex dostane příležitost tenhle konkrétní fix ověřit.

Všech 33 Python bloků a 1 JS blok znovu ověřeno strojově.
