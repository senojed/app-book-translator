## IMPORTANT

- **Task 11–12: redakce uvnitř skutečné `_run_critic` není ověřena.** Testy ji nahrazují mockem, takže kontrolují až výjimku předanou orchestrace. Přitom nový `critic.review()` zahrnuje neplatný verdikt přímo do `ValueError` (spec 225–227); může obsahovat text převzatý ze `styled`. Pokud `_run_critic` chybu vypíše nebo uloží před návratem `critic_failed=True`, pozdější redakce nepomůže. **Would verify:** skutečné logování `_run_critic` a klienta. **Oprava:** integrační test se skutečnými `critic.review` a `_run_critic`, fake klientem vracejícím dvakrát verdikt `"SECRET123"` a vypnutým report opt-inem; ověřit nepřítomnost secretu v konzoli, reportu a případné perzistentní diagnostice.

## NITS

- **Task 13 Step 2:** canary runner ošetřuje pouze timeout; při Ctrl+C stále nechá potomka běžet. Převzít také ukončení při `BaseException` z Tasku 5 a dát úklid T1/T2 do `finally`.
- **Task 13 Step 2:** `open(...out.txt).read()` nemá `encoding="utf-8"`. Při druhém běhu s českou kapitolou může lokální dekódování poškodit právě posuzovanou diakritiku. Číst explicitně jako UTF-8.
- **Task 11 Step 3:** převzatý docstring (spec 1477–1479) tvrdí, že smyčka má tři větve `report.append`; Task 12 zavádí jediný append ve `finally`. Přidat explicitní odchylku opravující tento popis.

## VERDICT
CHANGES_NEEDED