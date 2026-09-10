# Round 31 — Claude critique

Páté review kola-27 dodatku. Codex 2 IMPORTANT + 3 NITS.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `STYLIST_REPORT_REJECTED_TEXT=True` nebezpečný default:**
  Codex má pravdu. `STYLIST_ACCEPT_FS_RISK` = "agent smí číst disk během
  běhu", NE "exfiltrovaný obsah se smí TRVALE uložit do souboru" - a
  `polish-reports/` leží vedle repa, které bývá v synchronizované složce
  (Nextcloud) → teklo by to dál. Plný text = SAMOSTATNÉ rozhodnutí. →
  default `False`. Redukovaný report (`reason_types`) na měření v1 stačí;
  plný text = explicitní opt-in pro konkrétní běh. **POZN: vlastník
  projektu si původně `True` přál - je to teď informovaná volba, ne
  zablokovaná.**
- **IMPORTANT - dedup v `_rejection_reasons` moc široký:** kolo-29/30
  fix přeskakoval celý `(type, term_id)`. Nový chybný povrch B (nový
  klíč) by zamaskoval, že SOUČASNĚ narostl výskyt povrchu A → report
  ztratí jednu z příčin. → dedup na úrovni `_finding_key`
  (`(type, term_id, actual)`), per-povrch. Test se dvěma různými `actual`
  téhož termínu.

### NITS - fixed
- úvodní shrnutí "zahodí se" → "nepřijme se; zamítnutý výstup do reportu
  jen za opt-inem".
- próza "vnější `KeyboardInterrupt` handler stačí sám o sobě" - kolo 30
  to vyvrátilo pro report. Přeformulováno (stav běhu ANO, report NE).
- nadpis "Kolo 27-29" → "Kolo 27+".

## Claude VERDICT

`CHANGES_NEEDED` - 2 IMPORTANT. Aplikováno. Konvergence: 5→6→2→1→2 (kolo
31 přineslo jeden nový bezpečnostní pohled + jeden navazující na
kolo-29/30 dedup). Čeká se na kolo 32.

## Summary for log

Kolo 31: 2 IMPORTANT + 3 NITS. (1) `STYLIST_REPORT_REJECTED_TEXT`
defaultně `True` byl nebezpečný - opt-in ke čtení disku ≠ souhlas s
trvalým uložením exfiltrovaného obsahu do synchronizované složky →
default `False`, plný text samostatný opt-in. (2) kolo-29/30 dedup
skákal celý termín místo konkrétního povrchu → nový chybný povrch B by
zamaskoval nárůst povrchu A → dedup na `_finding_key`. NITs: "zahodí se",
próza o KeyboardInterrupt handleru, nadpis. Čeká se na kolo 32.
