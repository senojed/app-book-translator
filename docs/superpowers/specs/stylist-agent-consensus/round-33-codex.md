## IMPORTANT

- `stylist.polish()` – číselný guard (`before_nums`/`after_nums`) vs. bezpečnostní tvrzení z kol 29–32: tvrzení, že `stderr` je jediný Codexem řízený text v chybové cestě, je nepravdivé. Při změně čísel se celý `after_nums` vloží do `StylistError`; `_polish_one_chapter` jej vytiskne a uloží jako `failed.error` i při `STYLIST_REPORT_REJECTED_TEXT=False`. Prompt injection tedy může perzistentně exfiltrovat číselný obsah. Oprava: při flagu jiném než literál `True` neuvádět hodnoty sekvencí, pouze obecnou chybu; přidat regresní test s tajným číslem ve výstupu a ověřit absenci v reportu i stdout.

- `_polish_one_chapter()` po `commit_chapter_result` + in-loop `except KeyboardInterrupt`: oprava z kola 30 nezaručuje jeden pravdivý záznam za kapitolu. Interrupt po úspěšném commitu, ale před `report.append(...polished...)`, vytvoří pouze `interrupted`, přestože DB už obsahuje přijatou stylizaci. Interrupt po appendu a před returnem vytvoří navíc druhý záznam, takže `attempted_count = len(report)` může překročit počet skutečně pokusných kapitol. Oprava: centralizovat/upsertovat záznam podle `idx` a při interruptu po commit fázi ověřit, zda commit proběhl; přidat testy obou hranic.

## NITS

- Řádky 2777 a 3494 tvrdí, že `interrupted` obsahuje `stage + error`, ale kód ukládá pouze `stage`. Sjednotit prózu nebo přidat `error`.
- Komentář konfigurace „Žádný volný text“ je příliš obecný: report stále obsahuje textová pole `run_error`, `finalization_error` a `failed.error`. Omezit tvrzení explicitně na záznam `rejected`.

## VERDICT

CHANGES_NEEDED