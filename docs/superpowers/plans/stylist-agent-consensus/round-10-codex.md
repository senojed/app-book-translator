## NITS

- **Task 8, `test_rejection_keep_untranslated_term_no_leak_finding_not_rejected`:** odkaz „spec 171: leak jen když cz != canonical“ je chybný; řádek 171 obsahuje `extract_json(comp.text)`. Relevantní scénář je na řádcích **2631–2633**. Tvrzení, že `concordance.check_chapter` takový nález nikdy neemituje, označ **would verify** v `src/concordance.py`; vložený spec jeho implementaci neobsahuje.

## VERDICT
CONSENSUS