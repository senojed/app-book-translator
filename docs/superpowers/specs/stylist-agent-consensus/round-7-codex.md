## IMPORTANT

- Ř. 271, 480–486, 734–736, 1294 — ochrana tykání/vykání, hlasu a rejstříku spoléhá pouze na pokyn stylistovi. Kritik návod ve skutečnosti nedostává a `check_meaning_preserved` kontroluje jen význam. Stylista tedy může změnit registr a výstup projde. Rozšiřte kontrolu před/po explicitně o registr, oslovení a hlas vypravěče, případně jí předejte `guide_block`.

- Ř. 31–36, 1043–1051, 1247–1253 — odmítnutí historie/rollbacku je v rozporu s tvrzením, že uživatel je konečný soudce kvality. Výsledek se uloží dříve, než jej uživatel posoudí, a hash původní text neobnoví. Argument precedentem `revise_chapter` tuto novou experimentální cestu neřeší. Minimálně vytvořte před během obnovitelnou zálohu DB, nebo přidejte preview/dry-run před zápisem; není nutná plná verzovaná historie.

- Ř. 83–102 — validace odpovědi kritika stále není fail-closed. Top-level JSON jiné než objekt vyvolá `AttributeError` bez deklarovaného retry; nedict položky ve `findings` se tiše zahodí, takže `{"verdict":"pass","findings":[1]}` projde jako čistý výsledek. Validujte top-level `dict` i všechny položky `findings`; neplatný tvar musí aktivovat retry a následně výjimku.

- Ř. 344–346 — timeoutová cesta může stále viset neomezeně v samotném `subprocess.run(["taskkill", ...])`. Omezený následný `proc.wait()` tento případ neřeší. Přidejte `timeout` pro `taskkill` a zachyťte `TimeoutExpired`/`OSError` před fallbackem na `proc.kill()`.

- Ř. 1094–1097 — testovací požadavek stále tvrdí, že při selhání všech kapitol má běh `status="ok"`, zatímco implementace a tabulka vyžadují `"fatal"`. To je přímý rozpor určující opačné očekávání testu. Opravte odstavec na `status="fatal"` a `return 1`.

## NITS

- Ř. 1239–1245 versus 1285–1291 — sekce rozhodnutí současně tvrdí, že deterministická kontrola čísel zůstává mimo rozsah, a že byla přidána. První bod přepište tak, aby mimo rozsah ponechal pouze jména, slovně zapsaná čísla a nepokryté formy dat.

## VERDICT

CHANGES_NEEDED