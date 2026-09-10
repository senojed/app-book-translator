## IMPORTANT

- `main.py`, `_polish_rejected()` ř. 1093–1106: počítání přes `str.count(surface)` neodpovídá pravidlům konkordance. U `leak` je detekce case-insensitive s hranicemi slov; u `inconsistency` používá kmeny. Přidaný výskyt s jinou velikostí písmen nebo skloňováním proto může projít. Použít počítání se stejnou normalizací jako `check_chapter()` a přidat regresní testy pro změnu case a další skloňovaný výskyt.

- Test `test_polish_long_input_goes_through_stdin_not_argv`, ř. 1700–1721: fake proces stdin vůbec nečte. Test tedy neověřuje, že dlouhý prompt dorazil celý; projde i při zahození či zkrácení vstupu. Fake musí přečíst stdin a ověřit délku/hash nebo z něj rekonstruovat výstup.

- Chybová tabulka, ř. 2147: tvrzení „stejný konkordanční nález → přijato“ je po opravě z kola 20 nepravdivé. Stejný klíč se odmítá, pokud přibyl počet odpovídajících povrchů. Upravit řádek a výslovně uvést obě podmínky.

## NITS

- Docstring `stylist.py`, ř. 388 a 450–459: nadpis končí koly 17–18 a text stále popisuje `_cmd_polish` jako řešení opt-inu. Od kola 20 je závazná kontrola přímo v `stylist.polish()`. Aktualizovat nadpis i odstavec; CLI kontrolu označit pouze jako časný UX guard.

- `Mimo rozsah`, ř. 44: odkazuje na docstring `_backup_db_once`, ale popisuje jej starým názvem `_backup_db_once` správně; formulace „viz … výš“ na ř. 55 míří na sekci, která je ve skutečnosti níže. Opravit směrový odkaz.

## VERDICT

CHANGES_NEEDED