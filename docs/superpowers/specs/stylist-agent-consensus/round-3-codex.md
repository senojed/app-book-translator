## BLOCKING

- **Ř. 66, 406–454:** Návrh tvrdí, že `main.py` potřebuje pouze nový import `hashlib`, ale používá také globální `concordance` a `glossary`. V aktuálním `main.py` nejsou importované; příkaz skončí `NameError`. Doplnit oba importy a integrační test přes skutečný `_cmd_polish`.
- **Ř. 327–343, 418–424:** Přísnější `_polish_rejected` neopravuje dříve nalezený problém s verdiktem kritika. `critic.review()` zahodí pole `verdict`; odpověď `{"verdict":"revise","findings":[]}` se proto stále přijme. Validovat konzistenci verdiktu ve `critic.review`, nebo vracet verdikt spolu s findings; přidat regresní test.

## IMPORTANT

- **Ř. 395–424:** Kontrola odmítá všechny `omission`/`fidelity` nálezy v novém textu, nikoli pouze nálezy zavedené stylizací. `done` kapitola může legitimně obsahovat minor poznámku nebo falešný pozitivní nález, takže i významově identická úprava bude vždy zamítnuta. Porovnat nálezy a term mentions před/po a odmítat nové či zhoršené obsahové problémy.
- **Ř. 459–477:** `except Exception` považuje chybu DB, poškození schématu i programátorskou chybu za lokální selhání kapitoly. Dávka pak pokračuje a může skončit `status="ok"`. Zachytávat pouze definované obnovitelné chyby; databázové a neočekávané chyby ukončit jako fatální.
- **Ř. 31–35, 381–392:** Dříve odmítnutý požadavek na rollback zůstává platný. Osm hex znaků SHA-1 neumí obnovit ani porovnat přepsaný schválený text a má pouze 32bitovou kolizní odolnost. Guardraily jsou probabilistické, takže nevratné přepsání je nepřiměřené. Uložit alespoň jednu předstylizační verzi nebo obnovitelný snapshot; není nutná plná historie všech revizí.
- **Ř. 412–432:** Pokud Codex vrátí text totožný s původním, provedou se dvě placené kontroly, kapitola se označí jako stylizovaná a další pokus se bez `--force` zablokuje. Detekovat `styled == cz` před guardraily, nezapisovat marker a vykázat samostatný výsledek `unchanged`.
- **Ř. 443–478, 667:** Chybějící přihlášení, neplatný model nebo nekompatibilní CLI se zkouší znovu pro každou kapitolu; běh může skončit `ok` se všemi kapitolami `failed`. Přidat jednorázový preflight a globální konfigurační/autentizační chyby klasifikovat jako fatální.
- **Ř. 185–250:** Vytvoření a zápis vstupního souboru jsou mimo `try/finally`. Selhání při zápisu může ponechat částečný plaintext knihy v dočasném adresáři. Použít `TemporaryDirectory` a obalit celý životní cyklus od vytvoření adresáře.

## NITS

- **Ř. 462–468:** Test `isinstance(e, KeyboardInterrupt)` je mrtvý kód, protože `KeyboardInterrupt` nedědí z `Exception`. Odstranit jej; vnější `except KeyboardInterrupt` stačí.
- **Ř. 438, 413, 426:** Model se pouze testuje přes `.strip()`, ale do CLI a markeru se předává původní hodnota. Jednou jej normalizovat a používat normalizovanou hodnotu.

## VERDICT

CHANGES_NEEDED