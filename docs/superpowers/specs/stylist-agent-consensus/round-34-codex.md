## IMPORTANT

- `stylist.polish()` ř. 914–945, `_cmd_polish` ř. 1874–1882, config próza ř. 377–384: `STYLIST_REPORT_REJECTED_TEXT=False` stále není uzavřená redakční hranice. Chyby počtu odstavců a poměru délky obsahují hodnoty odvozené z Codexova výstupu; obecný handler navíc ukládá libovolné `str(e)` do `failed.error`. To odporuje tvrzení, že zůstávají pouze vlastní hlášky programu, a umožňuje perzistenci obsahu či odvozeného covert-channelu. Oprava: při `False` používat pouze pevné chybové kódy/texty bez hodnot odvozených ze `styled`; libovolné `str(e)` ukládat jen při explicitním opt-inu. Přidat sentinel testy pro strukturální chyby i neočekávanou výjimku.

- `_polish_one_chapter` ř. 1611–1617 a obecný per-kapitolový handler ř. 1874–1882: invariant „jeden report záznam na kapitolu“ platí jen pro `KeyboardInterrupt`. Po úspěšném commitu se nejprve přidá `polished`, ale následný `BrokenPipeError` nebo jiná běžná výjimka z `print()` způsobí, že vnější handler přidá druhý záznam `failed`. `attempted_count` i `summary` pak budou chybné. Oprava: report nemutovat uvnitř `_polish_one_chapter`; vracet jeden strukturovaný výsledek a append provést jednou v orchestrátoru, případně deduplikovat podle `idx` ve všech handlerech.

- Commit/interrupt hranice ř. 1590–1616, ř. 1858–1872 a testovací požadavek ř. 2731–2738: oprava z kola 33 stále nezaručuje pravdivý výsledek. Pokud wrapper `commit_chapter_result` provede commit a následně před návratem vyhodí `KeyboardInterrupt`, append `polished` se neprovede a vnější handler zapíše `interrupted`, přestože DB už obsahuje změnu. Přesně tato varianta je v testovací próze uvedena jako údajně ekvivalentní monkeypatchi `print`, ale podle navrženého kódu by test selhal. Oprava: po interruptu během commit fáze stav DB explicitně ověřit a zaznamenat `polished` nebo `commit_unknown`; testovat skutečně obě strany hranice. Opravit zastaralou testovací prózu.

## NITS

- `_write_polish_report` ř. 1691 a název souboru: `generated_at` nemá časové pásmo a filename má přesnost pouze na sekundy. Použít timezone-aware ISO 8601 a bezpečnější unikátní suffix.

## VERDICT

CHANGES_NEEDED