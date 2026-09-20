## IMPORTANT

- Task 2, revizní `except FatalRunError`: „minimální transakce B“ zapíše `questions=[]`, ale `state.begin_chapter()` už na začátku smazal všechny dosud nezodpovězené otázky kapitoly. Při `--retry-flagged` a fatálním selhání revize se tedy nenávratně smažou staré otázky, obdobně jako dříve mentions. Oprava: před `begin_chapter()` snapshotovat otevřené otázky a při checkpoint commitu je obnovit, případně explicitně sestavit validní náhradu z aktuálního výsledku; přidej regresní test s existující otevřenou otázkou.

- Task 2, statické markery `===PREKLAD===`/`===METADATA===`/`===KONEC===`: legitimní překlad obsahující některý marker samostatně na řádku je nerozlišitelný od protokolového markeru a bude odmítnut jako duplicita. Dosavadní test kryje jen marker uvnitř řádku. Oprava: použít pro každé volání nekolizní nonce delimitery, nebo definovat a implementovat jednoznačné escapování; přidej test pro doslovný marker na vlastním řádku v próze.

## VERDICT

CHANGES_NEEDED