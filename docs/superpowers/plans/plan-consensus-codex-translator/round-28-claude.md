# Round 28 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné)

### NITS
(žádné vlastní nové nad rámec Codexova bodu - provedl jsem nezávislý
průchod plánu, kontrolu Task 2's "Ověř úspěch" kroků proti VŠEM nově
přidaným testům z kol 22-27 (finální krok na řádku 1941 spouští CELÉ
soubory bez `-k` filtru, takže je automaticky pokryje), a kontrolu
Task 6's smoke testu proti `process_chapter()`'s návratovému tvaru po
kole 27's změně - beze změny, nic dalšího nenalezeno)

## On Codex's points

### Agreed + fixed

- **NIT (`_polish_preflight()`'s ořezaný `model` vs. neořezaný
  `config.CODEX_MODEL` pro cenu):** Souhlasím a ověřil jsem přesně -
  `_polish_preflight()` (main.py:1158, PRE-EXISTING, nemodifikovaná
  tímhle plánem) vrací `(config.CODEX_MODEL or "").strip()`. `_client_
  factory`'s lazy `factory()` (Task 4) tenhle OŘEZANÝ `model` posílal
  přímo do `CodexLLMClient(codex_cmd, model)` - stal by se `billed_
  model`. Task 1's `PRICE_IN_PER_MTOK[CODEX_MODEL] = 0.0` ALE používá
  RAW (neořezaný) `config.CODEX_MODEL` jako klíč. `CODEX_MODEL =
  "gpt-5.6-terra"` dnes nemá okolní whitespace, takže NENÍ aktivně
  chybové - ale kdyby NĚKDY mělo, `PRICE_IN_PER_MTOK[ořezaná_verze]`
  lookup (`_price()`, kolo 16) by minul i přes SPRÁVNĚ nastavenou cenu
  a vyhodil `MissingPriceError`.

  **Oprava:** `factory()` teď staví `CodexLLMClient(codex_cmd, config.
  CODEX_MODEL)` - RAW hodnota, stejná jako Task 1's dict klíč.
  `_polish_preflight()`'s vrácený `model` element se v `factory()`
  zahazuje (`_`) - použije se JEN pro vlastní prázdný-string check
  uvnitř `_polish_preflight()` samotné. Aktualizován existující test
  `test_client_factory_translator_backend_codex_uses_codex_client` -
  mock `_polish_preflight()`'s model element teď je záměrně ignorovaný
  (`"ignored"`), test ověřuje `client._inner.billed_model` proti
  novému `monkeypatch.setattr(config, "CODEX_MODEL", "m")` mocku
  místo toho.

## Claude VERDICT
CONSENSUS

## Summary for log
Kolo 28: jediný nález byl Codexův NIT (ořezaný vs. neořezaný CODEX_MODEL
pro cenový lookup - latentní, dnes nereachovatelný, protože CODEX_MODEL
nemá whitespace, ale defenzivně správné to opravit). Opraveno použitím
RAW `config.CODEX_MODEL` konzistentně napříč Task 1's price-table klíčem
a Task 4's `CodexLLMClient` konstrukcí. Vlastní nezávislý průchod
nenašel žádný nový BLOCKING/IMPORTANT bod. OBĚ strany (Codex i Claude)
CONSENSUS ve stejném kole - plán je hotový k exekuci.
