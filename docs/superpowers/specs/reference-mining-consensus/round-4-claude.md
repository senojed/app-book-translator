# Round 4 — Claude critique

## Claude's own findings

### IMPORTANT

- **Částečný běh (`--limit`) se tváří jako úplný.** Fingerprint potvrzuje shodu
  s draftem, ale nic neříká o tom, že se stupeň 1 pustil jen na část povrchů.
  UI pak nemá jak poznat, že zbytek nebyl ani zkoušen. *Fix:* `reference.json`
  nese `coverage: {attempted: [id], skipped_by_limit: [id]}`; UI u nepokrytých
  položek neukazuje „nic se nenašlo", ale „nezkoušeno".

### NITS

- Sekce „Otevřené otázky" pořád mluví o „kmenovém porovnání `concordance`",
  což po opravě neplatí. Sjednotit s novým kontraktem.

## On Codex's points

### Agreed + fixed

- **Normalizace a hledání si odporují.** Přijímám celé a je to nejzávažnější
  nález kola. `normalize_key()` vždy `casefold()`, takže „case-sensitive hledání
  obecných slov" na normalizovaném textu je nemožné. Ověřeno navíc, že
  `concordance.find_form_occurrences` je pro tenhle účel **nepoužitelné**:

  ```
  form_key("Bílá rada") == form_key("Bída rana")   → True
  find_form_occurrences("Byl to Za-Lord.", "Za-Lord") → []
  ```

  Kmen zkracuje „bílá" i „bída" na `bí`, „rada" i „rana" na `ra`; a tokenizace
  přes `\w+` rozseká `Za-Lord` na pomlčce, takže termín nenajde ani tam, kde
  stojí doslova.

  *Oprava a přiznaná otočka:* rozhodnutí z kola 3 (znovupoužít `concordance`)
  se **ruší**. `concordance` zůstává beze změny pro pipeline - je psaná pro
  hlídání driftu v jedné kapitole, kde falešný poplach jen vyvolá otázku, ne pro
  doložení termínu v milionovém korpusu. `reference.py` dostává vlastní matcher
  se dvěma oddělenými kontrakty (přesné hledání se zachováním velikosti písmen
  pro stupeň 0, prefixové pro stupeň 1) a `normalize_key` slouží **jen
  k identitě, nikdy k hledání**.

- **`build_app` třetí poziční parametr je `on_saved`.** Ověřeno
  (`server.py:108`). *Oprava:* `reference_path` je **keyword-only**:
  `build_app(draft_path, guide_path, on_saved, *, reference_path=None)`.
- **`id` není zaručeně unikátní.** Ověřeno: `scan_book` duplicity ani prázdné
  klíče nekontroluje, dedup je jen v `scan_chunks`. *Oprava:* validace před
  těžbou - prázdný klíč se přeskočí a nahlásí, duplicitní `(section, klíč)` se
  deterministicky sloučí (spojí se aliasy a poznámky) a nahlásí.
- **`write_reference` nepokrývá nálezy stupně 0.** Přijímám, `attempted` byly
  z definice jen položky poslané modelu. *Oprava:* úplný stavový automat pro
  každé aktuální `id`.
- **Chybějící `id` v odpovědi ≠ `cz: null`.** Dobrý postřeh: chybějící položka
  by přepsala dřívější platný nález na `unresolved`. *Oprava:* chybějící `id` →
  selhání položky, převezme se předchozí nález jako `stale`; `unresolved`
  vzniká jen z explicitního `null`.
- **`fresh: false` pořád předvyplňuje.** *Oprava:* při nečerstvém fingerprintu
  se reference k předvyplnění **nepoužije vůbec** - ani `cz`, ani `render`.
- **Prahy `confirmed` - primární tvar vs. sjednocení s aliasy.** *Oprava:* prahy
  se počítají výhradně z `per_form[primární]`; aliasy jsou doplňkový důkaz.
  Doplněn hraniční test (jeden výskyt primárního, mnoho u aliasu → `weak`).
- **UI fallback `c.render || "keep"`.** Ověřeno na `index.html:111`. *Oprava:*
  roletka dostane prázdnou volbu `-- vyber --`, fallback se ruší a testuje se
  serializovaný payload, ne jen vzhled.
- **Taxonomie klientských výjimek a report z uloženého payloadu.** *Oprava:*
  doplněna tabulka výjimek (`APIConnectionError`, `RateLimitError`, 5xx po
  vyčerpání retry) → dávka `failed`; report se generuje z **finálního slitého**
  payloadu, ne z výsledku před sloučením.
- **`load_reference` validuje jen JSON a verzi.** *Oprava:* validace celého
  schématu včetně typů, unikátnosti `id` a povolených sekcí; jakékoli porušení →
  ignoruj s varováním.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex našel 3 blokující a 7 důležitých, vše přijato. Zásadní je zrušení
rozhodnutí z kola 3: `concordance.find_form_occurrences` se pro doložení termínů
použít nedá - ověřeno, že koliduje `Bílá rada` s `Bída rana` a nenajde `Za-Lord`
ani v textu, kde stojí doslova. `reference.py` dostává vlastní matcher se dvěma
kontrakty, `normalize_key` slouží jen k identitě. Dále: `reference_path` musí být
keyword-only (třetí poziční je `on_saved`), `id` z draftu nejsou zaručeně
unikátní, chybějící položka v odpovědi modelu není totéž co explicitní null,
a nečerstvá reference nesmí předvyplňovat vůbec. Claude přidal: částečný běh
přes `--limit` se tváří jako úplný, chybí `coverage`.
