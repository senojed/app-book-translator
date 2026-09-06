## BLOCKING

- Ř. 294-303, 250-262: `Cost guard běží v pipeline PŘED complete()`, ale prompty a `complete()` volají agenti uvnitř. Pipeline předem nezná `system/user/max_tokens`, takže nemůže spolehlivě zavolat `count_tokens()` před každým voláním. Fix: přesunout cost guard do wrapperu `GuardedLoggedLLMClient.complete()` nebo změnit rozhraní agentů tak, aby nejdřív vraceli request objekt.

## IMPORTANT

- Ř. 353-359: `check_chapter(cz_text, glossary)` nemá EN originál ani informaci, zda se termín v kapitole vůbec vyskytuje. Nemůže korektně rozhodnout, že „očekávaný CZ tvar chybí“. Fix: přidat EN kapitolu / seznam termínů nalezených v EN, nebo stavět kontrolu nad deterministicky extrahovanými mentions.

- Ř. 146, 189-190, 253-262: requeue po odpovědi závisí na `term_mentions` dodaných translatorem. Pokud translator termín v `used_terms` vynechá, kapitola se nepřepočítá, i když obsahuje špatné rozhodnutí. Fix: `term_mentions` generovat deterministicky z EN kapitoly a/nebo CZ textu, ne důvěřovat pouze LLM metadatům.

- Ř. 192, 401-413: pravidlo „answer nikdy nesahá na právě zpracovávanou kapitolu“ není implementovatelné ve schématu. Neexistuje `processing` stav, lock, `run_id` na kapitole ani transakční vlastnictví kapitoly. Fix: přidat single-run lock a stav `processing`, nebo explicitně zakázat paralelní CLI příkazy během `run`.

- Ř. 450-453: cost guard započítává `count_tokens` pro vstup, ale výstupní cenu aktuálního volání specifikuje jen nepřímo. U překladače je output hlavní náklad. Fix: do vzorce přidat `max_tokens * output_rate` pro aktuální volání, případně konzervativní odhad podle typu agenta.

- Ř. 436, 450-453: rozpor v rollbacku. Tabulka tvrdí, že při překročení `MAX_SPEND_USD` jsou „kapitoly beze změny“, ale uprostřed `run` už mohou být předchozí kapitoly commitnuté. Fix: upřesnit „aktuální kapitola beze změny, dříve commitnuté kapitoly zůstávají“.

- Ř. 237-240, 329: chunked scout merge deduplikuje podle jména, ale není řečeno, jak řeší aliasy, kolize jmen a konfliktní vztahy `tyká/vyká` napříč chunky. Fix: definovat normalizační klíč, konflikt jako `must_decide`, a merge pravidla pro relationships.

## NITS

- Ř. 3: `Stav: schváleno` je matoucí pro dokument v aktivním review kole. Lepší `návrh` / `v revizi`.

- Ř. 125: `answer 3 "..."` neříká, zda `3` je ID otázky, nebo kapitola. Fix: přepsat na `answer <question_id> "..."`.

## VERDICT
CHANGES_NEEDED