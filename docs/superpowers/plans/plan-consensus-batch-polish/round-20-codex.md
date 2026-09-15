## BLOCKING

- Task 9, `_merge_findings_by_id(..., drop_stale_non_markers=True)` vs. `test_save_chapter_text_change_does_not_wipe_finding_added_via_light_write`: implementace při `incoming=[]` nález `b1` odstraní, test vyžaduje jeho zachování. Nelze splnit obojí. Fix: zaveď do GET/save verzi či sadu výchozích IDs a při změně textu maž jen nálezy známé klientovi před editací; mezitím serverem přidané nálezy zachovej. Alternativně změň explicitně semantiku i test na ztrátu `b1`.

## IMPORTANT

- Task 13 Step 8, migrace: DB záloha přes `shutil.copy2` není bezpečná SQLite záloha při WAL režimu; může vzniknout neobnovitelná kopie bez WAL změn. To odporuje existujícímu odůvodnění `_snapshot_db`. Fix: pro DB zálohu použij `main._snapshot_db(config.DB_PATH, backup_path)` a při selhání zastav před jakoukoli migrací.

## VERDICT
CHANGES_NEEDED