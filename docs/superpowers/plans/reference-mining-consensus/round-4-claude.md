# Round 4 — Claude critique

## Claude's own findings

Žádné nové vlastní nálezy tohle kolo - soustředil jsem se na ověření
Codexových bodů (všechny se týkají oblastí, které jsem sám v kole 2-3
přepisoval, takže jde o stejný vzorec: cizí review chytá regrese z mých
vlastních předchozích zásahů rychleji, než bych je našel sám). Test-count
komentáře jsem tentokrát zkontroloval strojově NAVÍC (skript porovnávající
`def test_` v hranicích každého tasku s tvrzeným počtem) - všech 8
create-new-file tasků (1-8, 12) sedí přesně.

## On Codex's points

5 BLOCKING, 3 IMPORTANT, 2 NITS - všechny přijaty po ověření.

### Agreed + fixed

- **Task 9: postava s `render="keep"` a prázdným `cz` ztrácela lidskou
  provenienci.** Ověřeno trasováním `_merge_section`: `human_cz` je pro
  prázdné `cz` falsy, takže se vzalo `ref_cz` a `provenance="reference"`,
  přestože `guide.json` už měl uložený řádek (validate() vyžaduje neprázdné
  `cz` jen při `render="translate"`, takže tenhle stav je zcela legitimní,
  uložený). *Fix:* `human_decided = bool(g)` - existence řádku v `guide.json`
  JE lidské rozhodnutí, i s prázdným `cz`. Nový test
  `test_character_keep_with_blank_cz_is_still_human_decided`.
- **Task 12: sdílené `item.provenance` mezi `cz` a `render`.** Vrácení
  jednoho pole by tiše přepsalo stav toho druhého (Codexův přesný scénář:
  ruční úprava `cz` → „vrátit zpět" u `render` → `item.provenance =
  "reference"` → `cz` se při příštím `render()` znovu zamkne jako doložené).
  *Fix:* nová `fieldProvenance(item, field)` čte `item._czProvenance` /
  `item._renderProvenance` s fallbackem na `item.provenance` - obě pole mají
  teď NEZÁVISLÝ stav.
- **Task 12: undo/lock stav žil jen v closures DOM prvků, `render()` ho
  zahazoval.** Kterákoli jiná akce (přijmout všechny, přidat vztah) staví
  celý strom znovu a smaže rozeditovaný stav uprostřed práce. *Fix:*
  přesunuto na `item._cz*`/`item._render*` (vlastnosti s podtržítkem, které
  `strip_transient` při ukládání ignoruje) - stav přežije libovolný
  `render()`, dokud item existuje.
- **Task 12: `evidence_only` nikdy nezobrazovala důkaz.** `valueField`
  vykreslovala čísla jen uvnitř `if (backed)`, ale `evidence_only` má vždy
  `backed=false` (prázdné `cz`). *Fix:* nezávislý blok pro
  `ref.classification === "evidence_only"` mimo `backed`.
- **Task 12: druhé kliknutí na "přijmout všechny" zahodilo možnost vrátit
  první dávku; kontrola `current === applied` mohla shodou hodnot přepsat
  pozdější ruční zásah.** *Fix:* tlačítko je `disabled`, dokud čeká
  nevyřízené "zpět"; nová `invalidateAcceptAllChange()` odstraní záznam
  z `lastAcceptAllChanges`, jakmile se pole ručně změní (volá se ze všech
  `onChange` callbacků v `render()`) - undo pak funguje nad tím, co zbylo,
  bez porovnávání hodnot.

### Agreed + fixed (IMPORTANT)

- **Task 12: tři testy netestují žádný JS.** Souhlasím věcně - stejné
  škálovací rozhodnutí jako v kole 2 (žádná nová DOM test infrastruktura
  v tomhle plánu), teď navíc podepřené tím, že logika, která se rozbíjela
  (closures, sdílená provenience), byla v tomto kole opravena na
  perzistentní `item._*` stav právě proto, aby ji šlo příště otestovat i bez
  prohlížeče, kdyby se DOM testy do projektu později přidaly.
- **Task 12: `aliasCollisionWarnings()` se počítala jen při `render()`,
  živá editace aliasu novou kolizi neukázala.** *Fix:* `al.onblur = () =>
  render()` - přepočet po dokončení editace (ne po každém stisku klávesy,
  to by rušilo psaní).
- **Task 13: uložený corpus fingerprint se počítal z AKTUÁLNÍHO
  filesystému (`corpus_fingerprint(corpus.source_root)`) až PO těžbě, ne
  z manifestu, ze kterého nálezy skutečně vzešly.** Změna EPUBu během běhu
  (může trvat minuty kvůli modelu) by uložila otisk nového textu k výsledkům
  ze starého - `review` by je pak označil za čerstvé, ačkoli nejsou. *Fix:*
  nová `reference_mine.manifest_fingerprint(manifest)` hashuje předaný
  manifest přímo, `_cmd_reference` ji volá na `corpus.manifest` (zachycený
  při načtení). Dva nové testy, včetně ověření, že dává stejný výsledek jako
  `corpus_fingerprint()` nad stejným manifestem (jinak by `_is_fresh`
  v `guide.py`, která pořád volá `corpus_fingerprint`, nikdy nenašla shodu).

### Agreed + fixed (NITS)

- `buildRowsInto`'s `nameKey` parametr nepoužitý - odstraněn ze signatury
  i ze všech čtyř volání.
- Task 15 checklist: `MIN_BOOKS` → `REFERENCE_MIN_BOOKS`.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Čtvrté kolo pokračovalo v konzistentním vzorci - 4 z 5 BLOCKING byly regrese
z vlastních kolo-2/3 oprav (sdílená provenience mezi dvěma nezávislými poli,
closure stav mizející při re-renderu, undo bez ochrany proti druhému
kliknutí). Nejzávažnější systémový problém: celá rodina Task-12 chyb od
kola 2 pramenila ze stejného architektonického rozhodnutí (stav v closures
DOM prvků místo v datovém modelu) - tohle kolo ho konečně řeší
systematicky (`item._cz*`/`item._render*`), ne další izolovanou záplatou,
což by měl být konec téhle konkrétní třídy regresí.

Task 13 nález (fingerprint z aktuálního disku místo ze zachyceného
manifestu) je jemný, ale reálný časový problém - korpus se načítá jednou,
těžba (LLM volání) může trvat minuty, a mezitím se může FS změnit.

Všech 32 Python bloků a 1 JS blok znovu ověřeno strojově. Test-count
komentáře nově ověřeny skriptem porovnávajícím tvrzený počet s hranicemi
každého tasku, ne jen bodově tam, kde na to upozornil Codex.
