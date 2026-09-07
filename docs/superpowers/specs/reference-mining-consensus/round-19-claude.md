# Round 19 — Claude critique

Kolo mělo zkontrolovat, jestli opravy z kola 18 nezavedly nové rozpory.
**Zavedly - a jeden z nich byl blokující.**

## On Codex's points

### Agreed + fixed (BLOCKING)

- **Precedence klasifikace, kterou jsem přidal v kole 18, vracela do hry
  centrální chybu specu.** Napsal jsem krok 2 jako „primární povrch doložen →
  `weak`", bez podmínek způsobilosti. Jenže `weak` předvyplňuje - takže `stole`
  se svými 79 výskyty a malým počátečním písmenem by spadlo do `weak`
  a předvyplnilo se. Přesně ta chyba, kvůli které celý ten aparát vznikl,
  a zavedl jsem ji opravou, která měla dokument sjednotit.

  *Oprava:* zavedena explicitní definice **způsobilosti** (velké počáteční
  písmeno, ≥ 3 znaky, alespoň jeden výskyt shodný i ve velikosti písmen,
  u krátkých povrchů výskyt mimo začátek věty) a kroky 1 a 2 se týkají **jen
  způsobilých** povrchů. Nezpůsobilý povrch jde vždy do stupně 1 a končí nejvýš
  `evidence_only`.

### Agreed + fixed (IMPORTANT)

- **Test agenta si po kole 18 protiřečil s precedencí:** tvrdil, že explicitní
  `null` dá vždy `unresolved`, ale nová precedence má u položky s důkazem ze
  stupně 0 dát `evidence_only`. Upřesněno.
- **Pravidlo o zobrazení důkazu zabíjelo `evidence_only`.** Vazba
  „liší-li se `cz` od `matched_cz`, důkaz skryj" se vztahovala i na třídu,
  jejímž **jediným obsahem je důkaz** a která má `cz` prázdné záměrně.
  Omezeno na třídy s předvyplněnou hodnotou.
- **Postpodmínka 6 nešla mechanicky ověřit** („aliasy jsou identifikující …
  a spol."). Doplněn konkrétní predikát pro označení podezřelých aliasů
  (malé počáteční písmeno, ≤ 3 znaky, seznam oslovení a rolí); rozhoduje dál
  člověk, ale test vynucuje, že žádný označený alias nezůstal.

### Agreed (NITS)

- `matched_en` sjednoceno na `matched_forms` podle schématu `Evidence`.
- `Finding.source` doplněn pro `evidence_only`.

## Claude's own findings

Žádné nad rámec Codexových.

## Claude VERDICT

CONSENSUS
