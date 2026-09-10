## IMPORTANT

- `main.py:_cmd_polish`, ř. 1779–1835; report kontrakt, ř. 1596–1600: `KeyboardInterrupt` během zpracování aktuální kapitoly nepřidá žádný záznam. `attempted_count = len(report)` ji proto chybně označí jako nezpracovanou, stejně jako problém opravený v kole 29 pro `FatalRunError`. Přidat `outcome="interrupted"` s `stage`, zahrnout jej do `_REPORT_OUTCOMES` a otestovat přerušení během Codexu i následných kontrol.

## NITS

- Ř. 1629 oproti ř. 1051–1053 a 2773–2775: report znovu čte `config.CODEX_MODEL`, přestože próza tvrdí, že normalizovaná lokální hodnota `model` se používá všude. Předat skutečně použitý `model` do `_write_polish_report`; tím bude auditní údaj přímo svázán s během.
- Ř. 2708–2711 a 3423–3425: souhrn kontraktu hlavičky vynechává `run_id`, `generated_at` a `summary`, které implementace zapisuje. Doplnit pro konzistenci.
- Ř. 2700–2702: tvrzení, že zamítnutý/selhaný pokus „nic v DB nemění“, je nepřesné; vzniká `runs` a případně `llm_calls`. Upřesnit na „nemění stav/text kapitoly“.

## VERDICT

CHANGES_NEEDED