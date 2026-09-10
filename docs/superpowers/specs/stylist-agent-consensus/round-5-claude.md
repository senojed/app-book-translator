# Round 5 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní - Codex round 5 pokryl to podstatné)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
(žádné vlastní)

## On Codex's points

### Agreed + fixed
- **BLOCKING - chybějící `encoding="utf-8"`:** ověřeno vlastní zkušeností
  z týhle konverzace (opakovaně jsem řešil `UnicodeEncodeError`/cp1252
  problémy v tomhle přesném prostředí u jiných Python volání). Přidáno
  explicitně na `Popen`.
- **BLOCKING - `rendered_terms=[]` je skutečná slepá skvrna, ne jen
  ztráta metadat:** Codex mě přesvědčil zpět - v kole 4 jsem to hodnotil
  jako přijatelný metadatový kompromis, ale `examined_terms()` termín
  zachycený VÝHRADNĚ přes `rendered_terms` (bez přesné EN shody povrchu)
  s prázdným seznamem vůbec NEZKOUMÁ - žádná baseline, žádný `after`
  nález, úplně neviditelné. Přidán `state.chapter_mentions()` (potvrzeno -
  je to skutečně malý getter, stejný vzor jako existující `get_chapter`),
  zapojen do `_polish_one_chapter` pro baseline i `after` volání i
  přepočet mentions.
- **IMPORTANT - `critic.review()` pořád fail-open na neplatný `verdict`:**
  přidána `verdict in ("pass", "revise")` kontrola - modul sám tvrdí, že
  rozbitý výstup vede k retry+výjimce, tohle byl přesně ten nedodržený
  případ.
- **IMPORTANT - `timeout` na Windows neukončí celý strom procesů
  (`codex.cmd` → `node.exe`):** Toto je obecně známá, zdokumentovaná
  Windows `subprocess` limitace (timeout kill jde jen na přímého potomka).
  Přepsáno z `subprocess.run` na `Popen`+`communicate`, `_kill_process_tree`
  s `taskkill /T /F` na Windows při timeoutu.
- **IMPORTANT - "všechno selhalo" nastavovalo `status="ok"` navzdory
  vlastnímu zdůvodnění "systémový symptom":** Souhlasím, že to byl vnitřní
  rozpor - opraveno na `status="fatal"` spolu s nenulovým exit kódem.
- **NITS - zastaralá próza (vstup přes soubor, baseline z `notes`,
  `(type, term_id)` bez `actual`):** opraveno na 4 místech, kde předchozí
  kola nechala prózu neaktualizovanou po změně kódu.

### Agreed but already addressed
(žádné - kolo 5 nálezy jsou nové)

### Disagreed (s odůvodněním, zachováno z kola 4)
- **IMPORTANT - deterministická kontrola čísel/dat:** Codex teď navrhuje
  UŽŠÍ verzi (jen multiset arabských čísel/procent/měn/dat, ne kompletní
  NLP extraktor) - to je rozumnější návrh než kolo 4, ale pořád jde o
  NOVOU schopnost (parsování a porovnání číselných tokenů napříč
  přirozeným textem), kterou nemá ŽÁDNÁ jiná část týhle pipeline. `check_
  meaning_preserved` už čísla explicitně kontroluje (LLM vrstva) -
  trvám na tom, že tohle je dostatečné a konzistentní s architekturou;
  úzký deterministický guard by byl dodatečná údržbová zátěž (formátování
  čísel v češtině - "1 000", "1000", "tisíc" - by potřebovalo vlastní
  normalizaci) za nejistý přínos nad tím, co už LLM vrstva dělá.
- **IMPORTANT - automatická verifikace kvality stylu:** trvám na
  stanovisku z kola 4 - mimo explicitní zadání (ochrana proti halucinaci),
  uživatel zůstává posledním soudcem.

## Claude VERDICT

Po aplikaci obou BLOCKING a 4 IMPORTANT + 3 NITS z kola 5 (celkem 2
BLOCKING + 4 IMPORTANT opraveno v tomhle kole, 2 IMPORTANT body zůstávají
vědomě mimo rozsah s prohloubeným zdůvodněním) nenacházím ve vlastním
čtení nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 5: Codex našel 2 nové BLOCKING (chybějící `encoding="utf-8"` -
potvrzeno vlastní zkušeností z týhle session; `rendered_terms=[]` je
skutečná slepá skvrna, ne jen ztráta provenience - kolo 4 rozhodnutí
REVIDOVÁNO) a 4 IMPORTANT (kritik pořád fail-open na neplatný verdikt,
Windows timeout neukončí celý strom procesů, "všechno selhalo" mělo
vnitřně rozporný status) + 3 NITS (zastaralá próza po předchozích
opravách kódu). Vše opraveno. 2 body (deterministická čísla, automatická
kvalita) zůstávají vědomě mimo rozsah - Codex u čísel navrhl užší verzi,
ale i ta by byla nová schopnost bez precedentu ve zbytku pipeline. Design
je teď kompletní - čeká se na kolo 6 Codexu.
