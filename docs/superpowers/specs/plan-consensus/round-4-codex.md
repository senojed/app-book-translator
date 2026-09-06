## BLOCKING

- Řádky 178, 183-192, 422-425: `answer <question_id>` řeší jednu otázku, ale stavový automat říká `needs_human → pending` po „všech blocking otázkách“ a přesná pravidla pak říkají „blocking otázka → pending vždy“. To je rozpor. Pokud kapitola má 2 blocking otázky, po první odpovědi může `run` spustit kapitolu s nevyřešenou dírou. Fix: `answer` po jedné otázce nastaví kapitolu na `pending` jen když pro `chapter_idx` nezůstává žádná unresolved `severity=blocking`.

## IMPORTANT

- Řádky 269 vs 428-429 vs 512: plán byl opraven tak, že `term_mentions` nestaví translator, ale stále zůstaly staré reference na `used_terms`. To je zavádějící kontrakt. Fix: odstranit `used_terms` z pořadí stavby/testů i komentáře schématu; `term_mentions` plní výhradně `concordance.build_mentions(EN, CZ, glossary)`.

- Řádky 304-313 vs 436: wrapper je pojmenovaný `PipelineLLMClient`, ale schéma stále mluví o `LoggedLLMClient`. Navíc `PipelineLLMClient(inner, run_id, agent, ...)` váže `agent` v konstruktoru, což je nejasné pro pipeline volající více agentů. Fix: buď explicitně vytvářet wrapper per agent, nebo dát `agent` jako parametr metody/logging contextu.

- Řádky 340-355, 393-396: `answer` může později změnit termín na `approved`, ale není jasné, jak se vyřeší konflikt s existujícím `guide.json`. Plán říká, že při reseedu vyhrává `approved`, ale translator dostává i `návod` i `glosář`; pokud guide pořád obsahuje staré CZ, prompt může být konfliktní. Fix: určit jediný zdroj pravdy pro termíny v promptu, ideálně glossary; `guide_as_prompt_block()` nesmí emitovat termíny, které přebíjí `approved` glossary.

- Řádky 360-373: `concordance.check_chapter` slibuje detekci „známé varianty != approved/seeded cz“, ale návrh neříká, odkud se ty známé varianty berou. Pokud translator použije nový český synonymní překlad, deterministická kontrola ho neuvidí jako variantu, ale jako `omission` minor. Fix: buď zúžit slib na enforceable kontroly, nebo zavést `cz_variants`/aliasy sbírané z `term_mentions`, candidates a lidských odpovědí.

- Řádky 468-469: „kanárek“ je nedotažený. Podle běhu se kapitola nejdřív nastaví na `processing`; fatal chyba pak údajně „nesahá na žádnou kapitolu“. Není jasné, zda je `processing` commitnuté před LLM voláním. Fix: explicitně popsat transakční hranice: processing commit před voláním a recovery na startu, nebo žádný zápis kapitoly před úspěšným canary voláním.

## NITS

- Řádky 315-323: tvrzení o aktuálním modelu/ceně je vhodné nechat jako ověřené k datu implementace. Anthropic docs aktuálně uvádějí `claude-sonnet-5` jako active a cenu $2/$10 per MTok, ale plán by měl mít model ID a ceny jako konfigurační hodnoty s validačním krokem před pilotem. Zdroj: https://docs.anthropic.com/en/docs/about-claude/model-deprecations a https://docs.anthropic.com/en/docs/about-claude/models/migrating-to-claude-4

- Řádek 445: lock je v `data/`, ale adresářová struktura `data/` nezmiňuje. Doplň ho nebo uveď, že se vytváří runtime.

## VERDICT
CHANGES_NEEDED