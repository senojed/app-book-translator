## IMPORTANT

- Task 2 checkpointy „kontrola“ a „příprava transakce B“ + Task 5 generický `except Exception`: `_checkpoint_flagged()` nejdřív správně uloží kapitolu jako `flagged`, ale pak původní nefatální výjimku znovu vyhodí. `_cmd_run` ji přepíše na `error`, takže se kapitola při dalším `run` automaticky zkusí znovu. To ruší účel checkpointu. Oprav: po úspěšném checkpointu nefatální chybu převést na návratový výsledek `flagged` (nebo zvláštní výjimku, kterou CLI zachytí bez `update_chapter(status="error")`); `FatalRunError` a `KeyboardInterrupt` dál re-raise. Přidej integrační test přes `_cmd_run`.

## NITS

- Task 3 `CodexLLMClient.complete()` a `count_tokens()`: deklaruje „nenulový“ odhad, ale `// 2` vrací `0` pro krátký neprázdný vstup či výstup. Použij `max(1, ...)` pro neprázdný text a doplň test.

## VERDICT
CHANGES_NEEDED