## IMPORTANT

- `main.py:_cmd_polish`, ř. 1765–1779; report kontrakt ř. 1582–1584: `FatalRunError` z kritika/cost guardu se přehodí bez záznamu aktuální kapitoly. `attempted_count = len(report)` ji proto chybně označí jako nezpracovanou. Oprava: při propagaci `FatalRunError` doplnit `fatal` záznam, pokud jej `_polish_one_chapter` ještě nepřidal; přidat test pro `pipeline._run_critic` vyhazující `FatalRunError`, nejen pro commit.

- `stylist.polish`, ř. 857–860; `_polish_one_chapter`, ř. 1432–1435; bezpečnostní kontrakt ř. 1601–1608: `STYLIST_REPORT_REJECTED_TEXT=False` stále netěsní. Codex může vložit tajný obsah do `stderr`; ten se stane součástí `StylistError`, konzole i `failed.error` v reportu. Oprava: při vypnutém detailu nepersistovat ani netisknout raw `stderr`/výjimky pocházející z Codexu; ukládat pouze normalizovanou kategorii chyby. Přidat regresní test s tajným textem na stderr a nenulovým exit kódem.

## NITS

- Ř. 2717–2720 stále tvrdí, že bez preflightu by běh skončil `status="ok"`, přestože ř. 3344–3351 tvrdí, že tato stale próza byla v kole 26 opravena. Má být `status="fatal"` při selhání všech kapitol.

- Ř. 3364 označuje výstup `_rejection_reasons` jako „DEduplikovaný seznam“. Kód deduplikuje pouze konkrétní překryv konkordančních větví; kritikovy a meaning-check nálezy záměrně nededuplikuje. Formulaci zpřesnit.

- Testovací scénář ř. 2581–2585 uvádí, že první volání `_polish_one_chapter` může vyhodit výjimku „mimo per-kapitolovou smyčku“. Nemůže: obecná výjimka je uvnitř smyčky zachycena jako `failed`. Pro prázdný report použít výhradně selhání `_client_factory`.

## VERDICT

CHANGES_NEEDED