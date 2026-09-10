## BLOCKING

- **Řádky 1057–1082, test `test_polish_invokes_codex_with_expected_argv`:** U Python skriptu je `sys.argv[0]` cesta ke skriptu; `argv[1]` je `"exec"`. `tail = argv[2:]` proto zahodí `"exec"` a `assert tail[0] == "exec"` vždy selže. Oprava: použít `tail = argv[1:]`. Současně ověřit celý očekávaný seznam, ne jen přítomnost flagů.

## IMPORTANT

- **Řádky 347–361, 528–536, číselný guard:** Regex nehlídá znaménka ani typograficky správně oddělená procenta. `-12 → 12`, `12 % → 12` i `12 % → 12` mají shodný multiset, přestože mění význam. Oprava: zahrnout znaménko a volitelnou běžnou/NBSP mezeru před `%`, procento kanonizovat jako součást tokenu a přidat regresní testy.

- **Řádky 933–957, lifecycle snapshotu:** `shutil.copy2` proběhne před `try/finally`; následná chyba v `glossary.all_terms`, načtení guide nebo `state.create_run` zanechá `.pre-polish-snapshot`. Tvrzení o vždy provedeném úklidu proto neplatí. Oprava: celý úsek po vytvoření snapshotu obalit `try/finally`; `rid` inicializovat na `None` a `finish_run` volat jen po úspěšném `create_run`.

- **Řádky 1057–1089, „přesný argv“ test:** I po opravě indexu test není přesný: dovolí duplicitní nebo dodatečné nebezpečné přepínače a nekontroluje hodnoty `-C`/`-o` ani jejich vztah. Oprava: normalizovat dynamické cesty a porovnat celý seznam; ověřit, že `-o == Path(-C)/"out.txt"`.

- **Průchod konzistence prózy vůči kódu:** Zůstalo několik popisů starého chování:
  - **Řádek 625:** tvrdí, že nevzniká soubor s textem knihy, ale `-o` zapisuje stylizovaný text.
  - **Řádky 748–750:** docstring stále uvádí `concordance.check_chapter(..., [])`, zatímco kód používá `rendered_terms`.
  - **Řádky 681–686 a 1448–1451:** stále tvrdí, že všechny per-kapitolové chyby skončí `status="ok"`; aktuální kód používá `"fatal"`.
  - **Řádky 1440–1443:** tvrdí, že baseline pochází z doby nastavení `done`; nyní se počítá čerstvě těsně před stylizací.
  - **Řádky 1554–1559:** tvrdí, že `check_meaning_preserved` kontroluje jen význam; od kola 7 kontroluje i rejstřík.
  - **Řádky 1576–1583 a 1608–1612:** popisují přímé/líné kopírování DB, které kolo 9 nahradilo časným snapshotem a pozdní promocí.

  Oprava: aktualizovat nebo výslovně označit tyto historické body jako překonané; sekce „Rozhodnutí“ se nyní prezentuje jako aktuální stav.

## VERDICT

CHANGES_NEEDED