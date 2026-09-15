## IMPORTANT

- Task 2 `assign_ids` / Task 13 Step 8 migrace: Nevalidní neprázdné `id` (např. `123`) zůstane zachováno, protože se nahrazuje jen falsy hodnota. GET jej vrátí klientovi, ale resolve/save jej následně odmítne (`finding_id`/`id` musí být string). Duplicity existujících `id` migrace také neopravuje, přestože merge/resolve předpokládají unikátnost. Oprava: `assign_ids` musí pro ne-string/prázdné/duplicitní id generovat nové UUID; doplň testy migrace pro `id: 123` a duplicitní id.

## VERDICT

CHANGES_NEEDED