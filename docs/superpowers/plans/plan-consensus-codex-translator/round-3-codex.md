## BLOCKING

- Task 2, `CodexLLMClient.complete()` / komentář k `truncated`: plán spoléhá na neexistující pojistku. `translator._parse()` při chybějícím `===METADATA===` nevyhodí chybu; přijme vše za `===PREKLAD===` jako překlad a vrátí prázdná metadata. Uříznutý výstup tedy může být potichu uložen jako `done`. Přidejte povinný koncový marker (např. `===KONEC===`) do promptu a striktní validaci obou markerů i konce; doplňte test částečně uříznutého výstupu.

## IMPORTANT

- Task 2, odmítnutý limit/checkpoint před revizí: odůvodnění odmítnutí je chybné. Bez guardu timeout/context failure při `revise_chapter()` stále zahodí kompletní scénový překlad, jen méně předvídatelně. Nový Codex backend tento případ zavádí pro plnou kapitolu EN + CZ + glosář. Uložte checkpoint scénového překladu před kritikou/revizí a při selhání revize jej zachovejte jako `flagged`/`needs_human`; pak lze bezpečně použít limit nebo jasně ošetřit timeout.

- Task 4, `_cmd_run`: kontrola `STYLIST_ACCEPT_FS_RISK` a použitelnosti CLI proběhne až při prvním `client_factory("translator")`. `run --translator codex --only <done-index>` nebo prázdná fronta proto skončí úspěchem i bez povinného opt-inu, což odporuje globální podmínce „`--translator codex` vyžaduje … True“. Validujte backend hned na začátku `_cmd_run`, před vytvořením běhu; ověřený model a příkaz předejte/cachujte do factory.

- Task 2 + Task 4, chybové ukládání: `extract_json()` vkládá až 2 000 znaků surové odpovědi do `ValueError`; `_cmd_run` je pak bez redakce uloží do `chapters.notes`. Pro Codex s přijatým FS rizikem je to trvalá exfiltrační cesta pro zamítnutý výstup, obcházející ochranu `STYLIST_REPORT_REJECTED_TEXT`. Změňte parser/obsluhu chyby tak, aby perzistentní chyba neobsahovala raw model output, a přidejte regresní test.

## VERDICT
CHANGES_NEEDED