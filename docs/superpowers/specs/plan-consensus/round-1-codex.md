## BLOCKING

- Řádky 135-136, 187-189: revizní translator podle pseudokódu dostává jen `CZ + nálezy`, ne explicitně EN originál. Bez EN neumí opravit věrnost, vynechávky ani významové chyby. Fix: revizní režim definovat jako `EN kapitola/scéna + předchozí CZ + critic findings + guide + glossary`.

- Řádky 326-327: u `kritik / scout` je useknutý výstup jen varování a parsování části. To je špatně hlavně pro `scout`: částečný guide může tiše vynechat postavy/termíny a znehodnotit celý běh. Fix: truncated scout/critic = fail/retry/chunking; nikdy nepokračovat s částečným JSON jako autoritativním vstupem.

## IMPORTANT

- Řádky 173-184, 375-376: celý scout v jednom 130k-word volání je označen jako plán, ale zároveň otevřená otázka pilotu. To je nekonzistentní základ architektury. Fix: už v designu definovat fallback `scan --chunked`: kapitoly/chunky → partial scout facts → merge/deduplicate → review UI.

- Řádky 237-238: model ID je ověřitelně aktivní, ale Sonnet 5 má změny API chování. Anthropic docs uvádí `claude-sonnet-5`, 1M context, 128k output a zákaz non-default sampling parametrů. Fix: do provider vrstvy explicitně napsat „neposílat temperature/top_p/top_k pro Sonnet 5“ a přidat token counting před pilotem. Zdroj: https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5

- Řádky 270-279, 260-266: drift check nemá data, která slibuje analyzovat. `glossary` má `{term_en: {cz,...}}` a `add_or_update()` pravděpodobně přepíše starý překlad, takže nelze „posbírat všechny odlišné tvary napříč kapitolami“. Fix: ukládat `term_mentions(term_en, cz_observed, chapter_idx, source)` nebo ve glossary držet `variants[]` + kapitoly.

- Řádky 137, 260-266: automatické přidávání `new_terms` z translatora do závazného glosáře bez validace může zafixovat halucinovaný nebo špatný překlad a šířit ho dál. Fix: rozlišit `candidate_terms` a `approved_terms`; do promptu dalších scén dávat kandidáty slabě, do concordance jen schválené nebo seedované termíny.

- Řádky 121, 164-165, 309-310: schema otázky neobsahuje odhadnutou odpověď ani dopadovou oblast. Přitom plán chce poznat, zda se odpověď liší od guess, a „přepočet kapitol“. Fix: přidat `guess_answer`, `applies_to`/`term_en`/`rule_key`, `affected_chapters`; definovat přesně, co `answer` requeueuje.

- Řádky 312, 335-337: cost guard je jen měkký odhad před kapitolou a `runs` ukládá jen agregát. Při pádu procesu se usage ztratí a `scan` může překročit limit před jakoukoli pauzou. Fix: persistovat usage po každém LLM callu; guard použít i pro `scan`; přidat worst-case odhad včetně revizních kol.

- Řádky 324-327: globální konfigurační/API chyby se míchají s per-kapitola chybami. Špatný klíč, invalid model nebo 400 kvůli parametrům označí kapitoly `error` a `run` „pokračuje“, což jen hromadně vyrábí špatný stav. Fix: klasifikovat chyby na fatal run-level vs recoverable chapter-level; fatal ukončí příkaz bez změny kapitol.

## NITS

- Řádky 11-12: věta „Přechod z brainstormu rovnou do kódu, chyběl psaný spec.“ je fragment. Upravit na plnou větu.

- Řádek 279: „škáluje na 350 kapitol“ nesedí s cílem „~350 stran“. Fix: „desítky kapitol“ nebo skutečný odhad počtu kapitol.

- Řádky 363-369: Review UI je až po CLI `run`, ale `run` závisí na `guide.json` z review fáze. Fix: pořadí stavby dát `scan + minimal review/approve path` před plný `run`.

## VERDICT

CHANGES_NEEDED