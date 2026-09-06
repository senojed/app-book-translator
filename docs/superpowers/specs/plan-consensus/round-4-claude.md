# Round 4 — Claude critique

## Claude's own findings

### NITS
- `add_variant()` doplněno do glossary API (potřeba pro `variants` seznam).
- `variants` doplněno i do glossary schema `{term_en: {cz, variants, ...}}`.

Žádné vlastní BLOCKING/IMPORTANT tentokrát - spec je po 3 kolech konzistentní,
zbývají loose ends které Codex trefil přesně.

## On Codex's points

### Agreed + fixed
- **BLOCKING: víc blocking otázek na kapitolu vs `answer` po jedné** — opraveno:
  `answer` vrací `needs_human` kapitolu na `pending` jen když už pro její
  `chapter_idx` nezbývá nezodpovězená `blocking` otázka. Stavový automat i
  requeue pravidla sjednoceny.
- **IMPORTANT: staré reference na `used_terms`** — opraveno: vyčištěno ze
  schema komentáře, pořadí stavby i testů. `term_mentions` plní výhradně
  `concordance.build_mentions`.
- **IMPORTANT: `LoggedLLMClient` vs `PipelineLLMClient` + `agent` v konstruktoru**
  — opraveno: jednotný název `PipelineLLMClient`, vytváří se zvlášť pro každé
  volání agenta (levný objekt, `agent` = label do logu).
- **IMPORTANT: guide vs glossary jako zdroj pravdy pro termín→CZ** — opraveno:
  glosář je jediný zdroj. `guide_as_prompt_block()` emituje styl/vztahy/
  keep-translate rozhodnutí, ale ne dvojice termín→překlad. Po `answer` má
  `approved` glosář přednost a v promptu ho nic nepřebíjí.
- **IMPORTANT: odkud "známé varianty" pro `inconsistency`** — opraveno: glosář
  dostal `variants: []` (z term_mentions / kandidátů / lidských odpovědí).
  `inconsistency` = CZ obsahuje `variant` ≠ kanonický `cz`; `omission` = ani
  `cz` ani `variant`. Explicitně přiznáno: úplný novotvar chytne až drift check.
- **IMPORTANT: kanárek + transakční hranice `processing`** — opraveno: krok 0
  (`processing`) se commituje před 1. LLM voláním; fatal → kapitola zůstane
  `processing`, žádná nedostane finální stav, další `run` `processing` vrátí
  na `pending`. Formulace "fatal nesahá na kapitoly" upřesněna.
- **NIT: model/ceny jako config + validační krok** — opraveno: explicitní věta
  v sekci Modely ("před pilotem ověřit proti Anthropic docs").
- **NIT: lock chybí v adresářové struktuře** — opraveno: `data/` a `output/`
  doplněny do stromu s obsahem (state.sqlite3, guide*.json, glossary.json,
  .book-translator.lock).

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — žádné vlastní BLOCKING/IMPORTANT, ale Codexův 1 BLOCKING
(multi-blocking otázky) byl reálný a několik IMPORTANT byly loose ends po
předchozích kolech. Konvergence pokračuje (kolo 1: 10+, 2: 12, 3: 8, 4: 8 ale
menší). Jedno potvrzovací kolo.

## Summary for log
Kolo 4: Codex 1 BLOCKING (multi-blocking otázky na kapitolu) + 5 IMPORTANT
(loose ends: used_terms zbytky, wrapper name, guide/glossary source of truth,
variants zdroj, kanárek wording) + 2 NIT. Claude bez vlastních
BLOCKING/IMPORTANT. Vše přijato: answer řeší 1 otázku a needs_human→pending jen
když nezbývá blocking; glosář = jediný zdroj termín→CZ, guide neemit termíny;
glossary +`variants`; kanárek/processing transakčně dotažen; used_terms úplně
pryč; nits (config validace, dir strom). Sporné: nic. Blíží se konsenzus.