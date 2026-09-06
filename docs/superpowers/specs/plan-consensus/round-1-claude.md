# Round 1 — Claude critique

## Claude's own findings

### BLOCKING
- **Revizní režim translatora bez EN originálu** (nezávisle shodné s Codexem):
  run pseudokód i sekce Translator dávaly revizoru jen `CZ + nálezy`. Bez EN
  neopraví věrnost. → Opraveno: revizní režim = EN kapitola + CZ + findings +
  návod + glosář.

### IMPORTANT
- **Concordance issues chybí ve stavovém automatu a v revizní smyčce.**
  Pseudokód step 5 spouštěl revizi na "concordance problém", ale nebylo řečeno
  co s tím revizor dělá ani jaký je koncový stav. → Opraveno: concordance nálezy
  (`leak` / `inconsistency`) sjednoceny do tvaru findings, revizor je dostane;
  `leak`/`approved inconsistency` po MAX kolech → status `flagged`.
- **`needs_human` vs dávkový `run`.** Nebylo řečeno, jestli blokující otázka
  zastaví celý `run`. → Opraveno: `run` needs_human/error kapitoly přeskočí,
  reportuje na konci.
- **`export` a nečisté kapitoly.** Původně `export` = jen `status='done'`;
  chybějící kapitola 17 v knize je vada. → Opraveno: nová sekce Export -
  flagged s markerem, needs_human/error jako `[!! CHYBÍ KAPITOLA]` + varování,
  `--only-done` opt-out.
- **UTF-8 stdout.** Pokus 1 padal `UnicodeEncodeError` na české konzoli Windows.
  Spec to neřešil. → Opraveno: nová sekce Prostředí, `main.py` vynutí UTF-8.
- **Re-scan vs existující `guide.json`.** Nedefinováno. → Opraveno: `scan` píše
  jen draft, `review` GET slévá draft+final s předností člověka.

### NITS
- "škáluje na 350 kapitol" vs "~350 stran" → "desítky kapitol (typicky 40-60)".
- Fragment věta v Kontextu → opraveno.
- Pořadí stavby: scout přesunut před translatora, review UI explicitně jako
  "minimální schvalovací cesta stačí k prvnímu run".

## On Codex's points

### Agreed + fixed
- **BLOCKING: revizní translator bez EN** — viz výše, opraveno.
- **BLOCKING: useknutý scout = jen varování** — opraveno: scout truncated =
  fatal běhu, ne pokračovat s částečným JSON. Přidán `--chunked` fallback
  s deterministickým `merge_scout_facts()`.
- **IMPORTANT: scout 1 volání = zároveň plán i otevřená otázka** — opraveno:
  1 volání je default, `--chunked` navržený fallback; otevřená otázka
  přeformulována na "jen volba defaultu".
- **IMPORTANT: Sonnet 5 sampling parametry** — opraveno: provider vrstva
  explicitně neposílá temperature/top_p/top_k; `count_tokens` před pilotem.
- **IMPORTANT: drift check nemá data** — opraveno: nová tabulka `term_mentions`
  plněná z translatorových `used_terms`; `check_drift` čte odtud, ne z glosáře.
- **IMPORTANT: new_terms bez validace do závazného glosáře** — opraveno:
  `status` na glosáři (seeded/approved/candidate); candidate se do promptu dává
  slabě, do tvrdé concordance kontroly jen seeded+approved; `answer` povyšuje.
- **IMPORTANT: schema otázky bez guess/scope** — opraveno: `questions` rozšířeno
  o `kind`, `scope_key`, `guess_answer`; requeue pravidla přesně definována.
- **IMPORTANT: cost guard měkký, usage se ztratí při pádu** — opraveno: tabulka
  `llm_calls`, zápis po každém volání; guard platí i pro `scan`; worst-case
  odhad zbytku včetně revizních kol.
- **IMPORTANT: fatal vs per-kapitola chyby** — opraveno: sekce Chyby přepsána,
  třída "Fatal běhu" (klíč, model, 400, spend) ukončí příkaz bez dotčení kapitol;
  "kanárek" = první volání.
- **NIT: fragment věta, "350 kapitol", pořadí stavby** — vše opraveno.

### Disagreed
- Žádný bod Codexu jsem nezamítl. Bod o "token counting před pilotem" jsem
  zúžil na řádek v provider vrstvě (není to blocker, je to připomínka).

## Claude VERDICT
CHANGES_NEEDED — v tomto kole jsem sám našel 1 BLOCKING + 5 IMPORTANT; všechny
opraveny, ale rozsah změn je velký a chce druhé kolo revize.

## Summary for log
Kolo 1: Codex našel 2 BLOCKING (revizor bez EN, scout truncation) + 8 IMPORTANT.
Claude nezávisle našel stejný BLOCKING + 5 dalších IMPORTANT (concordance ve
stavovém automatu, needs_human v dávce, export nečistých kapitol, UTF-8,
re-scan/guide). Všechny body přijaty a zapracovány do specu: revizní režim
dostává EN, glosář má candidate/approved status, nová tabulka `term_mentions`
pro drift, `llm_calls` pro usage, přepsaná klasifikace chyb (fatal vs
recoverable), rozšířené `questions` schema, sekce Export a Prostředí. Nic
sporného. Druhé kolo ověří konzistenci velkého přepisu.