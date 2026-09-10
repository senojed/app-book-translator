# Round 27 — Claude critique

Kolo 27 = první review kola-27 post-consensus dodatku (pozorovatelnost
zamítnutí + report soubor). Codex našel 5 IMPORTANT + 1 NIT, všechny
platné. Můj dodatek byl uspěchaný.

## Claude's own findings
Nezávislý průchod: shodné body jako Codex. Navíc drobnost - shadowing
`r` v `_write_polish_report` (loop var vs. genexp), přejmenováno na `rec`.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - report ukládá zamítnutý text = nová PERZISTENCE
  potenciálně exfiltrovaného obsahu, ne "žádná nová expozice":** platí.
  Můj původní argument ("DB už text knihy má") pokulhával - DB NEMÁ
  zamítnutý výstup Codexu, ten se dřív zahodil. Opraveno: (a) přiznáno
  v `_write_polish_report` docstringu i v sekci "Bezpečnostní rozhodnutí
  (kolo 19)" jako doplnění; (b) `config.STYLIST_REPORT_REJECTED_TEXT`
  opt-out (default `True` na přání vlastníka, `False` = report bez
  `styled`); (c) stale próza o dočasnosti výstupu (bezpečnostní detail 1
  + `polish()` tempdir komentář) doplněna o odkaz.
- **IMPORTANT - report vznikal jen po normálním doběhnutí smyčky,
  `FatalRunError`/`KeyboardInterrupt` ho zahodil:** platí a je to
  vážné - právě částečný běh je nejcennější data. `report = []`
  přesunut PŘED `try`, `_write_polish_report` volán z `finally`
  (guarded `rid is not None`), hlavička dostala `run_status` +
  `incomplete`.
- **IMPORTANT - best-effort chytal jen `OSError`, `json.dump` TypeError
  by unikl a shodil běh na fatal:** platí. `except OSError` →
  `except Exception`, `.tmp` cleanup, `tmp=None` guard pro brzké selhání.
- **IMPORTANT - próza tvrdila "u failed plné nálezy", kód ukládá jen
  error:** platí, `failed` je PŘED kontrolami. Kontrakt sjednocen
  všude (`_write_polish_report` docstring, "Mimo rozsah", Rozhodnutí
  sekce, chybová tabulka, test bullety): `rejected` = reasons/findings/
  styled; `failed` = jen error.
- **IMPORTANT - report bez `CODEX_MODEL`/schema/timestamp, nejde
  porovnat reject rate mezi konfiguracemi:** platí (Codex volání není
  v `llm_calls`, model se z reportu jinak nezjistí). Doplněno
  `schema_version`, `codex_model`, `generated_at`, `run_status`.
- **NIT - "viz Mimo rozsah" odkaz nepřesný:** opraveno na "bod
  Granulární přijetí / opravná smyčka v sekci Rozhodnutí z kol 1-26".

## Claude VERDICT

`CHANGES_NEEDED` - 5 platných IMPORTANT ve vlastním dodatku, vše
aplikováno. Čeká se na re-review (kolo 28).

## Summary for log

Kolo 27: první review kola-27 dodatku. Codex 5 IMPORTANT + 1 NIT, vše
platné a aplikované: (1) report ukládá zamítnutý text = nová perzistence
exfiltrovatelného obsahu (přiznáno, `STYLIST_REPORT_REJECTED_TEXT`
opt-out, stale próza opravena); (2) report se zahazoval při
`FatalRunError` (přesun do `finally` + `run_status`/`incomplete`);
(3) best-effort chytal jen `OSError` (→ `except Exception` + `.tmp`
cleanup); (4) próza "u failed plné nálezy" nepravdivá (kontrakt
sjednocen: failed = jen error); (5) report bez `codex_model`/schema
(doplněno). Čeká se na kolo 28.
