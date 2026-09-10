## IMPORTANT

- **Task 5, Step 3 — životní cyklus procesu při přerušení:** přebíraný kód (spec 880–891) ukončuje proces pouze při `TimeoutExpired`. Při `KeyboardInterrupt` z `communicate()` nevolá `_kill_process_tree` ani omezený `wait`; orchestrace může dokončit report a uvolnit zámek, zatímco Codex pokračuje. Testy Tasku 12 nahrazují celé `stylist.polish`, takže tuto cestu neověřují. **Oprava:** doplnit cleanup při přerušení a ostatních výjimkách po spuštění procesu, zachovat původní výjimku; testovat přerušení přímo uvnitř `communicate()` a ověřit kill/wait.

- **Task 11 — test `forwards_rendered_only_mentions` neprokazuje zachování provenience:** `rendered` i `detected` používají stejný termín, formu a scénu; kontroluje se pouze existence nějakého `rendered` záznamu. Test tak nerozpozná přeznačení původně `detected` termínu při `build_mentions`, jehož argumenty ani nesleduje. Navíc původní text „Původní věta.“ hlášenou „Přezdívku“ vůbec neobsahuje. **Oprava:** použít dva různé termíny, konzistentní původní text, sledovat argumenty `check_chapter` i `build_mentions` a po commitu ověřit provenienci obou termínů.

- **Task 9/12 — chybí test skutečného okamžiku zálohy:** test `snapshot_db_produces_logically_equal_copy` kontroluje jediný řádek glosáře; testy orchestrace jen existenci zálohy. Přesunutí snapshotu za `create_run` nebo první placenou kontrolu by stále prošlo, přestože porušuje spec 2524–2536. **Oprava:** zachytit obsah tabulek před během; během mockované kontroly skutečně vložit `llm_calls`; po přijetí porovnat zálohu s původním stavem včetně `chapters`, `runs`, `llm_calls`, `term_mentions`.

- **Task 13, Steps 2–5 — manuální ověření nemá bezpečný konec při selhání:** konfigurace se vrací až pozdějším ručním krokem. Přerušení nebo chyba mezi kroky ponechá FS opt-in zapnutý. Běh navíc mění pracovní DB a může přepsat její dosavadní jedinou zálohu; vrácení konfigurace tyto změny nevrátí. **Oprava:** ověřovat nad konzistentní kopií reálné DB v odděleném adresáři a konfiguraci nastavovat pouze v ověřovacím procesu, bez editace `config.py`. Canary spustit před průchodem knihy a použít nově vytvořený soubor s neškodným náhodným obsahem.

## NITS

- **Task 1 Step 3 / Task 4 Step 3 — rozsahy stále zahrnují markdown fence:** konfigurační kód začíná na **345**, nikoli 344; modul na **434**, nikoli 433. Task 1 navíc nesprávně umisťuje otevírací fence na 343. **Oprava:** rozsahy **345–400** a **434–746**, opravit i self-review.

- **Task 2 Interfaces — nesoulad s přebíraným kódem:** tvrzení „non-list `findings` → rozbitá odpověď“ neplatí pro `null` ani chybějící pole; spec 188 a 229 obě varianty přijímá jako prázdné findings. **Oprava:** explicitně popsat tuto výjimku a přidat test očekávaného chování.

## VERDICT
CHANGES_NEEDED