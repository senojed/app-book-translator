## IMPORTANT

- Ř. 155–161, 283–289: `new_terms` nemají garantovanou otázku ani stabilní `term_id` při vzniku. Pokud translator přidá kandidátní termín, plán neříká, zda se má automaticky založit `guess` otázka a jak se otázce doplní `scope_key` po `add_candidate`. Fix: po insertu kandidáta vytvořit/aktualizovat `question(kind=term, scope_key=term_id, guess_answer=cz)`.

- Ř. 424–428, 497–502: konflikt candidate vs seeded není vyřešen. Kandidát má `term_id="cand_"+slug(term_en)`, reseed z guide použije `slug(canonical_en)` a `candidate` řádky “se nedotknou”. Výsledek: dvě entity pro stejný termín, rozbitý prompt, drift i requeue. Fix: reseed musí najít kandidáta podle `canonical_en/aliases`, převést ho na seeded/approved nebo migrovat FK; případně používat stejný `term_id` i pro kandidáty.

- Ř. 456–464, 473–478: `term_mentions = ÚPLNÝ pozorovací záznam` je nepravdivé. Neznámé CZ varianty zachytíš jen když je translator uvede v `rendered_terms`; deterministická detekce hledá jen `cz/accepted_alt/kmen`. Drift tedy není úplný. Fix: změnit tvrzení na best-effort, nebo přidat deterministicky dohledatelné pozice/strategie; nespoléhat na úplnost v downstream logice.

- Ř. 202, 267–268, 532: `relationship` scope_key `"a|b"` nemá jednotnou normalizaci. Scout merge používá `sorted(a,b)`, answer jen `"a|b"`. Různé pořadí/jmenný alias založí duplicity nebo zapíše odpověď jinam. Fix: definovat `relationship_key(a,b)=sorted(normalize(resolve_alias(a)), normalize(resolve_alias(b))).join("|")` a používat všude.

- Ř. 369–370, 621–623: cost guard po potvrzení limitu nemá stav. Jakmile `spent_so_far + estimate > MAX_SPEND_USD`, bude se ptát před každým dalším voláním. Fix: po potvrzení uložit per-run override/nový limit, nebo vyžadovat navýšení `MAX_SPEND_USD`.

- Ř. 536–542: “upsert” nad dvěma partial unique indexy je nedospecifikovaný. SQLite `ON CONFLICT` musí cílit konkrétní index/predicate; jeden obecný upsert pro NULL i non-NULL `chapter_idx` nebude triviálně fungovat. Fix: specifikovat helper `upsert_open_question`, který větví globální vs kapitolové otázky, nebo použít explicitní SELECT+UPDATE/INSERT v transakci.

## NITS

- Ř. 125: CLI seznam neuvádí `scan --chunked`, i když je součást rozsahu.
- Ř. 383–387: model `claude-sonnet-5` jsem ověřil jako aktivní v aktuálních Anthropic docs; ponechat pilot check cen/limitů. Zdroj: https://docs.anthropic.com/en/docs/about-claude/model-deprecations

## VERDICT

CHANGES_NEEDED