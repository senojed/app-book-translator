## BLOCKING

- `src/agents/stylist.py: polish()` vs. `_cmd_polish` ř. 1283–1305 — povinný FS-risk opt-in je kontrolován pouze v CLI obálce. Přímé volání veřejné `stylist.polish()` spustí `codex exec` i při `STYLIST_ACCEPT_FS_RISK=False`, takže tvrzení „polish běží JEN za opt-inem“ není pravdivé. Oprava: vynutit souhlas přímo v `stylist.polish()`; CLI kontrolu ponechat jen pro časnou hlášku. Přidat test přímého volání s vypnutým opt-inem.

## IMPORTANT

- `_polish_rejected`, ř. 1029–1052 — zdůvodnění návratu z `Counter` na množinu je chybné na úrovni skutečného textu. Deduplicace `check_chapter()` pouze zaručuje nejvýše jeden finding, ale současně skryje zvýšení počtu porušení. Například původní CZ obsahuje jeden leak `White Council`; stylista změní další správný výskyt na `White Council`. Baseline i after vrátí stejný jediný klíč a regresi přijmou. Oprava: porovnávat počty/signatury skutečných výskytů, případně rozšířit findings o počet nebo všechny výskyty. Integrační test musí ověřit scénář 1→2 v textu, ne pouze absenci duplicitních findings.

- Test argv, ř. 1535–1585 — očekávaná hodnota se vytváří stejnou `_codex_argv()` funkcí jako produkční hodnota. Test je tautologický a už nezachytí odstranění `--sandbox read-only`, `--ephemeral` ani `--skip-git-repo-check`, což byl jeho deklarovaný účel. Samostatná kontrola existuje jen pro `--ignore-user-config`. Oprava: explicitně asertovat celý bezpečnostní kontrakt nebo jednotlivé povinné flagy a jejich hodnoty; duplicita mezi implementací a testovacím oracle je zde žádoucí.

- `_polish_one_chapter`, ř. 1216–1226 a 1252–1256 — všechny předchozí mentions s neprázdným `cz_form` se převádějí na `rendered_terms`, bez kontroly původního `source`. Původně `detected` mention se po úspěšném průchodu uloží jako `rendered`, čímž se falšuje provenience. Pro zachování slepé skvrny stačí předávat pouze položky se `source=="rendered"`; `detected` termíny jsou dohledatelné z EN/glosáře. Přidat regresní test zachování `source`.

## NITS

- Ř. 1882–1886 a tabulka ř. 2037 tvrdí, že FS-risk gate běží před kontrolou modelu / před čímkoli dalším. Kód na ř. 1285–1290 kontroluje `CODEX_MODEL` jako první. Sjednotit pořadí nebo prózu.

- Ř. 1323–1329 a 1441–1445 stále popisují aktuální snapshot přes `shutil.copy2`; kód od kola 14 používá `_snapshot_db()`/SQLite backup. Aktualizovat stale komentáře.

- Povinný canary, ř. 1859–1864, nepoužívá přesnou produkční argv: volá `_codex_argv(["codex"], ...)`, zatímco produkce nejprve používá `_resolve_codex_cmd()` a na Windows předává absolutní `codex.cmd`. Canary má použít rozřešený příkaz.

- Checklist ř. 1847 říká, že `-C` „skutečně izoluje“, přestože dokument následně potvrzuje neomezené čtení mimo `-C`. Upřesnit, že izoluje pouze pracovní adresář a automatické načítání projektového kontextu, nikoli filesystem.

## VERDICT

CHANGES_NEEDED