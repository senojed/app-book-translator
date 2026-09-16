# Round 10 — Claude critique

## Claude's own findings
### BLOCKING
(žádné vlastní nové - Codexovo BLOCKING níž jsem nezávisle ověřil trasováním kódu)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **BLOCKING (`split_sections()` stále nebezpečná i po řádkovém
  kotvení):** Souhlasím, ověřil jsem TRASOVÁNÍM přesně na testu
  `test_marker_like_text_inside_metadata_json_does_not_confuse_parser` -
  moje kolo-9 validace (`_marker_line_positions`) SPRÁVNĚ potvrdí, že
  `===KONEC===` je přesně JEDNOU na vlastním řádku (ten skutečný,
  koncový). ALE `split_sections()` na tohle nebere ohled - dělá si
  VLASTNÍ nezávislé substring hledání (`after.split(MARK_END, 1)[0]`).
  Pro `after` = JSON blob + inline "===KONEC===" v `note` poli + reálný
  koncový marker, `.split(MARK_END, 1)[0]` najde PRVNÍ substring výskyt -
  to je ten INLINE (uprostřed JSON), ne ten skutečný na konci - metadata
  sekce se uřízne uprostřed, JSON se rozbije. Validace výš a extrakce
  sekcí byly dva NEZÁVISLÉ mechanismy, co jsem mylně považoval za
  provázané.

  **Oprava:** `_parse()` `split_sections()` vůbec nevolá - sekce řeže
  PŘÍMO slicingem podle OVĚŘENÝCH pozic z `_marker_line_positions()`
  (`raw[trans_pos[0]+len(MARK_TRANSLATION):meta_pos[0]]` pro překlad,
  analogicky pro metadata). `split_sections()` samotná zůstává v
  `src/llm/parsing.py` nedotčená (obecná utilita, vlastní testy) - jen
  `translator.py` ji už nepoužívá, import se odstraní.

- **IMPORTANT (`FatalRunError` kapitola se automaticky opakuje):**
  Souhlasím ČÁSTEČNĚ - ověřil jsem `begin_chapter()`/`recover_processing()`
  kód přesně a potvrdil mechanismus (kapitola zůstane `processing`,
  příští `run` ji vrátí na `pending`, `queue_for_run()` ji zařadí znovu).
  Nesouhlasím ale s implikovanou závažností "STEJNÉ jako kolo 2/6" -
  `queue_for_run`'s `error`-auto-retry běží TICHO uprostřed jinak
  úspěšně vypadajícího běhu (snadno přehlédnutelné); `FatalRunError`
  vyžaduje, aby uživatel RUČNĚ znovu spustil `run` po VIDITELNÉM selhání
  (tiskne "Fatální chyba běhu", exit 1) - kvalitativně jiná míra
  neviditelnosti. I tak je návrh reálné zlepšení (persistentní záznam,
  `flagged` vyžaduje vědomé `--retry-flagged`, nedbalé opakované "spusť
  to znova" ho tiše nezkusí) - přijímám a implementuji, gated JEN na
  `--translator codex` (Claude-cesta `FatalRunError` - cost guard,
  `LockLostError` - je před-existující chování, mimo rozsah týhle
  plánu).

  **Oprava:** `except FatalRunError as e:` (i uvnitř `except translator.
  InvalidTranslationOutput`'s `codex` větve, co `FatalRunError` sama
  vyhazuje - sesterský except by ji NEZACHYTIL) označí kapitolu
  `flagged` s redigovanou diagnostikou PŘED re-raise. Přidán test dvou
  po sobě jdoucích `run`ů ověřující, že se kapitola bez `--retry-flagged`
  znovu nezařadí.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 10: BLOCKING (moje kolo-9 oprava validovala markery správně, ale
`split_sections()`'s NEZÁVISLÉ substring hledání zůstalo zranitelné -
marker-podobný text uprostřed JSON hodnoty by pořád rozbil parsing;
opraveno přímým slicingem podle ověřených pozic, `split_sections()`
se už nepoužívá). IMPORTANT (FatalRunError nechávalo kapitolu v
processing limbu, další run by ji tiše zařadil znovu - přijato s
výhradou, že závažnost je nižší než kolo 2/6 kvůli nutnosti explicitního
ručního opakování, ale oprava je pořád reálné zlepšení observability).
