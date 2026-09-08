# plan-consensus: implementacni plan tezby terminologie z referenci

- Plan: docs/superpowers/plans/2026-09-07-reference-mining.md
- Spec: docs/superpowers/specs/2026-09-07-reference-mining-design.md
- Start: 2026-09-08T06:51:34
- max_rounds: bez limitu do konsensu (bezpecnostni strop 30)
- Kritici: Codex (read-only) + Claude (jediny, kdo edituje)

---

## Kolo 1 - 2026-09-08T07:22:43

- round-1-codex.md: 13 BLOCKING, 6 IMPORTANT, 3 NITS, verdikt CHANGES_NEEDED
- round-1-claude.md: 11 vlastnich BLOCKING (11/13 se kryje s Codexem, presneji
  receno vsech 13 Codexovych prijato + 2 dalsi vlastni IMPORTANT), verdikt CHANGES_NEEDED
- Vysledek: plan opraven na 3882 radku (z 3122). Vsechny zmeny popsany v
  round-1-claude.md. Nejzavaznejsi: JS funkce v Tasku 12 nebyly zapojene do
  render() (formular by nedelal nic z toho, co Task 12 slibuje); fresh-fixture
  bug v Tasku 9/14 (fresh vzdy False, vsechny testy predvyplneni by padaly).
- Shoda: NE (oba CHANGES_NEEDED). Pokracuje kolo 2.

## Kolo 2 - 2026-09-08T07:40:45

- round-2-codex.md: 7 BLOCKING, 4 IMPORTANT, verdikt CHANGES_NEEDED
- round-2-claude.md: 1 vlastni BLOCKING (normalize() misto textnorm.normalize_key
  v _merge_section), vsech 7 Codexovych BLOCKING + 2 IMPORTANT prijato po
  overeni (vetsina jsou chyby zavedene vlastnimi opravami z kola 1 - typicky
  vzorec druheho kola). Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4160 radku. Nejzavaznejsi opravy: vztahova must_decide
  roletka porad kopirovala md.default (spec vyzaduje prazdnou volbu), Task 12
  nesplnoval polovinu spec tabulky (sbaleni confirmed, popisek not_attested,
  odliseni necerstveho, varovani kolize aliasu), NFC/NFD nesoulad mezi
  count_en_surface a classify()/_finding()/_merge_section (tri mista se
  stejnou chybou), zamykani poli podle shody hodnoty misto provenance,
  Task 14 tri testy s neuplne vyplnenym povinnym cz.
- Shoda: NE (oba CHANGES_NEEDED). Pokracuje kolo 3.

## Kolo 3 - 2026-09-08T07:56:37

- round-3-codex.md: 5 BLOCKING, 3 IMPORTANT, 2 NITS, verdikt CHANGES_NEEDED
- round-3-claude.md: vlastni NIT (test-count komentare zkontrolovany strojove
  napric vsemi tasky 1-8), vsech 5 BLOCKING + 3 IMPORTANT Codexovych prijato
  po overeni. Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4290 radku. Ctyri z peti BLOCKING byly regrese z kola-2
  oprav (fresh-fixture v Tasku 11, tri JS chyby v undo/lock mechanismu -
  classificationNote() poradi podminek, undo prepisujici rucni upravy,
  provenance se nemenila po rucni editaci doloziteho pole, tlacitka navrhu
  zustavala natrvalo disabled). IMPORTANT: load_cache() nekontrolovala shodu
  klicu cz/en ani minimum parů, source neoverovano proti enum, alias
  collision warning bez NFC normalizace.
- Shoda: NE (oba CHANGES_NEEDED). Pokracuje kolo 4.

## Kolo 4 - 2026-09-08T08:15:15

- round-4-codex.md: 5 BLOCKING, 3 IMPORTANT, 2 NITS, verdikt CHANGES_NEEDED
- round-4-claude.md: 0 vlastnich novych nalezu, vsech 5 BLOCKING + 3 IMPORTANT
  + 2 NITS Codexovych prijato po overeni. Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4400+ radku. Ctyri z peti BLOCKING regrese z kola 2/3
  (sdilena item.provenance mezi cz a render, closure stav mizejici pri
  re-renderu, undo bez ochrany proti druhemu kliknuti, evidence_only nikdy
  nezobrazovala dukaz). Task-12 stav presunut z DOM closures na item._cz*/
  item._render* vlastnosti (strip_transient je ignoruje) - systemova oprava
  cele tridy regresi, ne dalsi izolovana zaplata. Task 13: fingerprint
  pocitany z manifestu zachyceneho pri nacteni (manifest_fingerprint), ne
  z aktualniho FS po tezbe.
