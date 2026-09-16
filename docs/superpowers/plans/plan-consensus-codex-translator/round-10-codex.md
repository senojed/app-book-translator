## BLOCKING

- Task 2, Step 3 `_parse()`: Řádková validace nečiní stávající `split_sections()` bezpečným. Ten stále hledá markery jako podřetězce. `test_marker_like_text_inside_metadata_json_does_not_confuse_parser` proto selže: inline `===KONEC===` v JSON hodnotě předčasně ukončí sekci METADATA a JSON se rozbije. Oprava: po validaci sestavit `translation` a `metadata` přímo slicingem podle nalezených offsetů řádkových markerů; `split_sections()` zde nepoužívat.

## IMPORTANT

- Task 3/5, `FatalRunError` z právě zpracovávané kapitoly: plán stále nezabrání automatickému opakování při budoucím `run`. `begin_chapter()` nastaví `processing`; fatální výjimka kapitolu neaktualizuje; příští `_cmd_run()` ji přes `recover_processing()` změní na `pending` a znovu spustí. To přímo odporuje odůvodnění kol 2 a 6. Oprava: před opětovným vyhozením fatální chyby označit aktuální kapitolu `flagged` nebo `needs_human` s redigovanou diagnostikou; doplnit test dvou po sobě jdoucích běhů, že se kapitola bez explicitního retry již nezařadí.

## VERDICT

CHANGES_NEEDED