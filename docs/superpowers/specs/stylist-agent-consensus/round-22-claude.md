# Round 22 — Claude critique

## Claude's own findings
(žádné vlastní nad rámec Codexových)

## On Codex's points

### Agreed + fixed
- **IMPORTANT - multiplicita termínů pořád neúplná:** ověřil jsem přímo -
  `check_chapter()` hlásí `actual = leaked[0]` (první existující leak),
  takže nový leak JINÉHO aliasu, když `leaked[0]` zůstane stejný,
  neprojde přes kolo-21 kontrolu počtu `actual`. Rozšířeno: pro `leak`
  nálezy se počítají VŠECHNY zakázané EN povrchy termínu (canonical +
  aliasy), ne jen `actual`; `_polish_rejected` teď bere `glossary_rows`.
  Druhou půlku návrhu ("pokles schválených CZ forem → odmítnout") jsem
  VĚDOMĚ NEPŘIJAL - pokles je nejednoznačný (stylista legitimně sloučí
  dvě věty s opakovaným termínem), false-reject cena vyšší než úzká
  zbytková skulina (navíc pokrytá `check_chapter()` novou-inconsistency
  detekcí). Zdokumentováno v docstringu.
- **IMPORTANT - `stylist.polish()` obchází konfigurační invarianty:**
  ostrý bod - `codex_cmd=[]` (falsy) tiše spadl na produkční `["codex"]`
  (nebezpečné po opt-inu), `codex_model=None` obešel povinný model,
  `timeout=180` natvrdo obešel config. Opraveno PŘÍMO v `polish()`:
  `None` vs. `[]` rozlišeno, prázdný/neúplný `codex_cmd` = `StylistError`,
  model fallback na `config.CODEX_MODEL` + prázdný = chyba, `timeout:
  int | None = None` → config. Autouse fixture nastavuje i `CODEX_MODEL`,
  nový `test_polish_config_invariants`.
- **NIT - "`_resolve_codex_cmd` se volá jednou":** upřesněno - `polish()`
  ho volá taky, ale na absolutní cestě je to jen `os.path.isabs` check,
  `shutil.which` podruhé neproběhne.
- **NIT - `timeout=180` v signatuře vs. próza:** signatura změněna na
  `timeout: int | None = None`, config komentář upraven.
- **NIT - "kosmetický úklid" sidecarů:** přeznačeno na "bezpečnostně
  nutný krok" (starý `-journal` by SQLite mohl aplikovat na obnovený
  soubor).
- **NIT - chybová tabulka vztahuje multiplicitu i na `omission`:**
  omezeno na `leak`/`inconsistency` (`omission` má `actual=None`,
  přijímá se jen množinově).

## Claude VERDICT

Po aplikaci 2 IMPORTANT (1 částečně - přijato jádro, odmítnuta druhá
půlka s odůvodněním) + 4 NITS z kola 22 (0 BLOCKING) nenacházím nic
dalšího.

`CONSENSUS`

## Summary for log

Kolo 22: Codex našel 2 IMPORTANT (0 BLOCKING, druhé kolo v řadě) + 4
NITS. (1) `_polish_rejected` kolo-21 počítal jen `actual` povrch - nový
leak JINÉHO aliasu (`actual`=`leaked[0]` beze změny) by prošel; rozšířeno
na VŠECHNY zakázané EN povrchy termínu, `_polish_rejected` bere
`glossary_rows`. Druhá půlka návrhu (pokles schválených CZ forem)
vědomě odmítnuta - false-reject legitimního sloučení vět. (2)
`stylist.polish()` veřejné API tiše obcházelo konfigurační invarianty
(`codex_cmd=[]`→produkční Codex, `codex_model=None`→bez povinného
modelu, `timeout=180` natvrdo) - všechny 3 teď vynucené PŘÍMO v
`polish()`. Čeká se na kolo 23 (22/30 stropu).
