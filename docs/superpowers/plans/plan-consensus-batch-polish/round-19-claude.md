# Round 19 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **BLOCKING - `assign_ids` dává KAŽDÉ analýze nové náhodné `id` (Task
  2) - "Znovu polish" tak vrací nálezy s ÚPLNĚ JINÝMI `id`, i pro
  sémanticky "stejný" problém jako dřív vyřešený nález. `_merge_
  findings_by_id`'s "nikdy nic nemaž" politika pak OBĚ kopie drží
  navždy - duplicita v seznamu/reportu, osiřelé "vyřešeno" na starém
  `id`.** Ověřeno logicky (žádný spolehlivý způsob "srovnat podle
  obsahu" napříč nezávislými critic/LLM voláními - LLM output není
  deterministický). Zvolil jsem DRUHOU Codexovu navrženou alternativu
  ("reconcile fresh findings to existing IDs" ale ve zjednodušené
  formě) místo fingerprint+ordinal (ten by na nedeterministickém critic
  textu stejně nefungoval spolehlivě) - `_merge_findings_by_id` dostala
  nový `drop_stale_non_markers` parametr: `True` (jen na Task 9's
  TEXTOVĚ MĚNÍCÍ větvi, ne lehké) zahodí staré NON-marker nálezy, co
  nejsou v `incoming` (byly analyzovány pro TEXT, co tímhle zápisem
  přestává existovat) - markery se ZACHOVÁVAJÍ VŽDY. Bezpečné jen tady,
  protože existující CAS kontrola (`translated_text != cz_before` →
  409) zaručuje, že žádný JINÝ text-měnící zápis nemohl mezitím
  proběhnout souběžně (na rozdíl od lehké větve, kde "karta B přidala
  nález" race z kola 3/4 zůstává chráněný nezměněnou politikou). Nový
  integrační test (regenerate → save) ověřuje: starý vyřešený nález
  NEPŘEŽIJE, nový je nevyřešený, marker se zachová.

- **IMPORTANT - `btn-save`'s (a `toggleResolved`'s) `catch` léčil
  síťovou chybu jako "neuloženo", ale server mohl zápis dokončit PŘED
  tím, než se odpověď ztratila cestou zpátky - retry by pak narazil na
  409 (CAS), uživatel by nevěděl proč.** Ověřeno logicky - stejná třída
  problému jako `revertChapter` (kolo 15), co UŽ tenhle vzor řeší.
  Aplikováno STEJNÉ řešení na `btn-save` I `toggleResolved` (Codex
  explicitně žádal obojí) - `catch` teď přizná nejistotu (`alert`) a
  vynutí `window.location.reload()`, místo tichého "zkus to znovu"/
  vrácení checkboxu do (možná ŠPATNÉHO) předchozího stavu.

## Claude VERDICT

CHANGES_NEEDED (souhlas s oběma, plná implementace)

## Summary for log

Kolo 19 - první opravdu STRUKTURÁLNÍ nález od kola 10-18 série (ne jen
lock-timing vrstva) - odhaluje mezeru v CENTRÁLNÍM mechanismu celého
redesignu (resolved-checkbox perzistence napříč regenerate cykly, co
byl PŮVODNĚ uživatelův vlastní návrh místo auto-recompute). Fix je
cílený (jen text-changing větev, ne lehká) s jasným zdůvodněním PROČ je
bezpečný jen tam (existující CAS). Druhý bod rozšiřuje kolo-15 vzor
(ambiguous-write handling) na zbylá dvě místa, co ho ještě neměla.
