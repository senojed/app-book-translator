## BLOCKING

- `concordance.py` / `glossary.py`: `leak = EN podoba termínu je v CZ textu nepřeložená → vždy critical` koliduje s `keep → cz=term_en`. Ponechaná jména/termíny budou falešně critical.  
  Fix: `leak` se nesmí hlásit pro položky, kde je schválený/seeded render `cz == term_en`, případně rozlišit `must_translate` vs `may_keep`.

- `llm/client.py` vs hranice modulů: `LLMClient.complete()` nemá `run_id`, `agent`, DB handle ani callback, ale plán tvrdí, že klient po každém volání zapisuje do `llm_calls`. Současně `llm/client` podle tabulky nezná pipeline/agenty. To je neimplementovatelné bez porušení hranic.  
  Fix: buď logging přes wrapper v pipeline `LoggedLLMClient(run_id, agent, inner, state)`, nebo rozšířit protokol o explicitní telemetry callback. Ne přímo DB uvnitř obecného klienta.

- `Cost guard`: plán říká, že `complete()` vrací `count_tokens()` odhad, ale guard ho potřebuje před voláním. `Completion` žádné pole pro odhad nemá a protokol nemá samostatnou metodu.  
  Fix: přidat do `LLMClient` `count_tokens(system, user, model) -> int` a jasně říct, že cost guard běží v pipeline před `complete()`.

- `questions` / `answer`: translator output obsahuje jen `{"text", "severity"}`, ale requeue pravidla vyžadují `kind`, `scope_key`, `guess_answer`. Pipeline je z textu spolehlivě neodvodí.  
  Fix: rozšířit output otázky na `kind, scope_key, guess_answer, text, severity`; pro `blocking` určit, zda má kapitola vždy requeue, nebo zda může po odpovědi jen změnit pravidlo.

## IMPORTANT

- Stav `error`: sekce run říká, že `needs_human` a `error` se přeskočí; automat říká `error --run auto retry--> pending`. To je přímý rozpor.  
  Fix: definovat jedno chování, např. běžný `run` retryuje `error`, nebo jen `run --retry-errors`.

- `needs_human` + `answer == guess_answer`: pravidla říkají „nic dalšího, žádná kapitola se nepřekládá znovu“, ale automat říká `needs_human -> pending`. Není jasné, jak se kapitola dostane do `done`.  
  Fix: pro blocking otázky definovat samostatně: po zodpovězení vždy `pending`, nebo pokud původní překlad zůstává platný, přechod na `done`.

- Review UI / `must_decide`: `must_decide` je jen pole volných stringů. Není určeno, kam se odpověď zapíše: do postav, termínů, vztahů, nebo `rules`.  
  Fix: změnit scout schema na strukturované rozhodnutí `{kind, scope_key, question, options/default}`.

- `POST /api/guide`: „seed glosáře se přegeneruje při každém uložení“ může smazat runtime `approved`/`candidate` položky nebo změnit jejich status.  
  Fix: popsat merge strategii: přegenerovat jen `seeded`, zachovat `approved/candidate`, řešit konflikty explicitně.

- `term_mentions`: při requeue kapitoly se neříká, že staré mentions pro kapitolu musí být smazány před novým překladem. Drift pak bude počítat zastaralé formy.  
  Fix: při startu nebo commitu retranslation `DELETE FROM term_mentions WHERE chapter_idx=?`.

- `llm_calls`: schéma neobsahuje cenu, provider, stop reason/truncated, status/error. Pro cost guard a audit bude nutné zpětně mapovat ceny podle modelu a data.  
  Fix: přidat aspoň `provider`, `estimated_cost_usd`, `truncated`, `status`.

- `critic` truncation: „varování, zparsuj část“ je rizikové. Částečný JSON často nepůjde validně parsovat a může minout critical nálezy.  
  Fix: u kritika raději retry s vyšším `max_tokens`; po selhání označit kapitolu `flagged` nebo `error`, ne tichý pass s varováním.

## NITS

- Model `claude-sonnet-5` a tvrzení o 1M context / 128k output jsou aktuální technické předpoklady. Před implementací je ověřit proti Anthropic docs a dát do configu, ne tvrdě do logiky.

- `export --only-done = ostatní úplně vynechá` je prakticky nebezpečné. Minimálně by měl stdout vypsat seznam vynechaných kapitol.

## VERDICT

CHANGES_NEEDED