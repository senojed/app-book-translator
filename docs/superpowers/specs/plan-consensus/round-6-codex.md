## BLOCKING

- `glossary.py` / `concordance.py` ř. 394-398, 422-424: `variants` jsou zároveň „pozorované tvary“ i „akceptované tvary“. To rozbije kontrolu: první špatný tvar schváleného termínu se přidá do `variants`, další kontrola ho už nebude brát jako inconsistency. Fix: oddělit `accepted_variants` od `observed_forms`, nebo `variants` nepoužívat jako výjimku pro approved/seeded bez lidského potvrzení.

- Stav + soubory, ř. 147-162, 390, 447-448, 525-530: plán tvrdí „commit kapitoly je jedna transakce“, ale glosář je JSON mimo SQLite. Crash mezi zápisem JSON a DB zanechá nekonzistentní stav. Fix: runtime glosář uložit do SQLite, nebo explicitně navrhnout atomický reconciliation protokol. Pro pokus 2 doporučuji SQLite.

## IMPORTANT

- Run lock, ř. 501-506: `review` není uveden mezi mutujícími zamčenými příkazy, ale zapisuje `guide.json` a reseeduje glosář. Může kolidovat s `run`/`scan`. Fix: `review` musí držet stejný lock minimálně při `POST /api/guide`, lépe po dobu serveru.

- `answer`, ř. 191-200 vs otázky ř. 270-274: `kind=relationship` a `kind=other` nemají definované chování. U vztahu není jasné, kam se odpověď zapisuje ani které kapitoly se requeue. Fix: relationship update do `guide.relationships`, `scope_key="a|b"`, affected chapters definovat explicitně; `other` buď zakázat, nebo mapovat na `guide.rules`.

- Drift, ř. 170-172 a 427-431: drift se jen reportuje do `drift_reports` a vypíše počet nálezů. Není cesta k otázce, requeue ani export markeru. Fix: drift findings převést na actionable questions nebo flag affected chapters.

- `rendered_terms`, ř. 138-151 a 279-284: fresh translator běží po scénách, ale pozdější kroky mluví o jedné množině pro kapitolu. Není definované slučování metadat po scénách a po revizním režimu. Fix: explicitně: aggregate per-scene `rendered_terms`/`new_terms`/`questions`; při revizi zahodit stará metadata kapitoly a použít metadata z revizního celokapitolového výstupu.

- `questions` schéma, ř. 476-480: chybí dedup/supersede pravidlo. Rerun kapitoly může založit stejné unresolved otázky opakovaně. Fix: unikátní klíč pro otevřené otázky `(chapter_idx, kind, scope_key, text/severity)` nebo upsert + `superseded_at`.

## NITS

- Ř. 139: signatura `concordance.check_chapter(EN kapitola, CZ, glosář)` je v rozporu s ř. 419, kde vyžaduje i `rendered_terms`. Sjednotit.
- Ř. 279-280: „pro každý termín z dodaného glosáře“ je drahé a zbytečné. Lepší: jen termíny, kterých se translator dotkl nebo jejichž EN surface/alias je ve scéně.
- Model `claude-sonnet-5` a 1M/128k jsou aktuálně v souladu s Anthropic docs, ale ceny se po 2026-08-31 měnily; držet validaci před pilotem. Zdroj: https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5

## VERDICT

CHANGES_NEEDED