- Shoda: NE (oba CHANGES_NEEDED). Pokracuje kolo 5.

## Kolo 5 - 2026-09-08T08:30:39

- round-5-codex.md: 2 BLOCKING, 3 IMPORTANT, verdikt CHANGES_NEEDED
- round-5-claude.md: 0 vlastnich novych nalezu, vsech 2 BLOCKING + 3 IMPORTANT
  Codexovych prijato po overeni. Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4470+ radku. Nejzavaznejsi: kolo-4 oprava (presun stavu
  z closures na item._cz*) sama zavedla novou variantu te same chyby -
  odemceni menilo provenienci hned, ne az skutecnou editaci, takze revert
  mizel po libovolnem re-renderu. Opraveno rozdelenim canBeReference (trida+
  cerstvost) od locked (navic vyzaduje !unlocked); provenience se meni az
  v oninput/onchange. Prvni nalezena mezera bez souvislosti s regresi:
  load_reference validovala jen typy poli, ne semantickou konzistenci cz/
  navrh vuci classification - pridana obrana do hloubky na dvou mistech.
  Vazba dukazu na hodnotu mela chybu v obou smerech (shown_cz and ... byla
  deravaa moc prisna zaroven).
- Shoda: NE (oba CHANGES_NEEDED). Pokracuje kolo 6.

## Kolo 6 - 2026-09-08T08:43:45

- round-6-codex.md: 3 BLOCKING, 2 IMPORTANT, verdikt CHANGES_NEEDED
- round-6-claude.md: 0 vlastnich novych nalezu, vsech 3 BLOCKING + 2 IMPORTANT
  Codexovych prijato po overeni. Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4570+ radku. Nejzavaznejsi: opravu shown_cz z kola 5 jsem
  jen naplanoval, nikdy nezapsal - realna procesni chyba, opraveno a poucen
  se overovat greppem. Task 12 UI-desync trida chyb (revert mizel po editaci,
  navrhy nedostupne po odemceni, dukaz nezivy) mela spolecnou pricinu - rucni
  DOM manipulace misto jednotneho render()-po-akci vzoru. Prepracovano
  systematicky: vsechny klikaci akce voraji render(), psani zustava line s
  onblur dorovnanim. Task 10: _seed_one guard pouzival .strip().lower()
  misto textnorm.normalize_key - NFC/NFD nesoulad.
- Shoda: NE (oba CHANGES_NEEDED). Pokracuje kolo 7.

## Kolo 7 - 2026-09-08T08:56:27

- round-7-codex.md: 2 BLOCKING, 1 IMPORTANT, 1 NIT, verdikt CHANGES_NEEDED
- round-7-claude.md: 1 vlastni podezreni vlozene primo do promptu (blur/click
  race), Codex ho nezavisle potvrdil jako BLOCKING. Vsech 2 BLOCKING + 1
  IMPORTANT + 1 NIT Codexovych prijato po overeni. Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4610+ radku. blur handler (valueField i alias pole) ted
  pouziva setTimeout(0) pred render(), aby neprerusil mousedown->click
  sekvenci na sousednim tlacitku. renderField.canBeReference prepsana na
  stabilni ref.fresh+classification misto mutable item.render (stejna trida
  chyby jako valueField mela pred kolem 5, jen na jinem miste).
  corpus_fingerprint/load_cache ted odchytavaji OSError z build_manifest po
  uspesnem isdir() (TOCTOU race) - nevim misto HTTP 500/nezachycene vyjimky.
- Shoda: NE (oba CHANGES_NEEDED). Pokracuje kolo 8.

## Kolo 8 - 2026-09-08T09:10:55

- round-8-codex.md: 2 BLOCKING, 1 IMPORTANT, verdikt CHANGES_NEEDED
- round-8-claude.md: 0 vlastnich novych nalezu, oba BLOCKING + IMPORTANT
  prijaty po overeni. Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4660+ radku. load_corpus() ted bere manifest pred i po
  parsovani a zveda ValueError pri nesouladu (TOCTOU race behem cteni
  desitek EPUBu). Task 2 kroky 7/10 prestaly delat git add data/... (cela
  slozka je v .gitignore, zustala jen kopie souboru). Hromadne
  accept/undo prepracovano na zivou shodu hodnoty pri samotnem zpet
  (pendingAcceptAllChanges) misto jednosmerneho mazani zaznamu pri prvni
  odchylce - resi scenar pouzij navrh -> vrat navrh -> vrat davku, ktery by
  drivejsi verze ztratila. Vedome zdokumentovany kompromis proti kola-4
  namitce (coz uz nejde uspokojit obojí bez plneho undo/redo zasobniku).
- Shoda: NE (oba CHANGES_NEEDED). Pokracuje kolo 9.

