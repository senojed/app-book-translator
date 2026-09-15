## BLOCKING

- Task 9, lehká větev `if text == cz_before`: Po „Znovu polish“ může uživatel ponechat původní text, ale uložit nové findings. Větev nepředává `known_ids`, takže `_merge_findings_by_id` zachová staré findings a přidá nové UUID findings z regenerace; opakování hromadí duplicity. Oprava: pro regenerovaný seznam explicitně předej `known_ids` i do lehké větve (nejlépe pod samostatným příznakem „findings pochází z regenerace“, aby prázdný běžný save nezačal mazat findings). Přidej test regenerate → návrat k původnímu textu → save.

- Task 13, Step 8 migrace: Zálohy nejsou spolehlivé při částečném selhání. `_snapshot_db` i `shutil.copy2` mohou zanechat neúplný cílový soubor; další běh pak přes `if exists` tento nevalidní soubor považuje za původní zálohu a migraci provede bez obnovitelné zálohy. Navíc history backup vzniká až po commitu `chapters.notes`. Oprava: vytvoř obě zálohy před první DB změnou do unikátních dočasných souborů, ověř je a teprve pak je atomicky přejmenuj na finální cesty; při selhání dočasný soubor smaž a migraci zastav.

## NITS

- Task 9, `known_ids_raw = payload.get("known_ids") or []`: Falešné ne-list hodnoty (`false`, `0`, `""`, `{}`) se změní na `[]` a projdou validací, přestože kontrakt říká „pokud přítomné, musí být pole stringů“. Rozliš chybějící/`null` od jiných hodnot.

## VERDICT

CHANGES_NEEDED