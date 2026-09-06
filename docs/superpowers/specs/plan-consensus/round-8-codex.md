## BLOCKING

- [design.md:284](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:284), [290](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:290), [415](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:415): `term_id` byl zaveden kvůli aliasům a stejnému povrchu pro různé entity, ale translator stále reportuje `rendered_terms` přes `term_en`. To neumí rozlišit homonyma/aliasy a rozbíjí `term_mentions`, drift i `questions.scope_key=term_id`.  
  Fix: prompt glosáře musí obsahovat `term_id`; translator metadata musí vracet `{term_id, cz_as_used, scene_idx}` pro známé termíny. `term_en` používat jen v `new_terms` pro neznámé povrchy.

## IMPORTANT

- [design.md:440](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:440), [441](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:441), [524](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:524): `build_mentions` tvrdí “pro každý termín” jeden `Mention`, ale `rendered_terms` má být jeden řádek na výskyt. Bez `scene_idx`/occurrence a bez pravidla pro více CZ forem v jedné kapitole se ztratí intra-chapter inconsistency.  
  Fix: definovat `term_mentions` jako jeden řádek na pozorovanou formu/výskyt nebo explicitně agregovat distinct formy; přidat `scene_idx` a případně `source=rendered|detected|omission`.

- [design.md:506](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:506), [513](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:513): `UNIQUE(chapter_idx, kind, scope_key, severity)` zkolabuje více různých `style`/`other` otázek ve stejné kapitole, protože `scope_key=""`.  
  Fix: přidat `question_hash`/`text_hash` do dedup klíče, nebo pro `style/other` generovat stabilní scope podle otázky.

- [design.md:514](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:514), [170](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:170): globální drift otázka má unikát jen `(kind, scope_key, severity) WHERE chapter_idx IS NULL`. Jakmile je zodpovězená, nový drift pro stejný termín už nepůjde založit bez přepsání historie.  
  Fix: unikátní index jen pro nevyřešené otázky (`answer IS NULL`) nebo přidat `generation/up_to_chapter`.

- [design.md:363](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:363), [532](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:532): text vyžaduje logovat `error_class`, ale schéma `llm_calls` ho nemá.  
  Fix: přidat `error_class TEXT NULL`; případně `error_message` oříznutý na rozumnou délku.

- [design.md:564](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:564), [579](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:579): fatal chyba “nesahej na žádnou kapitolu / aktuální kapitola beze změny” je v rozporu s kanárkem po transakci A, který už kapitolu přepne na `processing`.  
  Fix: buď udělat fatal kanárek před transakcí A, nebo změnit text chyby na “aktuální kapitola může zůstat `processing`, další run ji vrátí na `pending`”.

## NITS

- [design.md:426](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:426), [429](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:429): API `promote(term_en, cz)` / `add_accepted_alt(term_en, ...)` neodpovídá novému `term_id` modelu. Přepsat na `term_id`.

- [design.md:470](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:470), [476](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:476): není řečeno, jak CLI pozná, že UI úspěšně uložilo a má provést reseed. Stačí krátce definovat signál/return path.

## VERDICT

CHANGES_NEEDED