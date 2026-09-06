## BLOCKING

- Ř. 451-457 vs 157-160 vs 316-333: `check_chapter()` má vracet `Finding`, ale kandidátní `inconsistency` má být `question`. `Finding.severity` povoluje jen `critical|minor` a neobsahuje `term_id`, přitom krok 7 potřebuje `scope_key=term_id`.  
  Fix: přidej do `Finding` `term_id` a `action: revise|question|note`, nebo odděl `ConcordanceQuestion` od `Finding`.

## IMPORTANT

- Ř. 141 vs 283-300: pipeline očekává `rendered_terms = {term_id, cz_as_used, scene_idx}`, ale výstup translatora `scene_idx` nemá. Po revizním režimu se navíc metadata celé kapitoly „nahradí“, takže `scene_idx` nejde dopočítat.  
  Fix: schema sjednotit: buď `scene_idx nullable`, nebo pipeline doplňuje index jen u scén a revizní výstup explicitně ukládá `scene_idx=null`.

- Ř. 414-431, 484-487, 533-540: reseed glosáře po `review` může rozbít referenční integritu nebo historii, pokud „přepíše seeded řádky“ znamená delete+insert. `term_mentions` a `questions.scope_key` odkazují `term_id`.  
  Fix: specifikovat update-in-place podle stabilního `term_id`, nebo deterministické `term_id` při seedu, nebo zakázat/omezit reseed po rozběhnutém překladu.

- Ř. 175, 193: `run --retry-flagged` je jediná cesta pro flagged kapitoly bez použitelné otázky, ale není v seznamu CLI příkazů ani v build/test plánu.  
  Fix: doplnit CLI syntaxi, přesnou frontu stavů, zda resetuje `revision_rounds`, a test přechodu `flagged → pending`.

- Ř. 424-431 vs 292-293: `new_terms` se deduplikuje podle `term_en`, ale design současně tvrdí, že `term_id` řeší „stejný povrch, různé entity“. U termínů nalezených translatorem to nejde.  
  Fix: buď přiznat omezení v1, nebo `new_terms` rozšířit o aliasy/disambiguation a konflikt převést na `must_decide`.

## NITS

- Ř. 521-522: „partial UNIQUE“ v SQLite budou ve skutečnosti samostatné `CREATE UNIQUE INDEX ... WHERE ...`, ne inline constraint. Zapiš to tak, aby implementace nesklouzla k neplatnému DDL.
- Ověřil jsem aktuální modelový předpoklad: `claude-sonnet-5`, 1M context a 128k output odpovídají aktuální dokumentaci Anthropic. Není to problém plánu. Zdroj: https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5

## VERDICT

CHANGES_NEEDED