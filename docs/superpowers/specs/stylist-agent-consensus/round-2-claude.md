# Round 2 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní - Codex round 2 pokryl to podstatné)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
- Importy `config`/`extract_json` uvnitř `check_meaning_preserved` byly
  nekonzistentní se zbytkem kódové základny (`lexicographer.py` je má na
  vrcholu souboru). Přesunuto na top-level importy `stylist.py`.

## On Codex's points

### Agreed + fixed
- **BLOCKING - `-o` + read-only sandbox se vzájemně vylučují:** opraveno.
  `-o out_path` teď zachytává POSLEDNÍ ZPRÁVU agenta (capture na úrovni
  CLI), prompt už agenta nežádá, aby cokoli zapisoval. Ověřeno přímo v
  tomhle běhu - `round-1-codex.md`/`round-2-codex.md` vznikly přesně
  touhle cestou (`-o` v mém vlastním `codex exec` volání pro tenhle
  plan-consensus).
- **BLOCKING - `["codex"]` na Windows nefunguje bez `shutil.which`:**
  přidána `_resolve_codex_cmd`, testy pro absolutní cestu (`sys.executable`,
  nevolá `which`) i chybějící holé jméno.
- **BLOCKING - testy odporují vlastní kontrole poměru délky:** oba
  pozitivní testy přepsané tak, aby fake vracel text PODOBNÉ délky a
  struktury jako vstup (poměr v mezích 0.5-1.5x). Test dlouhého vstupu teď
  navíc explicitně ověřuje `len(long_cz) > 32*1024`, ať skutečně testuje
  tvrzený limit, ne jen "nějaký delší text".
- **IMPORTANT - kritik EN-vs-CZ-po nechytí posun obhajitelný vůči EN, ale
  jiný než schválený výklad:** přidána `stylist.check_meaning_preserved`
  (CZ-před vs. CZ-po, nezávislý Anthropic prompt) jako TŘETÍ kontrolní
  vrstva vedle strukturální kontroly a kritika. `_polish_rejected` rozšířen
  o typ `meaning_drift`.
- **IMPORTANT - per-kapitolový `try` obaloval jen `stylist.polish`:**
  celé zpracování jedné kapitoly je teď v `_polish_one_chapter`, `_cmd_polish`
  ho volá v jednom `try/except Exception`, který navíc explicitně
  přeposílá `FatalRunError`/`KeyboardInterrupt` dál (nechytá je jako
  "obyčejnou" chybu kapitoly).
- **IMPORTANT - `FatalRunError` z kritika/cost guardu unikal jako
  `failed += 1`:** opraveno výše (stejná oprava) - `FatalRunError` teď
  ukončí CELÝ `polish`, `except FatalRunError` na úrovni `_cmd_polish`
  vypíše chybu a vrátí 1, `finish_run(..., "fatal")`.
- **IMPORTANT - `CODEX_MODEL=None` dělá audit nedohledatelným:**
  `CODEX_MODEL` je teď POVINNÉ (výchozí `""`, `_cmd_polish` na prázdné
  hodnotě rovnou skončí s chybovou hláškou). Marker vždy nese skutečný
  použitý model, nikdy "výchozí".
- **IMPORTANT - žádný test nechytí produkční problémy s executable/
  sandboxem (protože všechny mockují CLI):** přidána sekce "Manuální
  ověření" - jedno ruční spuštění nad reálnou kapitolou před tím, než se
  Task považuje za hotový, stejný princip jako vizuální kontrola u review
  formuláře v reference-mining plánu (Task 12).
- **NIT - `_already_styled` bez `isinstance(list)` kontroly:** přidáno,
  plus `isinstance(f, dict)` na každém prvku - platný, ale neseznamový/
  necekaný tvar `notes` teď dá bezpečné `False`, ne pád.
- **NIT - chybí `_print_usage(db, rid)`:** přidáno na konec `_cmd_polish`
  (kritik i kontrola významu jsou Anthropic volání, patří do stejného
  vyúčtování jako `run`).
- **NIT - cesta v promptu bez ohraničení, regex nezvládá mezery:** vyřešeno
  samo přechodem na `-o` (žádná zmínka o výstupní cestě v promptu), vstupní
  cesta je teď v uvozovkách (`f'... ze souboru "{in_path}" ...'`).

### Agreed but already addressed
(žádné - kolo 2 nálezy jsou všechny nové, nic z kola 1 se neopakovalo)

### Disagreed
(žádné - kolo 2 nezpochybnilo kolo-1 rozhodnutí o zúžení rozsahu plné
historie/plného auditu zamítnutých pokusů, což beru jako mlčky přijaté)

## Claude VERDICT

Po aplikaci všech bodů z kola 2 (3 BLOCKING + 5 IMPORTANT + 3 NITS)
nenacházím ve vlastním nezávislém čtení žádné další BLOCKING/IMPORTANT.

`CONSENSUS`

## Summary for log

Kolo 2: Codex našel 3 nové BLOCKING (kontradikce `-o`/`read-only sandbox`,
Windows `codex` vs. `codex.cmd`, vlastní testy odporující vlastní kontrole
délky) a 5 IMPORTANT (třetí kontrolní vrstva CZ-před/CZ-po, roztažení
per-kapitolového try, `FatalRunError` propagace, povinný `CODEX_MODEL`,
chybějící manuální smoke-test poznámka) + 3 NITS. Všechno opraveno -
klíčová oprava (BLOCKING #1) mění celý mechanismus zachytávání výstupu
Codexu z "agent zapisuje soubor" na "CLI zachytává poslední zprávu", což
je navíc přímo ověřené chování z tohohle vlastního plan-consensus běhu.
Design je teď kompletní - čeká se na kolo 3 Codexu, jestli potvrdí.
