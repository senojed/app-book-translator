# Round 24 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`except Exception`/`except FatalRunError` nechytí
  `KeyboardInterrupt`):** Souhlasím - ověřil jsem přímo v Pythonu
  (`KeyboardInterrupt.__mro__`), je to `BaseException` podtřída, NE
  `Exception`. Všechny TŘI checkpoint-except místa v `process_chapter()`
  (scénová smyčka kolo 23, pre-loop kritik kolo 22, revizní smyčka
  kolo 13/18/20/21/22) by tedy Ctrl+C BĚHEM `translate_scene()`/
  `revise_chapter()`/kritika přeskočily úplně - žádný checkpoint, žádná
  obnova starých otázek, ztráta `cz` stejná jako kdyby žádný z
  předchozích 6 kol fixů nikdy nebyl. Tohle NENÍ exotický edge case -
  Ctrl+C během dlouho běžícího `run`u je běžná uživatelská akce.

  **Oprava:** Rozšířil jsem všechny tři `except` klauzule na `except
  (Exception, KeyboardInterrupt)`/`except (FatalRunError,
  KeyboardInterrupt) as e:`. Zvažoval jsem `except BaseException` (širší,
  jednodušší), ale zvolil explicitní tuple s `KeyboardInterrupt` -
  přesnější dokumentace ÚMYSLU (chytáme konkrétně tenhle jeden extra
  případ, ne "cokoliv včetně `SystemExit`/`GeneratorExit`"), a shoduje
  se s tím, jak `except FatalRunError` už dnes explicitně pojmenovává
  typ. Chování po checkpointu beze změny - `raise` dál propaguje, `run`
  se pořád ZASTAVÍ (main.py žádnou z těchhle výjimek nezachytí ani
  neschovává), jen DB stav teď odpovídá poslednímu bezpečně uloženému
  kroku. Přidány dva regresní testy (scénová smyčka +
  `test_scene_loop_keyboard_interrupt_restores_existing_open_question`,
  revizní smyčka + `test_revision_keyboard_interrupt_preserves_
  translation`) - pokrývají obě strukturálně odlišné checkpoint cesty
  (otázky-only vs. `cz`+mentions+otázky).

### Agreed but already addressed (NIT)

- **NIT (Task 5's komentář "scénová smyčka NENÍ obalená" je zastaralý
  po kolo-23's fixu):** Souhlasím - přeformuloval jsem komentář v
  `main.py`'s `InvalidTranslationOutput` except větvi (Task 5), aby
  přesně rozlišoval DVĚ různé vrstvy ochrany: kolo-23's `try/except`
  kolem scénové smyčky řeší JEN obnovu starých otázek (žádný `cz`
  checkpoint, protože žádný `cz` tam ještě neexistuje), zatímco
  formát-drift/status handling (kolo 6, tenhle komentář) zůstává beze
  změny - `InvalidTranslationOutput` ze scénové smyčky se pořád stává
  `flagged`/`error` přes main.py, ne graceful continue.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 24: jeden IMPORTANT bod (přesný, ověřený - `KeyboardInterrupt` je
`BaseException`, ne `Exception`, takže by Ctrl+C obešel VŠECHNY tři
checkpoint-except místa přidané kola 13-23) + jeden NIT (zastaralý
komentář po kolo-23's fixu). Opraveno rozšířením `except` klauzulí na
`(Exception, KeyboardInterrupt)`/`(FatalRunError, KeyboardInterrupt)`
ve všech třech místech, přidány dva regresní testy. Šesté kolo v řadě
v checkpoint/data-loss oblasti - tentokrát ne nová FÁZE bez ochrany,
ale nová TŘÍDA výjimky, co obchází ochranu už existující.
