## IMPORTANT

- **Task 5/12 — chybí test předání neprázdného návodu (spec 2520–2523).** `_polish_env` vždy vrací prázdný `guide_block`; fake Codex testy kontrolují jen CZ text. Odstranění předání `guide_block` nebo `{guide_section}` ze skutečného promptu tedy projde všemi uvedenými testy. Návod přitom nese schválená pravidla rejstříku. **Oprava:** přidej konkrétní test `_cmd_polish`, který ověří předání neprázdného návodu do `stylist.polish`, a test `stylist.polish` s fake procesem, který ověří jeho přítomnost ve stdin. Přesuň tento požadavek z obecného „executor doplní“ do příslušných tasků.

## VERDICT

CHANGES_NEEDED