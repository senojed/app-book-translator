## IMPORTANT

- `_cmd_polish`, `except KeyboardInterrupt`: stav commitu se určuje jen přes `_already_styled(...)`. Při `--force` má kapitola marker už před aktuálním pokusem, takže přerušení před novým commitem bude chybně vykázáno jako `polished`. Oprava: detekovat změnu `translated_text` proti vstupnímu `c`, nebo zapisovat marker s aktuálním `run_id`. Přidat test `--force` nad dříve stylizovanou kapitolou, přerušení před i po novém commitu.

- `_polish_one_chapter` po `state.commit_chapter_result`: `print("...vylepšeno.")` může po úspěšném commitu vyhodit výjimku. Obecný handler ji označí jako `failed`; u jediné kapitoly bude celý běh dokonce `fatal`, přestože DB obsahuje přijatou stylizaci. Kolo 34 odstranilo duplicitní záznam, ale nezajistilo pravdivý výsledek. Oprava: po commitu nesmí diagnostický výpis změnit outcome; použít best-effort výpis nebo klasifikovat podle skutečného stavu DB. Test musí ověřit `outcome == "polished"` a `run_status == "ok"`, ne pouze jeden záznam.

- `_cmd_polish`, `except FatalRunError`: kapitola ukládá redigované `stylist._redact_detail(str(fe))`, ale vnější handler následně stejnou výjimku uloží nezměněnou do `run_error` a vytiskne přes `print(e)`. To obchází `STYLIST_REPORT_REJECTED_TEXT=False`. Komentář u in-loop handleru výslovně připouští Codexem odvozený obsah, zatímco komentář v `config.py` chybně tvrdí, že `run_error` Codexův obsah nenese. Oprava: redigovat také top-level `run_error` a konzolový výpis, případně oddělit bezpečný typ/stage od detailu dostupného jen za opt-inem. Přidat regresní test s `FatalRunError("SECRET123")`.

## NITS

- Testovací popis `STYLIST_REPORT_REJECTED_TEXT=False + secret na Codex STDERR` stále očekává text „stderr Codexu potlačen“, ale `_redact_detail` nyní vrací obecné „hodnoty potlačeny…“. Sjednotit prózu s aktuální hodnotou `_REDACTED`.

## VERDICT

CHANGES_NEEDED