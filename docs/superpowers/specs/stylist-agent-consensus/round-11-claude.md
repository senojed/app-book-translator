# Round 11 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Po aplikaci Codexových bodů jsem doplnil samostatný kolo-10 bullet do
"Rozhodnutí" sekce (kolo 10 dřív žádný svůj souhrnný bullet nedostalo,
jen inline opravy - stejná mezera, co Codex označil u nadpisu "kol 1-9").
ast.parse sweep přes všech 8 python bloků čistý.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - lifecycle snapshotu pořád ne PLNĚ chráněný:** ověřil jsem
  přímo - `shutil.copy2(db, snapshot_path)` (kolo 10 verze) ležel PŘED
  `try:`, takže selhání SAMOTNÉHO kopírování (plný disk, práva) by
  nechalo částečný `.pre-polish-snapshot` bez úklidu. Přepracováno -
  `backup_state` se sestaví (s HOTOVOU cestou) PŘED `try`, ale `shutil.
  copy2` samotné je teď AŽ UVNITŘ - `finally` tak pokryje i tenhle
  případ.
- **IMPORTANT - procentní guard ignoruje úzkou nezalomitelnou mezeru
  U+202F:** ověřil jsem - kolo 10 přidalo jen obyčejnou mezeru a NBSP
  (U+00A0), ne úzkou nezalomitelnou (U+202F) - oficiální typografická
  konvence pro "číslo + %". Přidáno do regexu i normalizace v
  `_number_multiset`.
- **IMPORTANT - obnova DB ze zálohy není atomická:** ověřil jsem -
  dokumentovaný postup `shutil.copy2(backup, db)` přímo na AKTIVNÍ cestu
  má stejné riziko částečného zápisu jako dřívější zálohování (co jsme
  právě opravili), jen by teď poškodil přímo `db`. Přepsáno na
  kopírování do dočasného souboru + `PRAGMA integrity_check` +
  `os.replace`.
- **IMPORTANT - chybí regresní testy na validaci severity/type:** ověřil
  jsem - kolo 9 přidalo fail-closed validaci v `critic.review()`, ale
  test scénáře v dokumentu ji neověřovaly. Přidány 4 scénáře (chybějící
  `severity`, `0` jako neplatná hodnota - přesně ten Python-falsy gap, co
  motivoval opravu, neplatný `type`, a persistence přes retry smyčku).
- **NIT - nadpis "Rozhodnutí" sekce zůstal na "kol 1-9":** ověřil jsem -
  kolo 10 dokument měnilo (5 IMPORTANT oprav), ale nedostalo vlastní
  souhrnný bullet ani se nepromítlo do nadpisu. Přidán kolo-10 bullet a
  nadpis aktualizován na "1-11" (rovnou včetně tohohle kola).
- **NIT - baseline próza pořád primárně odkazuje na kolo-3 verzi:**
  ověřil jsem - bullet zmiňoval jen "z doby, kdy kapitola dostala done"
  bez upřesnění, že kolo 4 zdroj baseline změnilo na čerstvý přepočet.
  Doplněno.

### Disagreed
- **NIT - zastaralé tvrzení o nepozorované změně rejstříku (řádky
  445-450):** udělal jsem cílený grep na VŠECHNY 4 výskyty fráze "nemá
  signál" v dokumentu (řádky 473-474, 618, 1021, a jeden v Rozhodnutí
  sekci) - tři z nich mluví jen o KRITIKOVI (pravdivé, nezměněné), jeden
  (Rozhodnutí bullet u `guide_block`) DŘÍV tvrdil totéž i o `check_
  meaning_preserved`, ale ten jsem opravil už v kole 10. Žádný ze čtyř
  aktuálních výskytů teď nedělá tu chybnou generalizaci. Beru tohle jako
  odkaz na stav PŘED kolo-10 opravou (Codexovo číslo řádku "445-450"
  navíc neodpovídá žádnému z těch čtyř míst v aktuální verzi).

## Claude VERDICT

Po aplikaci 4 IMPORTANT + 2 NITS z kola 11 (1 NIT rozporován po přímém
ověření všech výskytů - už opraveno v kole 10) nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 11: Codex našel 4 IMPORTANT (lifecycle snapshotu pořád ne plně
chráněný `try/finally` - samotný `shutil.copy2` zůstal venku; procentní
guard nezachytává úzkou nezalomitelnou mezeru U+202F; obnova DB ze
zálohy není atomická; chybí regresní testy na kolo-9 validaci
severity/type) + 3 NITS (baseline próza, zastaralé tvrzení o rejstříku -
už opraveno v kole 10, nadpis Rozhodnutí sekce). Přijato a opraveno vše
kromě jednoho NITu (zastaralé tvrzení o rejstříku), kde přímé ověření
všech 4 výskytů fráze v dokumentu potvrdilo, že už je opravené z kola 10.
Design je teď kompletní - čeká se na kolo 12 Codexu.
