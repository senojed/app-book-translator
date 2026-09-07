## IMPORTANT

- **Krok 0, ř. 67–71, stále nereportuje všechny vady, které má opravit. Skript vypisuje jen kolize aliasů a `/`/`or`, nikoli 9 chybných `must_decide`, 4 vadné vztahy ani nepovrchové hodnoty jako `Stroger's (hospital)`, `Warden(s)`, `the Merlin (title)`, `grasshopper (nickname for Molly)`, `evocation words (...)` a alias `Demonreach (nickname given by Harry)`. Přesné hledání je u nich nefunkční. Report i test musí kontrolovat všechny postpodmínky normalizace.

- Normalizace vztahů řeší pouze lomítka, nikoli aliasově duplicitní dvojice. Draft obsahuje například `Harry|Lara Raith` i `Harry|Lara` a `Harry|Ebenezar McCoy` i `Harry|Ebenezar`; příslušné `must_decide` cílí jen na krátké varianty. Konce vztahů je nutné převést na kanonická jména, dvojice sloučit a následně přemapovat vztahové `scope_key`.

- Sekčně oddělené `id` neřeší globální identitu glosáře. Draft obsahuje `Demonreach` současně jako postavu a místo; dále `Foo dog`, `skinwalker` a `naagloshii` kolidují mezi kanonickými termíny a aliasy postav. `_seed_one` vyhledává povrch globálně a přesná kanonická kolize se tiše přepíše; navržený guard chrání jen nález přes alias. Krok 0 nebo datový model musí explicitně vyřešit mezisekční homonyma a kolize.

- Predikát souvýskytu používá všechny aliasy, ale draft obsahuje neidentifikační či nejednoznačné aliasy: `sir`, `Captain`, `kid`, `apprentice`, sdílené `Hoss` apod. Ty mohou rozšířit `E` téměř na celý korpus a znehodnotit klasifikaci `proposed`. Normalizace musí aliasy pročistit, nebo `books_with_en` používat jen primární/bezpečné tvary.

- Spec požaduje aliasy v `SurfaceItem` a budoucím scoutovi ukládá synonyma do `aliases`, ale `merge_simple` ani POST allowlist aliasy míst a termínů nepřenášejí. Takové aliasy se před glosářem ztratí. Přidat je do merge kontraktu, UI payloadu a allowlistu.

## NITS

- Ř. 71 stále uvádí „operace na 26 řádcích“, zatímco ř. 55 správně uvádí přibližně 39.
- Ř. 534 znovu obecně tvrdí, že vzor již používá `must_decide`, přestože ř. 512–516 správně rozlišují textovou a vztahovou větev.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item