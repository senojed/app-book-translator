# Round 10 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`usage` volitelné + `or 1` přepisuje validní nulu):**
  Souhlasím, ověřeno přímo v plánu - `_exec_claude()`'s validace
  (Task 2) měla `if usage is not None: ...` (CHYBĚJÍCÍ `usage` tiše
  prošel), a `ClaudeCliClient.complete()` pak `usage.get("input_tokens")
  or 1` - `or` operátor v Pythonu přepíše i validní `0` (falsy) na `1`,
  ne jen `None`/chybějící klíč. Spec i spike potvrzují, že
  `--output-format json` vrací `usage` VŽDY na úspěšné cestě, takže
  "volitelnost" byla zbytečně shovívavá a maskovala by reálný bug v
  CLI/parsování jako tichý fallback místo chyby.

  **Oprava:** `_exec_claude()`'s `usage` validace zpřísněna -
  `isinstance(usage, dict)` je teď POVINNÝ požadavek (ne jen když
  `usage is not None`), stejná síla jako `result`'s validace.
  `ClaudeCliClient.complete()` přenáší `usage["input_tokens"]`/
  `usage["output_tokens"]` PŘÍMO, žádné `or 1`. Přidány 3 testy:
  chybějící `usage` celé, chybějící jedno pole, a zachování validní
  nuly (`input_tokens: 0` se nesmí stát `1`). Spec's "Parsování
  výstupu" sekce aktualizována stejně.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 10: jeden IMPORTANT, potvrzen jako reálný - `or 1` fallback je
klasická past (přepíše i legitimní nulu, ne jen chybějící hodnotu).
Opraveno zpřísněním validace na `_exec_claude()`'s úrovni (fail-fast,
ne tichý fallback) a přímým přenosem hodnot v `complete()`. 3 nové
testy pokrývají všechny tři scénáře (chybí celé pole, chybí jedno
pole, nula se zachová). Desáté kolo, hustota nálezů stále nenulová -
zatím žádné kolo nebylo čisté od obou stran současně.
