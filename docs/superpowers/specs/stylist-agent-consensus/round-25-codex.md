## IMPORTANT

- `stylist.py` `_CODEX_STATIC_FLAGS` a komentáře (ř. 615–624), manuální checklist (ř. 2094–2099), rozhodnutí kola 23 (ř. 2991–2995): zdůvodnění `--ignore-rules` je obrácené. Flag nenastavuje „nejrestriktivnější execpolicy“; odstraní i případná uživatelská pravidla `forbidden`/`prompt`, která mohou útok omezovat. Tvrzení „stylista nespouští shell příkazy“ navíc odporuje vlastnímu canary testu, kde Codex spustil `Get-Content`. Opt-in sice přiznává plný FS risk, ale není důvod rušit dodatečné restrikce. Odstranit `--ignore-rules` z argv a testů, nebo výslovně zdokumentovat, že jde o determinismus za cenu ignorování restriktivních pravidel—not bezpečnostní hardening.

## NITS

- Nadpis docstringu `Bezpečnostní detaily (kola 1-6 a 17-20)` (ř. 393) je po přidání `--ignore-rules` v kole 23 zastaralý.
- Rozhodnutí na ř. 2985 tvrdí, že `test_polish_config_invariants` testuje timeout; timeout ve skutečnosti ověřuje samostatný `test_polish_uses_config_timeout_and_strips_model`.

## VERDICT

CHANGES_NEEDED