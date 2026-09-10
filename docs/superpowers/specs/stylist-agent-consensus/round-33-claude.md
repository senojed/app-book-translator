# Round 33 — Claude critique

Sedmé review kola-27 dodatku. Codex 2 IMPORTANT + 2 NITS.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - "stderr je JEDINÝ Codexem-řízený text" nepravdivé:**
  číselný guard vloží celý `after_nums` (extrahovaná čísla ze
  STYLIZOVANÉHO textu) do `StylistError` → konzole + `failed.error` i za
  `False`. Prompt injection by přes to mohla exfiltrovat číselný obsah.
  → hodnoty číselných sekvencí jen za `STYLIST_REPORT_REJECTED_TEXT is
  True`, jinak obecná "hodnoty potlačeny" hláška. Komentář o "jediném"
  textu opraven.
- **IMPORTANT - `KeyboardInterrupt` fix (kolo 30) nezaručoval JEDEN
  pravdivý záznam:** interrupt po úspěšném commitu ALE před
  `report.append({polished})` → jen `interrupted` (přestože DB má přijatou
  stylizaci); interrupt po appendu → DVA záznamy → `attempted_count`
  přeteče. → `polished` append HNED po commitu (před `print`) +
  in-loop `except KeyboardInterrupt` dedup podle `idx` (jako kolo-29
  `FatalRunError`).

### NITS - fixed
- próza tvrdila `interrupted` = `stage`+`error`; kód má jen `stage`
  (Ctrl+C nemá smysluplnou hlášku). Sjednoceno na "jen `stage`".
- config komentář "žádný volný text" moc obecný - `run_error`/
  `finalization_error`/`failed.error` v reportu zůstávají (to jsou
  hlášky PROGRAMU, ne Codexův obsah). Upřesněno na `rejected` záznam.

## Claude VERDICT

`CHANGES_NEEDED` - 2 IMPORTANT. Aplikováno. Oba navazují na dřívější
bezpečnostní/robustnostní řešení (stderr gate → i čísla; kolo-30
interrupt → hraniční okna). Čeká se na kolo 34.

## Summary for log

Kolo 33: 2 IMPORTANT + 2 NITS. (1) stderr nebyl jediný Codexem-řízený
text - číselný guard dá `after_nums` do `StylistError` → gate i tady.
(2) kolo-30 `KeyboardInterrupt` fix měl hraniční okna (interrupt po
commitu = jen `interrupted`; po appendu = dva záznamy) → append hned po
commitu + idx-dedup. NITs: `interrupted` prose, config komentář.
Čeká se na kolo 34.
