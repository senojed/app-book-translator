# Round 21 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **BLOCKING - lehká větev (Task 9, `text == cz_before`) NEPŘEDÁVALA
  `known_ids` vůbec - "Znovu polish" → kandidát NEPŘIJAT (text zůstal
  původní) → uložit i tak má STEJNOU duplicitní chybu jako kolo 19/20,
  jen na lehké větvi.** Ověřeno - potvrzeno, `_merge_findings_by_id`
  volání v lehké větvi nemělo `known_ids` kwarg vůbec. Namísto
  Codexova navrženého "samostatného příznaku 'z regenerace'" jsem
  zvolil JEDNODUŠŠÍ řešení - `known_ids` (prázdná množina = bezpečný
  no-op, identické `None` chování) se teď posílá VŽDY, do OBOU větví
  jednotně. Ověřeno, že tohle NEREGRESUJE normální toggle-only save bez
  regenerace (typický `incoming` obsahuje všechna `known_ids`, nic se
  nezahodí) ani "karta B přidala nález" race (nález v `known_ids` není,
  přežije). Zjednodušil jsem i `_merge_findings_by_id` samotnou (odpadla
  mrtvá `if known_ids is not None/else` větev, `None` a `set()` se teď
  chovají identicky). Nový integrační test (regenerate → odmítnutí
  kandidátu → lehký save).

- **BLOCKING - migrace (Task 13 Step 8): zápis PŘÍMO na finální cestu
  zálohy riskuje neúplný soubor po přerušení, co by DALŠÍ spuštění
  mylně považovalo za platnou zálohu.** Souhlas, reálné riziko (Ctrl-C/
  výpadek/OOM kill uprostřed `_snapshot_db`/`shutil.copy2`). Opraveno -
  OBĚ zálohy (DB i historie) teď píšou na dočasnou `.tmp` cestu, ověří
  se (integrity_check uvnitř `_snapshot_db`), a TEPRVE PAK atomicky
  `os.replace` na finální jméno - přerušení nechá nanejvýš osiřelý
  `.tmp` soubor (uklizený při dalším pokusu), nikdy poškozenou "platnou"
  zálohu. Historie backup navíc dostala VLASTNÍ `except` s recovery
  zprávou (dřív neošetřená, propadla by jako holý traceback).

### Agreed + fixed (NIT)
- `payload.get("known_ids") or []` by tiše propustilo PŘÍTOMNÉ, ale
  ne-list hodnoty (`false`/`0`/`""`/`{}`) místo 400. Opraveno na
  explicitní `None`/chybějící rozlišení. Nový test.

## Claude VERDICT

CHANGES_NEEDED (souhlas se vším, plná implementace)

## Summary for log

Kolo 21 dokončuje kolo-19/20 sérii (třetí a poslední mezera ve stejném
mechanismu - lehká větev) a najde nezávislou, reálnou mezeru v migračním
skriptu (backup atomicity). Vzorec z kola 13 se opakuje - vlastní
oprava (kolo 20) nebyla úplná, Codex našel zbývající díru další kolo.
Řešení (jednotné `known_ids` na OBOU větvích) je ve výsledku
JEDNODUŠŠÍ než Codexův navržený speciální příznak - stojí za
zaznamenání, že "bezpečně degraduje na no-op" vlastnost `known_ids`
umožnila zobecnění bez zvláštního případu.
