# Round 21 — Claude critique

## Claude's own findings

### BLOCKING / IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Vlastní sweep na `str.count` a `_fake_codex` stdin - Codex oba zachytil,
nic dalšího.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `str.count(surface)` neodpovídá pravidlům konkordance:**
  ověřil jsem přímo `src/concordance.py` - `leak` používá
  `_contains_surface` (case-insensitive, word-boundary regex),
  `inconsistency` používá `find_form_occurrences` (stem + lowercase).
  `str.count` (case-sensitive, přesná shoda) by přidaný výskyt s jinou
  velikostí písmen / v jiném pádu minul. Přepsáno na
  `len(concordance.find_form_occurrences(text, surface))` pro obě strany
  (funkce stemuje + lowercasuje, `stem()` má `.lower()` - ověřeno) -
  absolutní nepřesnost počtu nevadí, porovnává se relativní rozdíl touž
  funkcí. Přidán regresní scénář s pádovým + case rozdílem.
- **IMPORTANT - `_fake_codex` v long-input testu nečte stdin:** správně -
  test by prošel i kdyby se dlouhý prompt cestou zahodil. Přepsán na
  fake, co stdin ČTE, vytáhne si z něj CZ text (regex mezi promptovými
  značkami) a vrátí ho upravený - test pak ověří délku (celý vstup
  dorazil).
- **IMPORTANT - chybová tabulka "stejný nález → přijato" po kolo-20
  nepravdivá:** ověřeno, řádek rozdělen na dvě - "stejný klíč + stejný/
  nižší počet výskytů → přijato" vs. "stejný klíč + víc výskytů →
  zahozeno".
- **NIT - docstring nadpis + opt-in odstavec zastaralé (kolo 20):**
  nadpis "17-18" → "17-20", odstavec doplněn o závaznou kontrolu v
  `polish()` (kolo 20), CLI označena jen jako časný UX guard.
- **NIT - "Mimo rozsah" směrový odkaz "výš" míří dolů:** ověřeno (sekce
  "Bezpečnostní rozhodnutí" je na ř. 68, "Mimo rozsah" na ř. 18) -
  opraveno na "hned NÍŽE".

## Claude VERDICT

Po aplikaci 3 IMPORTANT + 2 NITS z kola 21 (0 BLOCKING) nenacházím nic
dalšího.

`CONSENSUS`

## Summary for log

Kolo 21: Codex našel 3 IMPORTANT (0 BLOCKING - poprvé od kola 16 zase
bez BLOCKING) + 2 NITS, všechny navazují na kolo-20 opravy. `_polish_
rejected` počítá výskyty přes `concordance.find_form_occurrences` (ne
`str.count` - case/skloňování); long-input test má fake, co stdin
SKUTEČNĚ čte a ověří celistvost; chybová tabulka rozdělena na dva
řádky. Docstring dotažen na kolo 20, směrový odkaz opraven. Čeká se na
kolo 22 Codexu (20/30 stropu využito).
