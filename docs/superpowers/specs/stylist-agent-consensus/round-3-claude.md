# Round 3 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní - Codex round 3 pokryl to podstatné)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
(žádné vlastní)

## On Codex's points

### Agreed + fixed
- **BLOCKING - `main.py` chybí importy `concordance`/`glossary`:** ověřeno
  přímým čtením `main.py` - dnes tam skutečně NEJSOU na modulové úrovni
  (`_cmd_review` je importuje LOKÁLNĚ, jen pro sebe). `_polish_one_chapter`
  je ale potřebuje na KAŽDÉ volání, přidáno na úroveň modulu spolu s
  `hashlib`.
- **BLOCKING - `verdict`/`findings` nesoulad v `critic.review()`:** ověřeno
  přímým čtením `critic.py` - `data.get("verdict")` se tam skutečně nikde
  nečte. Tohle je PŘEDEXISTUJÍCÍ mezera v jádru pipeline (postihuje `run`
  stejně jako `polish`), ale `polish` na `critic.review()` staví svou
  hlavní záruku, takže se sem promítá napřímo. Oprava PATŘÍ do
  `critic.py` (prospívá oběma příkazům), zdokumentováno jako samostatná
  sekce "Oprava mimo nový modul" - ne skrytá uvnitř `stylist.py`.
- **IMPORTANT - odmítání i pre-existujících minor nálezů by kapitolu
  navždy zablokovalo:** `_polish_rejected` přepsán na dvouparametrovou
  funkci (`baseline_findings`, `after_findings`) - konkordanční nálezy se
  srovnávají jako množina `(type, term_id)` PŘED/PO, kritikovy `revise`
  nálezy odmítají vždy (baseline pro `done` kapitolu má nula takových),
  kritikovy `minor` nálezy se ignorují (doména stylisty).
- **IMPORTANT - `except Exception` per kapitola je moc široký (DB/schema
  chyby vs. programátorská chyba vs. per-kapitolové selhání):** ověřil
  jsem `_cmd_run`'s existující kód - dělá PŘESNĚ totéž (`except Exception`
  kolem `process_chapter`, s explicitním `except FatalRunError: raise`
  PŘED tím). Broad-except-ale-reraise-FatalRunError je tedy zavedená
  konvence týhle kódové základny, ne nová díra, kterou by zaváděl `polish`.
  Přesto souhlasím s doplňkovou opravou: preflight (executable dostupnost)
  + varovná hláška při "všechno selhalo" dělají symptom ("run proběhl
  ok, ale nic se nestylizovalo") viditelný, aniž by bylo nutné měnit
  zavedenou per-kapitolovou konvenci na něco nekonzistentního se zbytkem
  kódu.
- **IMPORTANT - rollback/audit (opakovaný bod z kola 1-2):** stále
  částečně nesouhlasím s rozsahem (viz "Disagreed" níže), ale beru vážně
  konkrétní techickou výtku "8 hex znaků SHA-1 má jen 32bitovou kolizní
  odolnost" - to je fér technický detail, i když nemění mé stanovisko
  o rozsahu (viz níže).
- **IMPORTANT - `styled == cz` platí dvě kontroly zbytečně a zamkne
  kapitolu markerem, i když se nic nestylizovalo:** přidána explicitní
  `"unchanged"` větev v `_polish_one_chapter`, PŘED voláním kritika/kontroly
  významu, BEZ zápisu markeru.
- **IMPORTANT - chybí preflight, systémová chyba se maskuje jako N
  per-kapitolových selhání:** přidán `stylist._resolve_codex_cmd(["codex"])`
  na začátku `_cmd_polish` (levné, bez skutečného volání Codexu), plus
  varovná hláška při "všechno selhalo".
- **IMPORTANT - vytvoření/zápis vstupního souboru mimo try/finally:**
  `polish()` teď používá `tempfile.TemporaryDirectory()` jako context
  manager kolem CELÉHO životního cyklu (vznik adresáře, zápis vstupu,
  spuštění, čtení výstupu) - automatický úklid i při selhání zápisu.
- **NIT - `isinstance(e, KeyboardInterrupt)` je mrtvý kód:** ověřil jsem
  si Python sémantiku (`KeyboardInterrupt` dědí přímo z `BaseException`,
  ne `Exception`) - potvrzeno, `except Exception` by ho nikdy nezachytil.
  Zjednodušeno na `except FatalRunError: raise` PŘED obecným `except Exception`
  (přesně vzor z `_cmd_run`).
- **NIT - model se testuje přes `.strip()`, ale posílá se nenormalizovaný:**
  `model = (config.CODEX_MODEL or "").strip()` se počítá JEDNOU na
  začátku `_cmd_polish`, stejná proměnná se posílá do `_polish_one_chapter`,
  `stylist.polish`, `_stylist_marker`.

### Agreed but already addressed
(žádné - kolo 3 nálezy jsou nové)

### Disagreed
- **IMPORTANT - "dřívější odmítnutý požadavek na rollback zůstává platný"
  (plná historie/snapshot):** Trvám na stanovisku z kola 1 s upřesněním.
  Codex má pravdu, že 8 hex SHA-1 znaků neumí NIC obnovit (souhlasím - to
  ostatně marker nikdy netvrdil, jen "dohledatelnost", ne "obnovitelnost").
  Ale "guardraily jsou pravděpodobnostní, tedy nevratné přepsání je
  nepřiměřené" - tenhle argument by platil STEJNĚ pro `translator.revise_chapter`
  v hlavní pipeline, která TAKY nevratně přepisuje `translated_text` bez
  jakékoli historie, na základě STEJNĚ pravděpodobnostních (LLM) kontrol.
  Žádat plnou verzovanou historii JEN pro `polish` by byl nekonzistentní
  precedens vůči zbytku kódové základny, ne oprava skutečné mezery
  zavedené tímhle plánem. Kdyby šlo o řešení tohohle problému NAPŘÍČ celou
  aplikací (verzování `translated_text` obecně), je to samostatný,
  širší úkol - ne něco, co má tenhle spec propašovat jen pro jednu novou
  funkci.

## Claude VERDICT

Po aplikaci obou BLOCKING a všech IMPORTANT/NITS z kola 3 nenacházím ve
vlastním nezávislém čtení nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 3: Codex našel 2 nové BLOCKING (chybějící importy v `main.py` - reálný
`NameError`; `verdict`/`findings` nesoulad v `critic.review()` -
předexistující mezera v jádru pipeline, kterou `polish` zdědil) a 6
IMPORTANT + 2 NITS (baseline srovnání místo absolutního odmítání, širší
except-scope otázka - ověřeno jako zavedená konvence `_cmd_run`, detekce
`styled==cz`, preflight, `TemporaryDirectory`, normalizace modelu, mrtvý
`isinstance` kód). Vše opraveno kromě jednoho bodu (plná historie/rollback),
kde trvám na kolo-1 stanovisku s doplněným zdůvodněním - je to precedens
nekonzistentní se zbytkem kódové základny, ne díra zavedená tímhle plánem.
Design je teď kompletní - čeká se na kolo 4 Codexu.
