# Round 34 — Claude critique

Osmé review kola-27 dodatku. Codex 3 IMPORTANT + 1 NIT - tentokrát
STRUKTURNÍ přepis, ne dolaďování.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - redakční hranice pořád netěsnila:** i počet odstavců /
  poměr délky nesou hodnoty odvozené ze `styled`, a obecný `except` v
  `_cmd_polish` ukládal libovolné `str(e)` do `failed.error`. → JEDEN
  helper `stylist._redact_detail(detail)` - vrací `detail` jen za
  `STYLIST_REPORT_REJECTED_TEXT is True`, jinak generickou `_REDACTED`
  náhradu. Aplikováno na VŠECHNY Codexem-odvozené hodnoty v chybových
  hláškách (stderr, čísla, odstavce, ratio, `str(e)`).
- **IMPORTANT + IMPORTANT - invariant "1 záznam / kapitolu" byl křehký:**
  držel jen dedupem podle `idx` a padal na (a) výjimce z `print()` po
  commitu (`BrokenPipeError` → `_polish_one_chapter` už přidalo
  `polished`, vnější `except` přidá druhý `failed`), (b) commit-then-
  interrupt okně. Codex navrhl správnou strukturu: **`_polish_one_
  chapter` report NEMUTUJE, vrací jeden `dict`; `_cmd_polish` appendne
  přesně jednou za iteraci smyčky (invariant STRUKTURNÍ, žádný dedup).**
  Přepsáno. `KeyboardInterrupt` handler navíc zjistí STAV DB (marker
  `_already_styled`) a zapíše `polished`/`interrupted` podle skutečnosti,
  ne podle toho, kam dorazil kód. `fatal` `stage` zrušen (hláška
  `str(fe)` rozliší commit vs cost guard).

### NITS - fixed
- `generated_at` bez časového pásma, filename jen sekundová přesnost →
  timezone-aware ISO 8601 (`import datetime as _dt` do `main.py`),
  filename + `os.urandom(4).hex()` suffix.

## Claude VERDICT

`CHANGES_NEEDED` - 3 IMPORTANT. Aplikováno. Tohle je významnější změna
než minulá kola - report-append cesta je teď strukturně správná, ne
hlídaná. Měla by to být poslední velká iterace toho subsystému. Čeká se
na kolo 35.

## Summary for log

Kolo 34: 3 IMPORTANT + 1 NIT - STRUKTURNÍ přepis. (1) redakce
Codexem-odvozených hodnot v chybových hláškách přes jeden helper
`_redact_detail` (i odstavce/ratio/`str(e)`, ne jen stderr/čísla).
(2)+(3) `_polish_one_chapter` už `report` NEMUTUJE, vrací `dict`;
`_cmd_polish` appendne přesně jednou za iteraci (invariant STRUKTURNÍ);
`KeyboardInterrupt` handler zjistí stav DB. NIT: `generated_at`
timezone-aware, filename random suffix. Čeká se na kolo 35.
