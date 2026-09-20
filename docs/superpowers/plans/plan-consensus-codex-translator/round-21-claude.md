# Round 21 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (checkpoint obaluje jen `revise_chapter()`, ne
  následující `_run_critic()`):** Souhlasím a ověřil jsem přesně -
  po úspěšném `cz = res.translation` (uvnitř kola-13's `try`) smyčka
  PŘED mým fixem pokračovala MIMO try/except: kumulace `new_terms`,
  `questions`, `rendered`, `concordance.check_chapter()`, a HLAVNĚ
  `_run_critic(en, cz, client_factory("critic"))` - VŽDY Claude, i
  při `--translator codex`. `_run_critic()` má VLASTNÍ `except
  FatalRunError: raise` - kritikovo `FatalRunError` (cost guard, auth)
  by tak propagovalo z CELÉ `process_chapter()` funkce, ÚPLNĚ MIMO
  checkpoint, co jsem přidal kolo 13 - ten chrání jen selhání
  `revise_chapter()` SAMOTNÉHO, ne selhání NÁSLEDUJÍCÍHO kroku VE
  STEJNÉ iteraci. Scénář: Codex úspěšně (a zaplaceně) dokončí revizi,
  kritik HNED PO NÍ selže - nové `cz` se NIKDY nedostane k commitu,
  příští `run` přeloží celou kapitolu znovu od nuly.

  **Oprava:** Přesunuto `cz = res.translation` a CELÝ zbytek
  smyčkového těla (kumulace metadat, `_run_critic()` recheck) DOVNITŘ
  `try` bloku - `rounds += 1` zůstává JEDINÉ, co se provede AŽ PO
  úspěšném dokončení CELÉ iterace. Přidán přesně požadovaný regresní
  test (první kritik vyžádá revizi, revize uspěje, druhý kritik vyhodí
  `FatalRunError`, ověřeno zachování POSLEDNÍHO, revidovaného `cz`).

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 21: jeden IMPORTANT bod, přesný a dobře odůvodněný - kolo-13's
checkpoint chránil jen `revise_chapter()`'s VLASTNÍ selhání, ne selhání
následujícího `_run_critic()` volání VE STEJNÉ iteraci (kritik je VŽDY
Claude, i při --translator codex, takže jeho FatalRunError obchází
Codex-specifickou ochranu úplně). Opraveno rozšířením try/except na
CELOU iteraci revizní smyčky. Tohle je čtvrtý "kolo N objevilo mezeru
v kole M's fixu" případ v řadě pro revizní-smyčku checkpoint (kolo 9
timeout, kolo 13 commit chybí, kolo 18 mentions, kolo 20 questions,
teď kolo 21 scope) - konzistentní vzor postupného zpřesňování jedné
oblasti kódu.
