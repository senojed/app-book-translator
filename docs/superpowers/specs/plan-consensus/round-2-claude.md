# Round 2 — Claude critique

## Claude's own findings

### IMPORTANT
- **`notes` vs `critic_notes` nekonzistence** (zavedeno mým round-1 přejmenováním):
  schema mělo `notes`, pseudokód `critic_notes`. → Sjednoceno na `notes`.
- **`scope_key` pro `style` otázky nedefinovaný.** Style pravidla nemají přirozený
  klíč. → `scope_key` je `null` u style/other; requeue u style jede přes
  "všechny done/flagged od kapitoly vzniku otázky" (už bylo, teď explicitní).

### NITS
- Přidán `kind: relationship` (nová dvojice tyká/vyká zjištěná za běhu).

## On Codex's points

### Agreed + fixed
- **BLOCKING: `leak` koliduje s `keep → cz==term_en`** — opraveno: `leak` se
  hlásí jen pro termíny s `cz != term_en` (mají se překládat). Pro `keep`
  položky je EN podoba správná, `leak` se nehlásí.
- **BLOCKING: klient zapisující do `llm_calls` porušuje hranice modulů** —
  opraveno: `AnthropicClient` zůstává čistý; pipeline ho obalí do
  `LoggedLLMClient(inner, run_id, agent, state)`, ten loguje. Hranice zachovány.
- **BLOCKING: `count_tokens` musí být volatelný před `complete()`** — opraveno:
  přidán jako samostatná metoda `LLMClient.count_tokens()`; cost guard běží
  v pipeline PŘED `complete()`.
- **BLOCKING: translator question output nemá `kind`/`scope_key`/`guess_answer`** —
  opraveno: metadata otázky rozšířena na plný tvar; blocking otázky mají
  `guess_answer: null`.
- **IMPORTANT: `error` - run přeskočí vs automat "auto retry"** — opraveno
  (rozpor zavedený mnou v kole 1): běžný `run` bere `pending` + `error`
  (retry); `needs_human` + `flagged` přeskakuje.
- **IMPORTANT: `needs_human` + answer==guess → jak do `done`?** — opraveno:
  blocking otázky nemají `guess_answer`, po odpovědi kapitola VŽDY → `pending`.
  Podmínka answer==guess platí jen pro `guess` otázky.
- **IMPORTANT: `must_decide` volné stringy bez cíle odpovědi** — opraveno:
  strukturováno `{kind, scope_key, question, default}`.
- **IMPORTANT: POST /api/guide reseed může smazat approved/candidate** —
  opraveno: reseeduje jen `seeded`; approved/candidate zůstávají; konflikt →
  approved vyhrává.
- **IMPORTANT: `term_mentions` se nemažou při requeue → zastaralý drift** —
  opraveno: `DELETE FROM term_mentions WHERE chapter_idx=?` před zápisem nových
  (krok 6 pseudokódu).
- **IMPORTANT: `llm_calls` schema chudé** — opraveno: přidáno `provider`,
  `estimated_cost_usd`, `truncated`, `status`; sazby v config.
- **IMPORTANT: critic truncation "parse part" rizikové** — opraveno: 1× retry
  s vyšším max_tokens, pak kapitola `flagged` (ne tichý pass).

### Agreed but already addressed
- **NIT: model claims → config ne logika** — už z kola 1; teď v provider sekci
  explicitní věta "držet v config.py, ne v logice".

### Disagreed
- Nic. NIT o `export --only-done` přijat (přidán výpis vynechaných).

## Claude VERDICT
CHANGES_NEEDED — sám jsem našel 2 IMPORTANT (obě mnou zavedené v kole 1),
opraveno. Codexových 4 BLOCKING bylo reálných (většina = díry po velkém
přepisu v kole 1). Chce potvrzovací kolo.

## Summary for log
Kolo 2: Codex našel 4 BLOCKING + 8 IMPORTANT, převážně díry zavedené velkým
přepisem v kole 1 (interfacy nedotažené). Claude nezávisle 2 IMPORTANT (taky
vlastní kolo-1 chyby). Vše přijato: LLMClient dostal `count_tokens()` metodu,
logging přesunut do `LoggedLLMClient` wrapperu (hranice modulů), translator
question metadata mají plný tvar, `leak` se nehlásí pro keep termíny, `error`
retry vs `needs_human` skip rozpor vyřešen, blocking otázka vždy requeue,
`must_decide` strukturované, reseed glosáře jen `seeded`, `term_mentions` mazání
při retranslation, `llm_calls` bohatší, critic truncation retry+flagged.
Sporné: nic.