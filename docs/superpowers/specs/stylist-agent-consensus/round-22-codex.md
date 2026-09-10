## IMPORTANT

- `main.py`, `_polish_rejected()` ř. 1090–1117 a `_polish_one_chapter()` ř. 1279–1298 — ochrana multiplicity termínů stále není úplná. Pokud před i po zůstane alespoň jeden správný český tvar, změna dalšího správného výskytu na libovolný chybný tvar nevytvoří žádný nález. Obdobně nový leak jiné EN aliasové podoby projde, pokud `check_chapter()` nadále hlásí jako `actual` první již existující leak. LLM kontroly mohou oba případy minout. Nejde o dříve odmítnutý obecný NLP extraktor: stačí pro zkoumané glosářové termíny porovnat před/po celkový počet schválených CZ forem a počet každé zakázané EN surface; pokles prvního nebo nárůst druhého odmítnout. Přidat oba regresní testy.

- `stylist.polish()` ř. 663–727 — veřejné API nedodržuje deklarované konfigurační invarianty. `codex_cmd=[]` se kvůli `if codex_cmd else ["codex"]` tiše změní na produkční Codex místo chyby, což po bezpečnostním opt-inu může nečekaně spustit agenta s přístupem k disku. Současně `codex_model=None` obejde povinný `CODEX_MODEL` a pevný `timeout=180` obejde `STYLIST_TIMEOUT_SECONDS`. Rozlišit `None` od prázdného seznamu, prázdný příkaz odmítnout a povinný model i konfigurovaný výchozí timeout vynutit přímo v `polish()`; CLI kontroly mohou zůstat jako časný UX guard.

## NITS

- Ř. 970–975 tvrdí, že `_resolve_codex_cmd` se volá jednou, ale `polish()` jej volá znovu pro každou kapitolu; pouze `shutil.which` už podruhé neproběhne. Upravit formulaci nebo předat explicitně označený rozřešený příkaz bez opakované validace.

- Ř. 322–325 tvrdí, že timeout už není natvrdo ve výchozím parametru `polish()`, zatímco podpis na ř. 663 stále obsahuje `timeout: int = 180`. Sjednotit prózu a kód.

- Ř. 1212–1214 označuje odstranění starých sidecarů za „kosmetický úklid“, přestože okolní text správně popisuje riziko změny či poškození obnovené DB. Označit jej jako bezpečnostně nutný krok.

- Chybová tabulka ř. 2182 vztahuje počet `actual` i na `omission`, kde je `actual=None` a kontrola multiplicity se neprovádí. Omezit formulaci na `leak`/`inconsistency`; stejný `omission` klíč se přijímá pouze množinovým porovnáním.

## VERDICT

CHANGES_NEEDED