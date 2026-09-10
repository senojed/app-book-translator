## IMPORTANT

- **Guardrail, body před `_parse_findings`; Rozhodnutí „Pravidlo přijetí“:** Text stále tvrdí, že baseline pochází z uloženných `notes` z doby dokončení kapitoly. Kód ji správně přepočítává čerstvě pomocí `concordance.check_chapter`. To může implementátora vést k obnovení staré chyby. Opravit oba popisy na aktuální chování.
- **`_cmd_polish`, záloha DB:** Záloha se vytváří před zpracováním, nikoli „před prvním zápisem“. Přepíše tedy poslední použitelnou zálohu i při samých `unchanged`/`rejected`/`failed` výsledcích nebo při následném selhání načtení glosáře či návodu. Tím se ztratí možnost vrátit předchozí úspěšný průchod. Vytvořit zálohu líně těsně před prvním `commit_chapter_result`; předchozí zálohu nepřepisovat, pokud tento běh nic nezapíše. Doplnit přesný postup obnovy.
- **Manuální integrační ověření:** Fake CLI ignoruje většinu argumentů, ale manuální scénář nepožaduje ověřit celý skutečný kontrakt. Výslovně ověřit také `--ephemeral`, stdin přes poziční `-`, `-m <model>` a izolované `-C`; jinak jediný test reálného CLI nemusí zachytit nekompatibilitu zásadních přepínačů.
- **`stylist.polish` kontrakt a chybová tabulka:** Funkce slibuje `StylistError` při jakémkoli selhání spuštění, ale kolem `Popen` zachytává jen `FileNotFoundError`. `PermissionError`, neplatný executable nebo jiné `OSError` uniknou jako jiný typ. Zachytit `OSError` a převést jej na `StylistError`; přidat test alespoň pro existující, ale nespustitelnou cestu.
- **Rozhodnutí `guide_block`:** Starší bullet stále tvrdí, že `check_meaning_preserved` kontroluje jen význam a nemá signál pro registr, zatímco pozdější kód i rozhodnutí z kola 7 přidávají `register_changed`. Přepsat historickou pasáž tak, aby výslovně popisovala současnou kombinaci instrukce a následné verifikace.

## NITS

- **Souhrn tří guardrail vrstev:** Strukturální vrstva nezmiňuje kontrolu čísel a třetí vrstva nezmiňuje registr. Doplnit obě schopnosti.
- **Komentáře u preflightu:** Text stále uvádí, že bez preflightu by běh skončil `status="ok"`; aktuální logika „všechno failed“ nastavuje `"fatal"`. Aktualizovat rationale.
- **`_resolve_codex_cmd` a `polish` docstringy:** Několikrát stále odkazují na `subprocess.run`, přestože implementace používá `Popen`.
- **Preflight „JEDNOU“:** `_cmd_polish` provede preflight jednou, ale `stylist.polish` znovu volá `_resolve_codex_cmd` pro každou kapitolu. Buď předat již rozlišený příkaz dál, nebo odstranit tvrzení, že se řešení executable provádí pouze jednou.
- **Komentáře k dočasnému adresáři a poznámka pod kódem:** Stále obsahují obecné tvrzení, že nevzniká soubor s textem knihy, ačkoli stylizovaný text vzniká v `out.txt`. Omezit tvrzení výslovně na vstupní EN/CZ text.

## VERDICT

CHANGES_NEEDED