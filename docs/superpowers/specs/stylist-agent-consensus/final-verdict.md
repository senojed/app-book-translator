# Final verdict: CONSENSUS

Dosaženo v **kole 26** (bezpečnostní strop byl 30).

Codex i Claude vydali `CONSENSUS` ve stejném kole - oba nezávisle
neshledali žádný BLOCKING ani IMPORTANT bod.

## Průběh konvergence

| Kola | BLOCKING (Codex) | IMPORTANT/NITS |
|---|---|---|
| 1 | 3 | 9 |
| 2-8 | klesalo | opravy validace, backupu, lifecycle |
| 9-16 | občasné 1-2 | číselný guard, sqlite backup, exception handling |
| 17-19 | 1 BLOCKING (bezpečnost) | opt-in `STYLIST_ACCEPT_FS_RISK` |
| 20-25 | 0 | úzké IMPORTANT navazující na předchozí kola |
| 26 | 0 | 3 prozaické NITS |

## Klíčová rozhodnutí (detaily ve spec sekci "Rozhodnutí z kol 1-26")

- **Bezpečnost:** `codex exec --sandbox read-only` má OVĚŘENĚ neomezené
  ČTENÍ celého disku (živý canary test, kolo 18). Prompt injection z
  textu knihy může exfiltrovat citlivý soubor. Řešení (rozhodnutí
  vlastníka projektu, kolo 19): povinný opt-in `config.STYLIST_ACCEPT_
  FS_RISK = True` (default `False`), vynucený PŘÍMO v `stylist.polish()`.
  Migrační cesta na neagentní API nebo OS/kontejnerový sandbox je
  zdokumentovaná, mimo rozsah tohohle plánu.
- **`--ignore-user-config`** zůstává (hang fix, kolo 17);
  **`--ignore-rules`** vědomě NEPOUŽITO (kolo 25 - rozšiřovalo by
  útočnou plochu).
- **Kontrola výstupu:** 3 nezávislé sítě - strukturální (zdarma),
  kritik (EN vs. CZ-po), meaning/rejstřík check (CZ-před vs. CZ-po).
  `_polish_rejected` srovnává PROTI PŮVODNÍMU stavu, ne absolutně.
- **Záloha:** `_cmd_polish` zálohuje CELOU DB přes `sqlite3.Connection.
  backup()` (ne `shutil.copy2`), nejvýš jednou za běh, těsně před prvním
  přijatým zápisem. Obnova = dokumentovaný ruční postup (disaster
  recovery), ne automatizovaný CLI příkaz.

Plán je připraven k převedení na implementační plán (writing-plans).
