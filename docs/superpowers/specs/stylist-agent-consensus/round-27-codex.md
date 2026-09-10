## IMPORTANT

- `1477–1516`, `1493–1497`, `3192–3194`: Report ukládá zamítnutý Codex výstup, který může obsahovat data exfiltrovaná prompt injectionem. Tvrzení „žádná nová třída expozice“ a „nezasahuje do bezpečnostního jádra“ je nepravdivé: dříve byl zamítnutý obsah odstraněn, nyní trvale zůstane v samostatném JSON. Navíc `405–407` a `2558–2562` stále tvrdí, že stylizovaný výstup existuje jen dočasně. Oprava: explicitně revidovat bezpečnostní rozhodnutí, popsat perzistenci/retenci a přístupová práva reportů; opravit stale prózu. Zvážit samostatný opt-in pro ukládání plného textu.

- `1632–1656`, `1670–1721`: Report vznikne jen po normálním dokončení celé smyčky. `FatalRunError`, `KeyboardInterrupt` nebo jiná top-level chyba zahodí již nashromážděné záznamy, včetně předchozích zamítnutých textů. To odporuje „plnému auditu každého pokusu“ a „jeden soubor za běh“. Oprava: inicializovat report před `try`, zapisovat jej jednou ve `finally` pro každý vytvořený `rid` a zahrnout `run_status`/příznak neúplnosti. Přidat test částečné dávky ukončené `FatalRunError`.

- `1507–1516`: Deklarované best-effort chování není zajištěno. Zachytává se pouze `OSError`; například `TypeError` při serializaci neočekávané hodnoty ve findings unikne do `_cmd_polish`, změní běh na fatal a návratový kód na 1. Selhání před `try` rovněž není pokryto. Oprava: obalit celé sestavení a zapsání reportu vhodným `except Exception`, uklidit případný `.tmp` a otestovat chybu `json.dump`, nejen `makedirs/open`.

- `1481–1483`, `2476–2482`, `3183–3185` versus `1375–1378`, `1647–1649`, `2419–2420`: Próza tvrdí, že `failed` obsahuje „plný seznam nálezů“, ale kód i test ukládají pouze `error`. U selhání před kontrolami žádné findings ani neexistují. Oprava: změnit kontrakt konzistentně na „rejected: reasons/findings/styled; failed: error“, případně definovat a implementovat částečné findings pro pozdější selhání.

- `1480–1506`, `2483–2497`: Report určený k měření úspěšnosti neobsahuje `CODEX_MODEL`, ačkoli Codex volání není v `llm_calls` a dokument jinde model výslovně požaduje kvůli auditu. Reject rate tak nelze spolehlivě porovnat mezi konfiguracemi. Oprava: uložit alespoň `schema_version`, normalizovaný `codex_model`, čas a hash vstupního CZ textu; přidat přesný test schématu.

## NITS

- `3187`: Odkaz „viz Mimo rozsah“ je nepřesný; úplné zdůvodnění odkladu opravné smyčky je v `2488–2500`, zatímco úvodní „Mimo rozsah“ popisuje hlavně zákaz retry. Odkázat přímo na rozhodovací sekci.

## VERDICT

CHANGES_NEEDED