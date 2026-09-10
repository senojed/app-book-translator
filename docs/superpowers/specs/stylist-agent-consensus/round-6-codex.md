## BLOCKING

- **Testování ř. 984–987 a tabulka ř. 1022 vs. implementace ř. 760–770:** Plán současně vyžaduje při selhání všech kapitol `status="ok"` i `status="fatal"` s návratovým kódem 1. Oprava z kola 5 tedy nebyla promítnuta všude; implementace a předepsaný test si odporují. Opravit testovací scénář a tabulku na `status="fatal"` a `return 1`.

## IMPORTANT

- **`stylist.polish`, timeout ř. 382–385:** Po `taskkill` následuje neomezené `proc.wait()`. Pokud `taskkill` selže, timeoutová větev může zablokovat navždy. Kontrolovat návratový kód `taskkill`, použít fallback `proc.kill()` a vždy omezený druhý `wait`; přidat test selhání ukončení procesu.

- **Rozhodnutí ř. 1122–1129 – deterministická kontrola čísel/dat:** Zdůvodnění odmítnutí je příliš široké. Není nutný úplný NLP extraktor; normalizované porovnání množiny arabských čísel, desetinných hodnot, časů a číselných dat je levné a pokryje vysoce rizikové faktické změny. Precedens z původní pipeline není rozhodující, protože nový krok mění již schválený text. Přidat úzkou fail-closed kontrolu a slovně zapsaná čísla výslovně ponechat mimo rozsah.

- **Prompt a guardraily ř. 258–280, 424–477:** Stylista nezná překladový návod a kontrola před/po výslovně ignoruje stylistické rozdíly. Může tedy změnit tykání/vykání, hlas vypravěče nebo ustálený rejstřík tam, kde je angličtina nejednoznačná; EN-vs-CZ kritik to nemusí odhalit. Nejde o zamítnuté automatické hodnocení „je styl lepší“, ale o zachování již schváleného rejstříku. Předat relevantní část guide nebo rozšířit kontrolu před/po o změnu hlasu a registru.

## NITS

- **Ř. 519 a 607:** Stále tvrdí, že baseline pochází z `notes`, respektive ukazují `rendered_terms=[]`; implementace správně používá čerstvý výpočet a předchozí mentions. Aktualizovat zastaralý text.

- **Ř. 859–862 a 1092:** Dokumentace testu stále mluví o `subprocess.run`, přestože návrh používá `Popen.communicate`.

- **Ř. 1023–1024:** Tabulka uvádí tiché přeskočení, ale ř. 720–732 a rozhodnutí ř. 1119–1121 vyžadují hlášení.

- **Ř. 224:** Tvrzení, že text knihy není nikdy zapsán na disk, je nepravdivé; `-o` zapisuje celou stylizovanou kapitolu do `out.txt`. Formulovat pouze jako „vstupní/originální text se nezapisuje samostatně“ a nezaručovat bezpečné smazání dočasného souboru.

- **Ř. 581–592:** Osm hex znaků SHA-1 je zbytečně slabý auditní identifikátor. Použít celý SHA-256; nemá to praktickou režii.

## VERDICT

CHANGES_NEEDED