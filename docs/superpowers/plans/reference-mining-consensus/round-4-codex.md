## BLOCKING

- **Task 9, krok 3 (`_merge_section`)** — Priorita `guide > reference` stále neplatí pro platnou postavu s `render="keep"` a prázdným `cz`. `human_cz` je falsy, takže se převezme `ref_cz` a `provenance="reference"`, přestože řádek už rozhodl člověk. Oprava: přítomnost odpovídajícího řádku v `guide.json` musí zachovat i platné prázdné `cz` a nastavit lidskou provenienci; přidat test `guide render=keep, cz="" + fresh confirmed reference`.

- **Task 12, krok 3 (`valueField` / `renderField`)** — Jediná sdílená `item.provenance` je měněna dvěma nezávislými ovládacími prvky. Po ruční změně `cz` může „vrátit zpět“ u `render` nastavit provenienci zpět na `reference`; následující `render()` pak ruční `cz` zamkne a zobrazí jako doložené. Oprava: sledovat stav obou polí samostatně, nebo obnovit `reference` provenienci pouze tehdy, když se obě hodnoty rovnají původním referenčním hodnotám.

- **Task 12, krok 3 (`valueField`, `renderField`, `render`)** — Undo stav je pouze v closures DOM prvků. Jakýkoli následný `render()` (hromadné přijetí, přidání vztahu) zahodí `before`, aktivní „zpět“ i stav odemčeného referenčního pole. Akce tedy nejsou vratné, jak požaduje spec. Oprava: držet undo/lock stav mimo DOM, klíčovaný sekcí, indexem a polem, a rekonstruovat ovládání z tohoto stavu.

- **Task 12, krok 3 (`classificationNote` / `valueField`)** — `evidence_only` nikdy nezobrazí důkaz. `valueField` vykresluje počty pouze uvnitř `if (backed)`, ale `evidence_only` má prázdné `cz`, `provenance="none"` a `backed=false`; `classificationNote` tuto třídu také ignoruje. Oprava: vykreslit její `hits`, `books`, `per_form` a `matched_forms` nezávisle na předvyplnění.

- **Task 12, krok 3 (`acceptAllScoutSuggestions`)** — Druhé kliknutí na „přijmout všechny“ nastaví `lastAcceptAllChanges=[]` a zruší možnost vrátit první akci. Kontrola pouze přes `current === applied` navíc přepíše pozdější ruční či individuální akci, pokud se hodnota shodou okolností vrátí na stejný text. Oprava: během aktivního undo další hromadné přijetí zakázat a při každé následné editaci explicitně invalidovat příslušný záznam změny.

## IMPORTANT

- **Task 12, kroky 1–4** — Tři automatické testy nespouštějí žádný JavaScript; pouze ručně upravují Python payload. Prošly by i při odstranění `valueField`, `renderField`, obou undo funkcí, zamykání, sbalení i varování. Oprava: testovat stavové přechody skutečného JS nebo DOM; minimálně pokrýt přerenderování, křížové změny `render`/`cz`, opakované accept-all a `evidence_only`.

- **Task 12, krok 3 (`aliasCollisionWarnings`)** — Varování se počítají jen při `render()`. Editace aliasu aktualizuje data, ale varování nepřepočítá; protože normalizovaný draft začíná bez kolizí, nově vytvořená kolize nebude před uložením vůbec zobrazena. Oprava: po změně aliasů varování přepočítat a aktualizovat příslušné buňky.

- **Task 13, krok 3 (`_cmd_reference`)** — Ukládaný corpus fingerprint se po těžbě znovu počítá z aktuálního filesystému místo z `corpus.manifest`, ze kterého vznikly výsledky. Změna EPUBu během běhu tak může uložit nový fingerprint k výsledkům ze starého textu a UI je označí jako fresh. Oprava: uložit hash zachyceného `corpus.manifest`; aktuální manifest počítat pouze při následné kontrole čerstvosti.

## NITS

- **Task 12, krok 3 (`buildRowsInto`)** — Parametr `nameKey` se nepoužívá; odstranit jej z rozhraní a call sites.

- **Task 15, krok 2** — Checklist uvádí `MIN_BOOKS`; skutečný klíč je `REFERENCE_MIN_BOOKS`.

## VERDICT

CHANGES_NEEDED