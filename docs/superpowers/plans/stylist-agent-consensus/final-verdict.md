# Final verdict: CONSENSUS

Dosaženo v **kole 10** (strop byl 15).

Codex i Claude vydali `CONSENSUS` ve stejném kole - oba nezávisle
neshledali žádný BLOCKING ani IMPORTANT bod.

## Průběh konvergence

| Kolo | Codex | Claude | Hlavní téma |
|---|---|---|---|
| 1 | 3 BLOCKING, 7 IMPORTANT | 1 vlastní BLOCKING | 3 spec-verbatim testy porušují délkový guard; `_print_usage` raw print; ~15 chybějících testů |
| 2 | 4 IMPORTANT | 0 | sirotčí codex proces při Ctrl+C; provenience test; timing zálohy; Task 13 bezpečně |
| 3 | 1 BLOCKING, 2 IMPORTANT | 0 | kolo-1 stdin fix rozbil CRLF; KI test přepsán; Task 13 `shutil.copy2` → `_snapshot_db` |
| 4 | 3 IMPORTANT | 0 | append invariant (KI okno); redakční matice; Task 13 důkazy |
| 5 | 2 IMPORTANT, 2 NITS | 0 | append fix měl vlastní KI mezeru → `finally`; canary runner timeout |
| 6 | 1 IMPORTANT | 0 | `counts` v `else` nezapočítal `failed` z výjimky → souhrn z `report` |
| 7 | 1 IMPORTANT, 3 NITS | 0 | redakce ve skutečné `_run_critic` (pojistný test); canary `BaseException` |
| 8 | 1 IMPORTANT, 1 NIT | 0 | canary nevyhodnotitelný (token do proměnné); Task 8 integrace assert předpokladů |
| 9 | 1 IMPORTANT | 0 | `guide_block` předání netestované → +test Task 5/12 |
| 10 | 1 NIT | 0 | komentářová záměna čísla řádku. **CONSENSUS** |

## Charakter změn

Plán vznikl z už zkonsensovaného specu (38 kol), takže **žádná designová
díra** - všechny nálezy byly:
1. **Latentní chyby ve spec-verbatim testech** (délkový poměr > 1.5×,
   cp1252 stdin, CRLF) - plán je nahradil opravenými verzemi, produkční
   kód beze změny.
2. **Chybějící testy** klíčových cest (redakce ve všech větvích,
   `guide_block`, provenience slepé skvrny, all-failed z generické
   výjimky, KI okna) - doplněno ~25 inline testů.
3. **Malé odchylky od spec-verbatim** kde spec sám měl úzké okno:
   - `polish()` `except BaseException` - kill sirotčího codex procesu při Ctrl+C
   - `_cmd_polish` smyčka: jeden `try/except/finally`, append ve `finally`,
     `rec` dopočet z DB - uzavře KI okno mezi tělem iterace a appendem
   - souhrn/all-failed podmínka z `report`, ne z `counts` slovníku
   - Task 13: kopie DB přes `_snapshot_db`, config jen runtime atributy
     (bez editace `config.py`), canary test první + s vyhodnotitelným tokenem

Každá odchylka je v plánu explicitně označená a zdůvodněná.

## Stav

Plán je připraven k provedení (`superpowers:subagent-driven-development`
nebo `superpowers:executing-plans`).
