## IMPORTANT

- `Testování`, ř. 2157–2167: Test ověřuje pouze `pages=100`, nikoli funkčnost časového limitu. Regrese odstranící `progress=_check_deadline` nebo samotné vyhození `TimeoutError` by prošla a obnovila neomezené čekání řešené v kole 15. Přidat test s proxy `backup()`, která zavolá předaný callback, a řízeným `time.monotonic()`, který překročí deadline; očekávat `TimeoutError`.

## NITS

- `_codex_argv` docstring, ř. 626–629, a rozhodnutí kola 19, ř. 2886–2890: Tvrdí, že `test_polish_invokes_codex_with_expected_argv` volá nebo používá `_codex_argv`. Od kola 20 test záměrně používá ručně zapsaný oracle a helper nevolá. Upravit obě formulace; jde o stale prose.
- `Mimo rozsah`, ř. 37–40: „jedna přepisovaná záloha na běh“ je nepřesné. Běh bez přijaté změny zálohu nepromuje ani nepřepisuje. Použít „nejvýše jedna záloha za běh, pouze před prvním přijatým zápisem“.

## VERDICT

CHANGES_NEEDED