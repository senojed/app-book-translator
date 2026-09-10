## BLOCKING

- `stylist.polish`, volání `subprocess.run(..., text=True)` — bez explicitního `encoding` používá Windows lokální kódování; na cílovém stroji je `cp1252`, které nezakóduje český prompt. Volání skončí `UnicodeEncodeError` ještě před spuštěním Codexu. Nastavit `encoding="utf-8"` a přidat test se znaky `č`, `ř`, em dash a jiným Unicode.
- `_polish_one_chapter`, `rendered_terms=[]` — odmítnutý kompromis kolem `term_mentions` není pouze ztráta provenience. `examined_terms()` zahrne termín jen při přesné EN shodě nebo přes `rendered_terms`; u termínu zachyceného pouze hlášením translatoru jej baseline, následná konkordance i nové mentions úplně ztratí. Tím lze nepozorovaně změnit závazný termín a následné `answer` kapitolu nerequeueuje. Načíst existující mentions kapitoly, ověřit jejich `cz_form` ve stylizovaném textu a použít je jako vstup pro obě kontroly i obnovu mentions. Potřebný getter je malá oprava, nikoli nová infrastruktura.

## IMPORTANT

- `critic.review()` — validace stále selhává otevřeně: chybějící/neplatný `verdict`, `verdict="pass"` s nedict položkami nebo neplatnými poli může skončit prázdným seznamem a přijetím stylizace. Docstring přitom tvrdí, že rozbitý výstup vede k retry a výjimce. Validovat celý kontrakt: top-level dict, verdict enum, seznam dictů a enumy povinných polí; jakákoli odchylka musí retryovat a následně selhat.
- Rozhodnutí „bez deterministické kontroly čísel/dat“ — zdůvodnění zaměňuje jednoduchou bezpečnostní kontrolu za kompletní NLP extraktor. Přesný multiset arabských čísel, desetinných hodnot, procent, měn a explicitních dat lze porovnat levně a spolehlivě; zachytí například `12` → `21`, které mohou oba LLM kontroloři přehlédnout. Přidat alespoň tento úzký guard a složitější slovní číslovky ponechat mimo rozsah.
- `subprocess.run(..., timeout=180)` na Windows — `codex.cmd` spouští potomka `node`; timeout ukončuje pouze obalový proces, ne garantovaně celý strom. Codex může pokračovat a spotřebovávat kvótu. Použít procesní skupinu/Job Object a při timeoutu ukončit celý strom; přidat Windows test s potomkem.
- `_cmd_polish`, větev „všechny kapitoly selhaly“ — návratový kód je `1`, ale run je před návratem označen `"ok"`. Zdůvodnění „mechanismus doběhl“ odporuje vlastní klasifikaci jako systémového symptomu a DB audit bude hlásit úspěch. Nastavit stav `"fatal"` nebo zavést jednoznačný `"failed"`.

## NITS

- Poznámky u `-o` a sekce Rozhodnutí stále dvakrát tvrdí, že vstup jde přes soubor, zatímco implementace používá stdin.
- Guardrail sekce stále popisuje baseline z uložených `notes`; implementace ji správně přepočítává čerstvě.
- Testovací scénář popisuje klíč `(type, term_id)`, ale implementace používá `(type, term_id, actual)`.

## VERDICT

CHANGES_NEEDED