## IMPORTANT

- **Task 14, Step 2 — `toggleResolved`, `loadChapter`, handler Uložit (ř. 3467–3520, 3615): zastaralá reference na objekt nálezu.** Oprava z kola 6 odstranila zastaralou DOM referenci, ale `finding` může také zastarat. Reprodukce:
  1. Zaškrtnutí `f1` spustí požadavek, který ještě nedoběhl.
  2. Uložit zůstává dostupné; uložení a následný GET doběhnou první. `loadChapter()` nahradí `CURRENT_FINDINGS` novými objekty, kde je `f1.resolved=false`.
  3. Resolve následně zapíše `true` a vrátí 200. `toggleResolved()` upraví **starý objekt**; `renderFindings()` vykreslí nový objekt s `false`.

  Výsledkem je nezaškrtnutý, odemčený checkbox, přestože DB obsahuje `true`. Potvrzeno řízenou Node simulací funkce převzaté z plánu. **Oprava:** po úspěšné odpovědi vyhledej aktuální nález v `CURRENT_FINDINGS` podle `id` a aktualizuj jej, pokud stále existuje. Přidej regresní test pořadí resolve → save + reload → dokončení resolve.

## NITS

- **Task 5, Interfaces (ř. 769–777): zastaralý kontrakt `_commit_polish_result`.** Signatura vynechává `rendered_terms` a text výslovně tvrdí „NENÍ parametr“. Implementace ve Step 4 parametr správně obsahuje a dávka jej předává. Aktualizuj rozhraní podle finální signatury a popiš fallback pouze při `None`.

## VERDICT

CHANGES_NEEDED