## Kolo 9 - 2026-09-08T09:26:27

- round-9-codex.md: 0 BLOCKING, 2 IMPORTANT, verdikt CHANGES_NEEDED
- round-9-claude.md: 0 vlastnich novych nalezu, oba IMPORTANT prijaty po
  overeni. Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4780+ radku. undoAcceptAllScoutSuggestions ted cisti
  _czActiveKey/_renderActive pri vraceni kazdeho pole (jinak by zdanlive
  nevinne tlacitko navrhu tise obnovilo hodnotu, kterou bulk-undo prave
  zrusilo). Ctvrte kolo pozadavku na automatizovane JS testy - tentokrat
  prijato: pridan tests/test_review_ui_state.py testujici ctyri ciste funkce
  (bez DOM) pres Node jako subprocess, pokryva vsechny tri regrese z oblasti
  hromadneho prijeti/vraceni (kola 4, 8, 9). Testy overeny skutecnym
  spustenim (projdou proti aktualni verzi, spadnou proti rozbite).
- Shoda: NE (Codex CHANGES_NEEDED, Claude CHANGES_NEEDED - i kdyz Codex
  poprve bez BLOCKING). Pokracuje kolo 10.

## Kolo 10 - 2026-09-08T12:51:01

- Codex poprve narazil na vycerpany kredit (usage limit), retry doprosel.
- round-10-codex.md: 0 BLOCKING, 2 IMPORTANT, 2 NITS, verdikt CHANGES_NEEDED
- round-10-claude.md: 0 vlastnich novych nalezu, vse prijato po overeni.
  Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4830+ radku. Test test_bulk_undo_clears_active_
  suggestion_flag byl falesne zeleny (nikdy nenastavil _renderActive=true
  pred undo) - opraveno explicitni simulaci kliku pred volanim undo, pridan
  analogicky test pro _czActiveKey. valueField/renderField revert.onclick
  ted taky cisti _czActiveKey/_renderActive (jinak by po znovu-odemceni
  tlacitko navrhu ukazovalo stary stav zpet). Dve NIT opravy: _JS_SOURCE
  komentar prepsan (neni bajtova shoda, jen shoda chovani), instrukce pro
  test zastaralosti opravena (nesmi se znovu spustit reference).
- Shoda: NE (oba CHANGES_NEEDED, Codex podruhe bez BLOCKING). Pokracuje
  kolo 11.

## Kolo 11 - 2026-09-08T13:01:38

- round-11-codex.md: 0 BLOCKING, 1 IMPORTANT, 1 NIT, verdikt CHANGES_NEEDED
- round-11-claude.md: 0 vlastnich novych nalezu, oba prijaty po overeni.
  Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4870+ radku. Task 2 krok 8 doplnen o tri chybejici
  pravidla ze specu (pozicni parovani suggested_cz u vyctu, tri reseni
  bad_scope_key, pravidlo pro alias vyzadujici vlastni preklad - posledni
  z nich check_draft.py vubec nedetekuje, je to cisty rucni krok). Task 9
  guide-only vetev _merge_section opravena analogicky ke kolu 4
  (provenance=human jakmile radek v guide.json existuje, ne jen kdyz
  cz neni prazdne).
- Shoda: NE (oba CHANGES_NEEDED, Codex treti kolo za sebou bez BLOCKING).
  Pokracuje kolo 12.

## Kolo 12 - 2026-09-08T13:10:42

- round-12-codex.md: 0 BLOCKING, 0 IMPORTANT, 0 NIT, verdikt CONSENSUS
  (poprvé - prazdna kritika).
- round-12-claude.md: 1 vlastni novy nalez (Pridej dvojici nemazalo
  relationships_reviewed - nova dvojice s tichym defaultem vyka mohla
  proklouznout jako zkontrolovana). Opraveno. Verdikt CHANGES_NEEDED.
- Vysledek: plan cca 4880+ radku. add.onclick ted nastavuje
  relationships_reviewed=false pri pridani kazde nove dvojice.
- Shoda: NE (Codex CONSENSUS, ale Claude CHANGES_NEEDED - vlastni novy
  nalez). Pokracuje kolo 13, aby Codex mohl tenhle fix overit.

## Kolo 13 - 2026-09-08T13:18:45

- round-13-codex.md: overil Claude nalez z kola 12 jako validni a fix jako
  spravny a uplny; zadny dalsi nalez. Verdikt CONSENSUS.
- Claude vlastni pruchod (Task 13 CLI, struktura planu) - nic noveho.
  Verdikt CONSENSUS.
- SHODA DOSAZENA ve stejnem kole. final-verdict.md zapsan.
