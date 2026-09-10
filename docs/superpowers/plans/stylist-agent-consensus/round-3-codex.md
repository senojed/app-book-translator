## BLOCKING

- **Task 5, fake skripty parsující stdin:** Přechod na `sys.stdin.buffer.read().decode("utf-8")` odstranil normalizaci konců řádků. Na Windows rodičovský textový stdin může převést `\n` na `\r\n`; regex `---\n(.*?)\n\nOdpověz` potom nenajde shodu a `m.group(1)` spadne. **Oprava:** po UTF-8 dekódování normalizovat `\r\n` na `\n` ve všech třech parsujících skriptech. Přidat explicitní ověření této varianty.

## IMPORTANT

- **Task 5, `test_polish_kills_process_tree_on_keyboard_interrupt`:** Test spouští skutečný proces čekající na EOF, ale `_kill_process_tree` nahrazuje pouhým počítadlem a `communicate()` vyhodí výjimku ještě před uzavřením stdin. Následný `wait(timeout=10)` proto vyprší; test sám nezaručuje ukončení potomka ani uzavření rour. **Oprava:** použít kompletní fake `Popen` pro test pořadí `communicate → kill → wait → re-raise`, nebo spy delegující skutečné ukončení s nezávislým úklidem v `finally`. Ověřit také `wait` a zachování původní výjimky.

- **Task 13, Step 3:** Nově přidané `shutil.copy2("data/state.sqlite3", ...)` vytváří ověřovací DB mechanismem, který spec 1333–1341 výslovně odmítá kvůli souběžným zápisům a WAL. Izolovaný cíl nezaručuje konzistentní zdroj; manuální ověření může pracovat s neúplnou kopií. **Oprava:** použít již implementované `main._snapshot_db(source_db, verify_db)` a teprve potom přesměrovat `config.DB_PATH`.

## VERDICT
CHANGES_NEEDED