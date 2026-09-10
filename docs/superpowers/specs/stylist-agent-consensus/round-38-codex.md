## NITS

- Ř. 1935–1939: komentář stále tvrdí, že cost guard běží před/mimo stylizaci a nemůže nést Codexův obsah. Kolo 37 toto výslovně vyvrátilo. Uvést, že bezpečnost zajišťuje redakce ve `_polish_one_chapter`.
- Ř. 1476–1478: próza tvrdí „jediné místo“ pro `report.append`, ale kód má tři větve (fatal, interrupt, společná). Přesný invariant je „právě jeden append na iteraci“.
- Ř. 2721–2724: navržený test s „patchnutým `report`“ neodpovídá signatuře `_polish_one_chapter`, která už `report` nepřijímá. Testovat návratový `dict` a počet appendů v `_cmd_polish`.

## VERDICT

CONSENSUS - plan is good enough to execute.