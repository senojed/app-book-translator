# Round 20 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní nad rámec Codexova)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Codex opravdu tentokrát našel SKUTEČNĚ stale `shutil.copy2` komentář (v
`finally` bloku "VČETNĚ selhání samotného `shutil.copy2`") - moje
"5 kol falešných poplachů" hodnocení bylo předčasné. Opraveno + i jeden
navazující ("těsně před `shutil.copy2`" v `_cmd_polish` komentáři).

## On Codex's points

### Agreed + fixed
- **BLOCKING - opt-in gate jen v CLI obálce:** naprosto správně - `polish()`
  je veřejná funkce, přímé volání gate obešlo, moje tvrzení "polish běží
  JEN za opt-inem" bylo nepravdivé. Gate přesunut PŘÍMO do
  `stylist.polish()` (raise `StylistError` bez `STYLIST_ACCEPT_FS_RISK
  is True`), `_cmd_polish` si nechává vlastní časnou hlášku pro hezčí
  UX. Přidána autouse fixture do test modulu + cílený test přímého
  volání s vypnutým opt-inem.
- **IMPORTANT - `Counter`/množina míjí skutečný regresní scénář:** Codex
  má pravdu a MOJE kolo-18 reverze byla založená na neúplné analýze -
  `check_chapter()` dedup ZNAMENÁ, že "1 leak" i "2 leaky" téhož povrchu
  dají STEJNÝ jediný klíč, takže ani množina ani Counter-nad-findings to
  nezachytí. Přidána DRUHÁ kontrola v `_polish_rejected`: počítá výskyt
  `actual` povrchu v `cz_before` vs. `cz_after` u pre-existujících
  leak/inconsistency nálezů. `_polish_rejected` teď bere i texty.
- **IMPORTANT - argv test je tautologický:** správně - kolo 19 jsem
  přehnal DRY. `_codex_argv` helper je dobrý pro PRODUKCI (jedno místo),
  ale test bezpečnostního kontraktu musí mít NEZÁVISLÝ hardcoded
  oracle. Vrácen ručně přepsaný `assert tail == [...]`.
- **IMPORTANT - `rendered_terms` bez kontroly `source`:** ověřil jsem -
  `concordance._term_mentions` označí VŠECHNO z `rendered_terms` jako
  "rendered", takže forwardovaná `detected` mention by se uložila s
  falešnou proveniencí. Filtr `source == "rendered"` přidán (`detected`
  concordance dohledá sama). `chapter_mentions` getter už `source`
  vrací (SELECT ho má).
- **NIT - próza "gate před kontrolou modelu" vs. kód:** `_cmd_polish`
  přeuspořádán - FS-risk check je teď SKUTEČNĚ první (před `CODEX_MODEL`).
- **NIT - stale `shutil.copy2`:** opraveno (viz vlastní findings).
- **NIT - canary nepoužívá rozřešený příkaz:** checklist upřesněn na
  `_codex_argv(_resolve_codex_cmd(["codex"]), ...)`.
- **NIT - "`-C` skutečně izoluje":** upřesněno - izoluje pracovní
  adresář + projektový kontext, NE filesystem.

## Claude VERDICT

Po aplikaci 1 BLOCKING + 3 IMPORTANT + 4 NITS z kola 20 nenacházím nic
dalšího. Kolo 20 odhalilo reálnou díru v mém kolo-18/19 uvažování
(Counter reverze + gate jen v CLI) - obojí opraveno.

`CONSENSUS`

## Summary for log

Kolo 20: Codex našel 1 BLOCKING + 3 IMPORTANT + 4 NITS. Dva nálezy
odhalily chyby v mém dřívějším uvažování: (1) kolo-19 opt-in gate byl
jen v CLI obálce, přímé volání `stylist.polish()` ho obešlo - přesunut
PŘÍMO do `polish()`; (2) kolo-18 reverze `Counter` → množina byla
založená na neúplné analýze - `check_chapter()` dedup znamená, že ani
množina ani Counter-nad-findings nezachytí "1 leak → 2 leaky téhož
povrchu v textu" - přidána druhá kontrola počítající výskyt povrchu v
`cz_before`/`cz_after`. Dál: argv test odtautologizován (kolo 19 přehnal
DRY), `rendered_terms` filtruje `source == "rendered"` (jinak falešná
provenience). Čeká se na kolo 21 Codexu.
