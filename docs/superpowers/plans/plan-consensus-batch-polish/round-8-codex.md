## IMPORTANT

- **Task 14, Step 2 — `loadChapter()` (`CURRENT_FINDINGS = body.findings`): oprava kola 7 nepokrývá opačné pořadí odpovědí.** Reprodukovatelný průběh:
  1. Běží resolve požadavek; uživatel klikne „Uložit“.
  2. Save dokončí zápis a následný GET načte ještě `resolved=false`.
  3. Resolve zapíše `true`; jeho odpověď dorazí první a `toggleResolved()` správně upraví aktuální objekt.
  4. Opožděná GET odpověď nahradí celé pole starým `false`.

  Výsledek: server má `true`, editor zobrazuje `false`, žádný požadavek již neběží. **Ověřeno deterministickou simulací přímo JavaScriptu z plánu.** Nejde o opakování opravené zachycené reference: tentokrát novější stav přepisuje samotné `loadChapter()`.

  **Oprava:** serializovat save/revert a jejich následné načtení vůči rozpracovaným resolve požadavkům. Například po zamčení editoru vyčkat na jejich uložené Promise před pokračováním operace. Doplnit deterministický regresní test obou pořadí odpovědí; ruční rychlé klikání z bodu 5b tuto garanci neověří.

## VERDICT

CHANGES_NEEDED