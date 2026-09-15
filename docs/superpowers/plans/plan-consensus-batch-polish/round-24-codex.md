## NITS

- Task 13, Step 8 migrace: `UPDATE chapters SET notes=?` neaktualizuje `updated_at`, přestože UI tento údaj zobrazuje. Doplň `updated_at=CURRENT_TIMESTAMP`.

## VERDICT

CONSENSUS