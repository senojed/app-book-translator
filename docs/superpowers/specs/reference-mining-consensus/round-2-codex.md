## BLOCKING

- **Rozhodnutí 4 / test `stole`:** Case-sensitive hledání `stole` stále najde české „stole“. Proto může běžný český homograf při ≥5 výskytech ve ≥2 knihách skončit jako `confirmed`. Navržený test má chybný očekávaný výsledek. Oprava: povrchy začínající malým písmenem nikdy automaticky nepotvrzovat, případně zavést explicitní allowlist/denylist a přesnější kontextovou validaci.
- **Rozšíření `src/guide.py`:** Pravidlo „vynechat blok `reference`, liší-li se zobrazované `cz` od `matched_cz`“ odstraní metadata u každého `proposed`/`contradicted`: jejich `cz` je záměrně prázdné, zatímco `matched_cz` obsahuje návrh. UI pak nemůže zobrazit klasifikaci ani návrh. Oprava: vazbu `cz == matched_cz` vyžadovat jen pro důkaz předvyplněné hodnoty (`confirmed`/`weak`); návrhový blok zachovat nezávisle.
- **Review UI / integrace:** Existující `build_app(draft_path, guide_path, ...)` a `run_review_server(draft_path, guide_path, ...)` reference vůbec nedostávají; `GET /api/guide` volá starý dvouzdrojový wrapper, který má podle plánu použít `reference=None`. Výsledek těžby se tedy do UI nikdy nedostane. Oprava: specifikovat `REFERENCE_PATH`, loader a změny obou signatur i `_cmd_review`, včetně kompatibility testů.

## IMPORTANT

- **Klasifikace stupně 1:** „souvýskyt sedí“ nemá definovaný predikát. Není určeno, zda stačí jeden společný díl, všechny CZ výskyty, minimální počet knih nebo poměr. Oprava: uvést přesný deterministický vzorec a hraniční testy.
- **Chyby dávek / `write_reference`:** Rozbitá dávka se přeskočí, ale na konci se celý dosavadní `reference.json` nahradí. Přechodná chyba tak může smazat dříve platné nálezy pro celou dávku. Oprava: při jakémkoli selhání nepublikovat nový soubor, nebo pro selhané položky převzít předchozí nálezy a označit je jako stale.
- **Atomické zápisy:** Tvrzení, že zápis dat a následně reportu „nenechá data bez reportu“, je nepravdivé; pád mezi dvěma `os.replace` přesně tento stav vytvoří. Oprava: označit report za odvoditelný a obnovitelný, kontrolovat společný `run_id`, nebo publikovat oba artefakty přes atomicky přepínaný adresář/manifest.
- **CLI a konfigurace:** Není určena syntaxe příkazu `reference`, zdroj `root`, nové cesty, `MODEL_LEXICOGRAPHER`, tokenový limit ani přidání příkazu do `_MUTATING`. Bez toho nelze implementovat napojení na současný parser a cost guard jednoznačně.
- **Výstup lexikografa:** Chybí validace, že odpověď obsahuje právě požadované termíny, bez duplicit a neznámých položek, a že `cz` je `str | null`. Pouhé párování podle vráceného `term_en` umožní záměnu či tiché vynechání položek. Oprava: mapovat přes normalizovaný klíč, odmítnout duplicity/extra položky a chybějící položky převést na explicitní `unresolved`.
- **Persistovaný view-model:** Současný POST ukládá celý payload přímo do `guide.json`. Nové bloky `reference` se tak uloží mezi lidská rozhodnutí a mohou zastarat po dalším běhu těžby. Oprava: před `save_guide` metadata serverově odstranit; `guide.json` musí zůstat kanonický lidský model.
- **Identita při slévání:** Reference používá NFC + `casefold()` + zúžení whitespace, zatímco stávající `guide.normalize()` pouze `strip().lower()`. Není řečeno, že `merge_sources` přejde na stejnou normalizaci. Oprava: jedna sdílená normalizační funkce pro těžbu, merge i UI upsert.

## NITS

- **Pravidla hledání:** Upřesnit escapování regexových metaznaků, chování apostrofů/pomlček a přesnou detekci začátku věty.
- **Chyby agenta:** Určit zacházení s `OutputTruncated`; současný text řeší jen neparsovatelný JSON.

## VERDICT

CHANGES_NEEDED