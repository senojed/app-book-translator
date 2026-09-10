## IMPORTANT

- `stylist.polish()` ř. 875 a `_polish_one_chapter()` ř. 1534: `STYLIST_REPORT_REJECTED_TEXT` se vyhodnocuje obecnou truthiness. Hodnoty `1` nebo `"False"` tedy aktivují tisk a perzistenci potenciálně exfiltrovaného textu, přestože kontrakt požaduje explicitní `True`. Použít `config.STYLIST_REPORT_REJECTED_TEXT is True` na obou místech a přidat regresní testy pro `1`, `"False"` a `None`, včetně stderr větve.
- `_write_polish_report` docstring ř. 1643–1644: tvrzení „Uvnitř rizika, co uživatel přijal `STYLIST_ACCEPT_FS_RISK`“ opakuje rationale výslovně odmítnuté v kole 31. Trvalá perzistence je samostatné riziko a samostatný opt-in. Text opravit, jinak bezpečnostní dokumentace odporuje rozhodnutí kola 31.

## NITS

- `stylist.polish` komentář ř. 824–825 stále říká „za opt-outem“; od kola 31 jde o opt-in.
- Sekce „Kolo 27+“ ř. 3469–3471 stále popisuje dedup přes `(type, term_id)`, zatímco kód a rozhodnutí kola 31 používají `(type, term_id, actual)`.
- Tabulka chybových stavů ř. 2738 ve výčtu hlavičky reportu vynechává `run_id`, přestože kód i ostatní popisy jej uvádějí.

## VERDICT

CHANGES_NEEDED