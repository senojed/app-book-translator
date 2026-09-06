# Round 6 — Claude critique

## Claude's own findings

### IMPORTANT
- **Duplicitní popis drift checku** (dva odstavce, jeden starý "report do
  drift_reports, vypíše počet", jeden nový "→ questions"). → Sjednoceno,
  starý odstavec nahrazen.
- **`review` reseed glosáře vs izolace `review_ui`.** Reseed sahá na
  `glossary` tabulku, ale `review_ui` má sahat jen na `guide.*.json`. →
  Reseed přesunut do CLI příkazu `review` (po skončení serveru), ne do UI.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `variants` = "pozorované" i "akceptované" současně** (regrese
  z kola 5) — opraveno: `variants` zrušeno. Glosář má `cz` (kanonický) +
  `accepted_alt` (JEN člověkem schválené přes `answer`). Pozorované tvary žijí
  výhradně v `term_mentions`. `check_chapter` inconsistency = `cz_form` ∉
  ({cz} ∪ accepted_alt ∪ skloňování). Nic se do glosáře nepřidává automaticky.
- **BLOCKING: "commit kapitoly je jedna transakce" ale glosář je JSON mimo
  SQLite** — opraveno: glosář přesunut do SQLite tabulky `glossary`. Zápis
  glosáře + term_mentions + chapters + questions při jedné kapitole = jedna
  transakce. `guide.json` zůstává soubor (edituje se přes UI, za `run` se nemění).
- **IMPORTANT: `review` mimo run lock** — opraveno: `review` drží lock po dobu
  serveru.
- **IMPORTANT: `kind=relationship` / `kind=other` nedefinované** — opraveno:
  relationship → `guide.relationships`, scope_key="a|b", affected = kapitoly
  s oběma jmény v EN; other → `guide.rules` (jako style).
- **IMPORTANT: drift jen reportuje, žádná akce** — opraveno: `check_drift`
  vrací `DriftFinding[]`, pipeline z každého udělá `question` (upsert), odpověď
  jde běžnými requeue pravidly. `drift_reports` zůstává jen pro audit.
- **IMPORTANT: agregace metadat po scénách + po revizi nedefinovaná** —
  opraveno: krok 2 agreguje per-scéna (new_terms union, questions concat,
  rendered_terms union); revizní celokapitolový výstup NAHRADÍ agregát
  (new_terms se kumulují).
- **IMPORTANT: questions bez dedup/supersede** — opraveno:
  `UNIQUE(chapter_idx, kind, scope_key, severity)` + upsert; rerun kapitoly
  maže nezodpovězené a zakládá znovu (krok 0).
- **NIT: check_chapter signatura nekonzistentní** — sjednoceno na
  `(en_text, cz_text, glossary, rendered_terms)`.
- **NIT: "pro každý termín z glosáře" drahé** — opraveno: jen termíny s EN
  podobou ve scéně + termíny v `rendered_terms`.
- **NIT: model/ceny validace** — ponecháno (už v sekci Modely).

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 2 vlastní IMPORTANT (duplicita, izolace), Codexovy 2 BLOCKING
(jeden regrese z kola 5) + 5 IMPORTANT reálné. Přesun glosáře do SQLite je
větší změna, chce potvrzovací kolo.

## Summary for log
Kolo 6: Codex 2 BLOCKING (variants observed/accepted konflikt - regrese kola 5;
glosář JSON mimo SQLite transakci) + 5 IMPORTANT + 3 NIT. Claude 2 vlastní
IMPORTANT (duplicitní drift popis, review_ui izolace). Velká změna: **glosář
přesunut do SQLite** (transakční konzistence s commitem kapitoly). `variants`
zrušeno → `cz` + `accepted_alt` (jen člověk). Drift → questions (actionable).
Metadata agregace po scénách/revizi definována. questions UNIQUE klíč +
upsert. relationship/other kind chování. review drží lock. Sporné: nic.