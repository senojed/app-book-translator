## BLOCKING

- **Task 5, Step 7 (ř. 720–738): chybí vytvoření snapshotu.** `_backup_db_once` pouze přejmenuje existující soubor (`main.py:442`); plán nastaví cestu, ale nikde nevolá `_snapshot_db`. První zápis dávky skončí `FileNotFoundError`. Vytvořit snapshot před zpracováním a uklízet jej ve `finally`; opravit také test helperu.

- **Task 5, Step 3 + Task 13, Step 5: nepovolený zdroj historie.** `polish_store._VALID_HISTORY_SOURCES` přijímá pouze `"polish-review"` a `"revert"`. `"polish-batch"` proto selže při `save_history`, již **po změně DB**. Rozšířit validaci před zavedením dávkového zápisu a přidat test kompatibility staré historie.

- **Task 5, Step 3 + Task 9, Step 3: regrese při částečném zápisu.** Historie se načítá až po DB commitu; poškozený soubor tedy nezabrání změně knihy. Endpoint následně nepravdivě tvrdí „Text NEBYL uložen“. Načíst a validovat historii před commitem, rozlišit chyby před/po commitu a zachovat obnovitelný stav. Task 14 musí zobrazovat `history.stale`; nyní existující upozornění odstraňuje. Pokrýt také první zápis, po jehož selhání žádná historie neexistuje.

- **Task 5, Step 3/7: dávka nemá CAS ani kontrolu vlastnictví zámku před zápisem.** `cz_before` se pouze uloží do historie; `state.commit_chapter_result` provádí bezpodmínečný `UPDATE`. Kapitoly přitom pocházejí ze seznamu načteného před celou dávkou a `run_lock` neobnovuje šestihodinovou platnost. Před každým commitem obnovit/ověřit zámek a porovnat aktuální text a stav s výchozí verzí; při nesouladu nic nepřepsat.

- **Tasky 5/7/8/9/11/14: nálezy se násobí a rozcházejí.** Commit uloží stejný seznam do `notes` i historie; detail/report je zřetězí. Jeden nález se zobrazí dvakrát, po další editaci čtyřikrát. Checkbox aktualizuje pouze první nalezené úložiště. Navíc dávka přepíše původní nálezy z `run`, které má report údajně slučovat. Určit autoritativní úložiště a pravidla zachování nálezů, deduplikovat podle ID a používat stejnou agregaci také pro `/api/chapters`, který nyní historii vůbec nepočítá.

- **Task 5, Step 3 + Task 9: rozbitá sémantika `--force`.** Nový commit nepřidává `_stylist_marker`; ruční save navíc přepíše notes seznamem, ze kterého GET markery odstranil. `_already_styled` hledá právě tento marker (`main.py:100`). Další běh proto znovu stylizuje již dokončené kapitoly i ruční opravy bez `--force`. Zachovat serverem spravovaný stav stylizace a otestovat posloupnost batch → editace → batch bez/s `--force`.

## IMPORTANT

- **Tasky 2/8/13: chybí migrace existujících nálezů.** GET žádná ID nedoplňuje a stará data je nemají. Ponechaný revert navíc vytváří nové nálezy bez ID. Checkboxy proto nefungují nad existující knihou ani po revertu. Doplnit jednorázovou perzistentní migraci pod zámkem a přidělování ID ve všech zachovaných zápisových cestách.

- **Task 9, ř. 1304: ztráta `rendered_terms`.** Save vždy čte živé mentions, které předchozí polish mohl zúžit. Nová historie tím zahodí původní translatorem hlášené formy; následný revert je neobnoví. Zachovat metadata odpovídajícího historického řetězce; živou DB použít pouze bez použitelné historie. Rozšířit existující test `test_revert_uses_stored_rendered_terms_not_narrowed_live_mentions` o mezilehlou ruční editaci.

- **Tasky 9/11: textový CAS nechrání změny `resolved`.** Karta A načte nálezy, karta B jeden vyřeší, karta A uloží text se starým seznamem. Textový CAS projde a vyřešení zmizí. Zavést revizi metadat nebo při save slučovat aktuální stav podle ID; otestovat dvě karty.

