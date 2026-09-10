## IMPORTANT

- **Ř. 101–103, 1466–1472, 1546–1558, 1565–1569:** `STYLIST_REPORT_REJECTED_TEXT=False` nezabrání perzistenci citlivého obsahu. `reasons`/`findings` stále obsahují volná pole `issue`, `suggestion`, `actual`, `expected`, `cz_excerpt`, která mohou zopakovat exfiltrovaný text. Navíc se `issue` vždy vypisuje do konzole. Oprava: při opt-outu ukládat a tisknout pouze normalizované kategorie (`source`, `type`, `severity`, `action`, případně `term_id`), bez všech volných textových polí. Přidat test s tajemstvím ve všech těchto polích i v zachyceném stdout.

- **Ř. 1393–1394, 1517–1525, 1722–1730, 2512–2514, 2568, 2589–2590:** opakované tvrzení „`failed` je PŘED kontrolami, žádné findings neexistují“ je nepravdivé. Neočekávaná výjimka může vzniknout v konkordanci, kritikovi nebo meaning-checku po vytvoření části nálezů. Vnější handler je zahodí a uloží pouze chybu. Oprava: buď kontrakt pravdivě definovat jako „failed vždy ukládá jen error bez ohledu na fázi“, nebo uvnitř `_polish_one_chapter` zachovat `stage` a dostupné částečné findings. Přidat test výjimky v každé kontrolní fázi.

- **Ř. 1527–1529, 1573–1574, 1745–1749:** `incomplete = run_status != "ok"` je chybná odvozenina. Dávka, ve které byly zpracovány všechny kapitoly, ale všechny skončily `failed`, dostane `run_status="fatal"` a `incomplete=True`, přestože smyčka doběhla celá. Tím se zkreslí plánované vyhodnocování reportů. Oprava: sledovat samostatný `batch_completed` příznak nebo ukládat `planned_count`/`attempted_count`; `run_status` nesmí suplovat úplnost.

- **Ř. 1559–1560, 1712–1719, 1492–1504, 1788–1796:** garance „jeden report za běh i po FatalRunError/KeyboardInterrupt“ neplatí. Výjimka po `create_run`, ale před prvním appendem, vede kvůli `if not report: return` k žádnému reportu. Fatal chyba při commitování aktuální kapitoly ji navíc nezapíše vůbec, takže je nerozlišitelná od nezpracované kapitoly. Oprava: report vytvořit vždy, když existuje `rid`; přidat top-level `run_error` a záznam aktuálního pokusu/stage. Testovat přerušení před prvním výsledkem a selhání commitu aktuální kapitoly.

- **Ř. 1235–1238 versus 1116–1118 a 2597–2607:** duplicita stejného konkordančního problému byla přijatelná pro bool rozhodnutí, ale není přijatelná pro nový účel „měřit rozpad důvodů“. Jedna regrese může být současně přidána jako nový klíč i syntetický nárůst výskytu, takže agregace důvodů ji započítá dvakrát. Oprava: zavést jednoznačné `reason_code`, důvody deduplikovat, nebo výslovně definovat metriky jako počet kapitol s daným typem, nikoli počet položek `reasons`; přidat regresní test.

- **Ř. 1789–1808:** report se zapisuje před `finish_run`. Pokud finalizace DB selže, report už tvrdí například `run_status="ok"`, zatímco řádek běhu zůstane nedokončený. Oprava: nejprve best-effort provést `finish_run`, zachytit jeho výsledek, potom napsat report s `finalization_error` nebo odpovídajícím stavem.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item.