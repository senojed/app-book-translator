# Round 29 — Claude critique

Třetí review kola-27 dodatku. Codex 2 IMPORTANT + 3 NITS - klesá
(kolo 27: 5, kolo 28: 6, kolo 29: 2). Vše platné.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `FatalRunError` PŘED commitem bez záznamu kapitoly:**
  kolo-28 fix přidal `fatal` záznam jen v commit-větvi
  `_polish_one_chapter`. Ale `FatalRunError` z `pipeline._run_critic`
  (cost guard) padne DŘÍV → propadne bez záznamu → `attempted_count`
  kapitolu počítá jako nezpracovanou. → `_cmd_polish`'s
  `except FatalRunError as fe` teď záznam doplní (`stage=="pre-commit"`),
  s dedup proti commit-větvi.
- **IMPORTANT - `STYLIST_REPORT_REJECTED_TEXT=False` netěsní přes
  STDERR:** Codex může vložit secret do stderr → `stylist.polish` ho dá
  do `StylistError` (`stderr[:500]`) → konzole + `failed.error` v
  reportu. stderr je JEDINÝ Codexem-řízený text v chybové cestě
  `polish()`. → potlačeno U ZDROJE: `polish()` u nenulového exit kódu
  připojí raw stderr jen když `STYLIST_REPORT_REJECTED_TEXT` je `True`.

### NITS - fixed
- stale `status="ok"` u preflight-bulletu (ř. ~2742) - přeformulováno na
  "dnes by skončil `fatal`, ale drahou cestou".
- "DEDUPLIKOVANÝ SEZNAM" v kolo-27 sekci nepřesné - dedup je jen cílený
  na překryv dvou konkordančních větví, kritik/meaning-check se
  nededupují. Upřesněno.
- test scénář prázdného reportu tvrdil "první `_polish_one_chapter` volání
  hodí výjimku mimo smyčku" - nemůže, obecná výjimka ve smyčce = `failed`.
  Opraveno na `_client_factory` selhání.

## Claude VERDICT

`CHANGES_NEEDED` - 2 IMPORTANT, aplikováno. Konvergence pokračuje
(5→6→2). Čeká se na kolo 30.

## Summary for log

Kolo 29: 2 IMPORTANT + 3 NITS (klesá z 6). (1) `FatalRunError` z kritika/
cost guardu se přehodil bez `fatal` záznamu kapitoly → doplněno v
`_cmd_polish` (`stage=="pre-commit"`); (2) `STYLIST_REPORT_REJECTED_
TEXT=False` netěsnilo přes Codex stderr v `StylistError` → potlačeno u
zdroje v `polish()`. NITs: stale `status="ok"`, nepřesné "deduplikovaný
seznam", chybný cíl test scénáře. Čeká se na kolo 30.
