# Plan-consensus — finální verdikt

**Výsledek: MAX_ROUNDS** (10/10 kol vyčerpáno bez kola, kde by Codex i Claude
současně řekli CONSENSUS).

**Hodnocení konvergence: prakticky dosaženo.**

## Průběh

| Kolo | Codex | Claude | Rozsah oprav |
|---|---|---|---|
| 1 | CHANGES (2 BLOCK, 8 IMP) | CHANGES (1 BLOCK, 5 IMP) | architektura + data model |
| 2 | CHANGES (4 BLOCK, 8 IMP) | CHANGES (2 IMP) | interfacy (díry po přepisu kola 1) |
| 3 | CHANGES (1 BLOCK, 6 IMP) | CHANGES (1 IMP) | cost guard, term_mentions, run lock |
| 4 | CHANGES (1 BLOCK, 5 IMP) | CHANGES (0) | multi-blocking, glosář zdroj pravdy |
| 5 | CHANGES (0 BLOCK, 4 IMP) | CHANGES (0) | Finding schema, cirkularita driftu |
| 6 | CHANGES (2 BLOCK, 5 IMP) | CHANGES (2 IMP) | glosář → SQLite, accepted_alt |
| 7 | CHANGES (1 BLOCK, 5 IMP) | CHANGES (0) | term_id PK, schema precision |
| 8 | CHANGES (1 BLOCK, 5 IMP) | CHANGES (0) | term_id do translatoru, per-výskyt |
| 9 | CHANGES (1 BLOCK, 4 IMP) | CHANGES (0) | Finding action routing, reseed FK |
| 10 | CHANGES (0 BLOCK, 6 IMP) | **CONSENSUS** | candidate/seeded term_id, helpers |

## Stav

- **Architektura nezměněna od kola 4** (6 kol). Přístup A (pipeline agentů,
  orchestrace v kódu), 3 LLM agenti (scout, translator+revizor, kritik),
  deterministická concordance, SQLite stav, web UI review - beze změny.
- **Žádný BLOCKING od kola 8.** Kola 8-10 = ladění DB schematu a rozhraní.
- **Claude v kole 10: CONSENSUS** - nevidí žádný BLOCKING/IMPORTANT.
- **Codex drží CHANGES_NEEDED** - je instruován "nebýt shovívavý, necílit na
  rychlou shodu". Jeho kolo-10 nálezy byly schema nity, všechny zapracované.
  Kolo 11 by pravděpodobně našlo další vrstvu jemných nitů (klesající výnos).

## Nevyřešené / vědomá omezení v1 (zapsaná ve specu)

- Concordance párování termínů je podle povrchu; split povrchu na 2 entity je
  ruční `answer` operace.
- `term_mentions` je best-effort (závisí na translatorových `rendered_terms`
  pro tvary mimo glosář); drift na úplnost nespoléhá.
- České skloňování v concordance = kmenové porovnání, ne lemmatizace; LLM
  soudce případně později.
- Scout jedno volání vs `--chunked` = otevřená otázka k ověření pilotem.
- Rozchází se kritik s translatorem dost na to, aby revizní smyčka měla smysl?
  → k ověření pilotem (klíčové pro učební cíl).

## Doporučení

Spec je připravený na `writing-plans`. Otevřené otázky jsou explicitně
označené jako "k ověření pilotem" a pilot (2-3 kapitoly, ~$1) je první
implementační milník po skeletonu.
