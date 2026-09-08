# Round 10 — Claude critique

## Claude's own findings

Žádné nové vlastní nálezy. Kolo proběhlo se zpožděním - Codex poprvé narazil
na vyčerpaný kredit ("You've hit your usage limit"), musel jsem spustit
znovu; uživatel řekl pokračovat.

## On Codex's points

0 BLOCKING, 2 IMPORTANT, 2 NITS. Všechny přijaty po ověření.

### Agreed + fixed

- **Task 12: `test_bulk_undo_clears_active_suggestion_flag` nikdy
  nenastavila `_renderActive = true` PŘED voláním undo, takže by test prošel
  i po odstranění obou úklidových řádků z kola 9.** Ověřeno spuštěním -
  postavil jsem rozbitou verzi `undoAcceptAllScoutSuggestions` (bez úklidu)
  a potvrdil, že MŮJ PŮVODNÍ test by proti ní prošel taky (falešně zelený
  test). *Fix:* test teď explicitně simuluje krok "uživatel klikl na
  jednotlivé 'použít návrh'" (nastaví `_renderBefore`/`_renderActive`,
  přesně jak by to udělal `use.onclick`) PŘED voláním undo. Přidán
  analogický test pro `_czActiveKey` (dřív žádný neexistoval - jen `render`
  měl pokrytí, `cz` ne). Oba nové testy ověřeny spuštěním obojím směrem -
  projdou proti opravené logice, spadnou proti neopravené.
- **Task 12: `valueField.revert.onclick`/`renderField.revert.onclick`
  nečistily `_czActiveKey`/`_renderActive`.** Scénář: odemkni doložené pole
  → použij návrh → vrať se na referenční hodnotu (revert) → odemkni znovu →
  tlačítko návrhu mylně ukazuje "zpět" ze STARÉHO cyklu, ačkoli v tomhle
  novém cyklu nic aplikováno nebylo - vizuálně nesprávný stav i riziko, že
  klik na něj obnoví starou hodnotu z minulého cyklu. *Fix:* oba `revert.
  onclick` handlery teď čistí příslušný `_czActiveKey`/`_renderActive`,
  stejně jako to od kola 9 dělá `undoAcceptAllScoutSuggestions`.

### Agreed + fixed (NITS)

- **Task 12: `_JS_SOURCE` v testu není bajtově identická s produkčním kódem
  (chybí komentáře) - nic drift mezi kopiemi SAMOTNÉHO KÓDU nehlídá.**
  Přeformulováno "POZOR" varování z "doslovná kopie" na "kopie spustitelného
  kódu bez komentářů", s jasným varováním, že se hlídá jen shoda chování,
  ne bajtová shoda.
- **Task 12 krok 5: instrukce pro test zastaralosti byla technicky
  nesmyslná** - "posuň práh a ZNOVU SPUSŤ `reference`" by vytvořilo NOVÝ
  `reference.json` s otiskem sedícím na NOVÉM prahu, tedy zase čerstvý
  nález, ne zastaralý. Ověřeno trasováním `thresholds_fingerprint`.
  *Fix:* přepsáno na "změň práh v `config.py` a otevři `review` BEZ
  dalšího běhu `reference`" - tak fingerprint v `reference.json` zůstane
  starý a `review` ho porovná s novým (aktuálním) - to je test zastaralosti.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Desáté kolo - Codex poprvé narazil na infrastrukturní limit (vyčerpaný
kredit), ne na chybu v plánu; po opakování doběhl normálně. Oba IMPORTANT
nálezy patří do stejné rodiny jako kola 8-9 (bulk/individuální kompozice
akcí), ale tentokrát cílí na TEST samotný (falešně zelený assert kvůli
chybějící přípravě stavu), ne na produkční kód - jiná vrstva chyby: špatně
napsaný regresní test je stejně nebezpečný jako chybějící, protože vytváří
falešný pocit jistoty. Ověřil jsem opravu i protiběžně (rozbitá verze
skutečně test shodí) u obou nových testů, ne jen že syntakticky prošly.

Všech 33 Python bloků a 1 JS blok znovu ověřeno strojově.
