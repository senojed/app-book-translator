## IMPORTANT

- `main.py:1860–1866, 1920–1926` — `FatalRunError` z kritika se bez redakce zapisuje do `fatal.error`, `run_error` i konzole. Tvrzení, že zpráva z kritika/cost guardu nemůže nést Codexem odvozený obsah, není garantované: `_run_critic` přehazuje obecný `FatalRunError` z klienta poté, co klient obdržel `styled`. Oprava: v in-loop handleru použít `_redact_detail(str(fe))`, zapsat redigovanou hodnotu a znovu vyhodit sanitizovaný `FatalRunError`. Přidat test s `pipeline._run_critic -> FatalRunError("SECRET123")` pro oba režimy konfigurace.

## NITS

- Prose-vs-code nesoulad po kole 35:
  - `1086–1088` tvrdí, že `KeyboardInterrupt` vždy přidá `interrupted`; po commitu může správně přidat `polished`.
  - `2729–2732` stále používá absenci markeru jako důkaz neprovedeného commitu.
  - `2853` stále popisuje detekci přes `_already_styled(...["notes"])`; kód používá porovnání `translated_text`.
- `1667` uvádí název `run-<rid>-<timestamp>.json`, ale kód používá také osmimístný náhodný suffix.
- `378` označuje komentář jako „Kolo 27-35“, přestože byl měněn i v kole 36.

## VERDICT

CHANGES_NEEDED