- **Task 14, `toggleResolved`: chyby zápisu jsou skryté.** UI označí nález jako vyřešený i při 400/404/500/503. Nové nálezy z regenerace navíc ještě nejsou v žádném serverovém scope. Rozlišit lokální a uložené nálezy, přenášet skutečný scope a při neúspěchu zobrazit chybu a vrátit checkbox. Samotné „zkus oba scope“ nestačí.

- **Task 10: regenerace není bez zápisů.** `create_run`, `finish_run` a `PipelineLLMClient` zapisují do DB, přesto endpoint obchází zámky. `_client_factory` navíc účtuje do `config.DB_PATH`, nikoli předaného `db_path`, a `interactive=True` může HTTP požadavek zastavit čekáním na terminál. Vymezit povolené auditní zápisy, zajistit jejich zamykání, předávat správnou DB a použít neinteraktivní cost guard.

- **Tasky 9/14: editor nabízí úpravu všech kapitol, uloží pouze `done`.** Například `flagged` kapitolu lze otevřít a upravovat, ale save vždy vrátí zavádějící konflikt. Definovat podporované stavy a jejich přechody; umožnit opravu přeložených problematických kapitol bez automatického obejití otevřených otázek.

- **Task 12, ř. 1664–1673: export obchází i specifikací požadované `require_lock()`.** Souběžný save může způsobit, že kniha a report zachytí různé verze; souběžné exporty zapisují přímo do stejných souborů. Export serializovat, sestavit oba výstupy z konzistentního stavu a publikovat přes dočasné soubory. Task 14 musí zobrazit také vrácené `skipped`, které nyní ignoruje.

- **Task 9, ř. 1283–1305: nedostatečná validace findings.** `[null]` projde kontrolou seznamu a shodí `assign_ids`; neplatné typy `severity`, `id` či `resolved` mohou projít až do perzistence a rozbít report nebo identitu nálezů. Validovat jednotlivé objekty, neprázdná unikátní ID a typy používaných polí před jakýmkoli zápisem.

- **Task 14, regenerace/save: opožděné odpovědi mohou zahodit editaci.** Během regenerace zůstává textarea i save aktivní; pozdější odpověď bezpodmínečně přepíše novější text. Také `loadChapter()` po save přepíše změny napsané během požadavku. Použít revizi lokální editace a ignorovat zastaralé odpovědi nebo konfliktní ovládání dočasně zablokovat.

- **Task 13, Step 3: odstranění `draft_path` není dokončené.** V `build_app` zůstává `app.state.draft_path = draft_path` (`polish_server.py:559`), takže uvedené změny skončí `NameError` při startu. Výslovně odstranit atribut a ověřit všechny odkazy v produkčním kódu, nejen v testech.

- **Tasky 1/4/5/6/13: testovací postup není bezpečně připravený.** `_db` a `_make_db_with_one_chapter` v `tests/test_cli.py` neexistují. `_polish_env` nepřesměrovává `POLISH_HISTORY_PATH`, takže nové dávkové testy mohou zapisovat do skutečné historie projektu. Reload konfigurace z Tasku 1 ponechá změněné globální cesty i po obnovení prostředí. Opravit izolaci fixtures a převést stávající testy zámků, poškozené historie a částečného commitu na nové endpointy; nemažte je pouze proto, že používají draft fixture.

## NITS

- **Task 3, Step 7:** deklarované PASS nenastane, pokud zůstane `tally['drafted']` v `main.py:1234`. Přejmenovat také tento přístup již v Tasku 3.
- **Task 8, ř. 1169:** `find_chain_start` vrací začátek posledního souvislého řetězce, nikoli nejstarší záznam požadovaný novou specifikací. Výslovně sjednotit význam „originálu“ ve specifikaci, implementaci a testu historie s přerušeným řetězcem.

## VERDICT

CHANGES_NEEDED