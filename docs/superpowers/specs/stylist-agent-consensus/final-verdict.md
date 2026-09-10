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

---

## Dodatek (kola 27-38, druhá konsensuální smyčka)

Vlastník projektu po konsensu (kolo 26) přidal 2 požadavky a nechal na
dodatek proběhnout DALŠÍCH 12 review kol (27-38):

1. **Pozorovatelnost zamítnutí** - report soubor
   (`polish-reports/run-<rid>-<čas>-<hex>.json`) jako měřicí přístroj
   pro v1: per kapitola `outcome`, u `rejected` `reason_types` (vždy) +
   plný detail (`reasons`/`findings`/`styled`) jen za samostatným
   opt-inem `config.STYLIST_REPORT_REJECTED_TEXT is True` (default
   `False`).
2. **Granulární opravná smyčka** - zvážena, ODLOŽENA za v1. v1 =
   all-or-nothing + report jako měřicí přístroj; podle naměřeného reject
   rate se rozhodne dál.

Dodatek se ukázal jako netriviální subsystém (ne "aditivní próza") -
12 review kol vygenerovalo mj.:
- **Bezpečnost:** report u `rejected` PERZISTENTNĚ ukládá zamítnutý text
  od Codexu + volná pole nálezů - potenciálně exfiltrovaný obsah, navíc
  do synchronizované složky. Rozhodnutí (kolo 31): NENÍ pokryté přijetím
  `STYLIST_ACCEPT_FS_RISK`, proto SAMOSTATNÝ explicitní opt-in
  `STYLIST_REPORT_REJECTED_TEXT` (default `False`). Za `False` jdou
  VŠECHNY Codexem-odvozené hodnoty v chybových hláškách (stderr, čísla,
  odstavce, ratio, `str(e)`, `FatalRunError` z LLM klienta) přes
  `stylist._redact_detail` - redakce U ZDROJE.
- **Robustnost:** `_polish_one_chapter` vrací `dict`, `report` nemutuje -
  invariant "1 report záznam / iteraci smyčky" je STRUKTURNÍ. VŠECHNY
  diagnostické výpisy přes `_say()` (`try/print/except pass`) - výpis
  nemůže shodit ani přebít výsledek běhu. `KeyboardInterrupt` handler
  určí outcome podle stavu DB (`translated_text`), ne podle toho kam
  dorazil kód. Report z `finally` vždy když existuje `rid`, AŽ PO
  `finish_run`, s `run_status`/`batch_completed`/`planned_count`/
  `attempted_count`/`run_error`/`finalization_error`.

**Kolo 38: Codex i Claude CONSENSUS ve stejném kole.** Dodatek hotový.

Plán (jádro i dodatek) je připraven k převedení na implementační plán
(writing-plans).
