## BLOCKING

- Task 14, transakce B: `mentions = build_mentions(...)` se počítá před vložením `new_candidates`. Nový termín z `new_terms` tedy nedostane `term_mentions` řádek. Následek: `answer` na guess otázku nového termínu nenajde původní kapitolu přes `chapters_mentioning_term()` a nepřepočítá ji. Fix: po přípravě `new_candidates` rozšířit in-memory glossary o tyto kandidáty před `build_mentions`, nebo explicitně přidat mention pro každý nový termín v kapitole.

- Task 15, `run`/`scan` lifecycle: interface říká `finish_run` ve `finally`, ale body zároveň volají `finish_run(..., "fatal")` uvnitř `except`. To je nekonzistentní a snadno přepíše `fatal` na `ok`, pokud executor použije status proměnnou špatně. Fix: přesně předepsat jeden pattern: `status = "ok"` až po úspěchu, v `except FatalRunError: status="fatal"; return/raise`, ve `finally` jediný `finish_run`.

## IMPORTANT

- Task 7 vs spec, `relationship_key`: plán zavádí „v1 omezení“ bez alias-resolve, ale spec říká jedna definice přes `normalize(resolve_surface(a))`. To není jen kosmetika: `Harry|Murphy` a `Dresden|Murphy` se nerozpoznají jako stejný vztah, rozbije merge scout faktů i requeue vztahových odpovědí. Fix: buď implementovat spec definici přes glossary/alias resolver, nebo spec explicitně změnit. Teď je to rozpor.

- Task 16 + Task 6/7, tvar `guide.json`: validní POST test v Tasku 16 neobsahuje `terms`, ale `glossary.seed_from_guide()` v Tasku 6 iteruje `guide["terms"]`. Po `review` může reseed spadnout na `KeyError`, pokud `load_guide()` nenormalizuje existující soubor s chybějícími klíči. Fix: `load_guide()` musí vždy doplnit default shape pro chybějící klíče, nebo UI musí vždy POSTovat všechny sekce včetně `terms`.

- Task 5 vs spec, cost guard u `scan`: spec říká u `scan` tvrdě zastavit, neptat se. `PipelineLLMClient` nemá žádný režim pro „non-interactive/hard stop“ a `client_factory("scout")` z Tasku 15 ho neumí vynutit. Fix: přidat parametr typu `allow_cost_prompt: bool` / `interactive: bool`; pro `scan` při překročení stropu rovnou `FatalRunError`.

- Task 14 tests: chybí test na requeue po novém kandidátovi vytvořeném pipeline. Současný `test_new_term_creates_candidate_and_question` ověřuje jen glossary + question, ne `term_mentions`. Přidat test: po `process_chapter` pro `new_terms` zavolat `requeue.apply_answer(..., answer != guess)` a ověřit, že původní kapitola jde zpět na `pending`.

## NITS

- Task 6: očekávání říká PASS „5 tests“, ale uvedeno je 6 testů.

- Task 7: očekávání říká PASS „6 tests“, ale uvedeno je 7 testů.

## VERDICT

CHANGES_NEEDED