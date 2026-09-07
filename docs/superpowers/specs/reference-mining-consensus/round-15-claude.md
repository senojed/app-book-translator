# Round 15 — Claude critique

Poprvé po devíti kolech **žádný blokující nález**. Pět důležitých, všechny
ověřeny měřením na skutečném draftu.

## On Codex's points

### Agreed + fixed

- **Krok 0 nekontroloval všechny postpodmínky, které má zajistit.** Skript měl
  hlásit jen kolize a lomítka, takže by u draftu, který podmínky nesplňuje,
  tvrdil „hotovo". Doplněno šest očíslovaných postpodmínek, které skript
  kontroluje a test vynucuje.
- **Povrchy s poznámkou v závorce.** Ověřeno, je jich 6: `Warden(s)`,
  `the Merlin (title)`, `Stroger's (hospital)`,
  `grasshopper (nickname for Molly)`, `evocation words (Forzare, ...)` a alias
  `Demonreach (nickname given by Harry)`. Přesné hledání je u nich z principu
  nefunkční. Doplněno do tabulky vad i do postpodmínek.
- **Homonymum napříč sekcemi.** Ověřeno: `Demonreach` je současně postava
  i místo. Sekčně oddělené `id` před tím nechrání, protože **glosář má identitu
  globální** - `_seed_one` hledá povrch přes celou tabulku, takže druhý seed
  by první tiše přepsal a navržený guard chrání jen nález přes alias. Doplněno
  jako postpodmínka.
- **Neidentifikující aliasy.** Ověřeno, devět: `sir`, `kid`, `apprentice`,
  `Captain`, `Bob`, `Mad`, `Ana`, `Sam`, `Mai`. V predikátu souvýskytu by `E`
  rozšířily skoro na celý korpus. Dvojí oprava: krok 0 je odebírá **a zároveň**
  `books_with_en` nově používá **jen primární povrch** - predikát nemá stát na
  tom, že normalizace proběhla dobře.
- **Vztahy odkazující zkráceným jménem.** Ověřeno: `Ebenezar` vs
  `Ebenezar McCoy`, `Lara` vs `Lara Raith` - dvojice, které se mají sloučit,
  a jejich `scope_key` přemapovat. Doplněno do postpodmínek.
- **Aliasy míst a termínů se ztrácely** v merge kontraktu i v allowlistu.
  Dnes je žádné místo ani termín nemá, ale spec budoucímu scoutovi ukládá
  synonyma do `aliases`, takže by se před glosářem ztrácely. Doplněno.

### Agreed (NITS)

- „26 řádků" opraveno na ~39 (číslo z kola 14).
- Obecné tvrzení o `must_decide` upřesněno na **textové** větve.

## Claude's own findings

- **Do specu se mi dostal skutečný NUL bajt.** Psal jsem oddělovač dokumentů
  a v jedné náhradě se neescapoval, takže `git` i `grep` začaly soubor
  považovat za binární. Opraveno; příčina byla, že heredoc požírá zpětná
  lomítka - napříště na takové řetězce nepoužívat textovou náhradu přes shell.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Poprvé žádný blokující nález; pět důležitých, všechny ověřeny měřením.
Krok 0 nekontroloval všechny postpodmínky, které slibuje — doplněno šest
očíslovaných a k tabulce vad přibyly čtyři nové kategorie (povrchy s poznámkou
v závorce, homonymum napříč sekcemi, neidentifikující aliasy, vztahy
odkazující zkráceným jménem). Nejcennější je zjištění, že glosář má identitu
globální, takže sekčně oddělená id nechrání před kolizí Demonreach
(postava i místo). books_with_en nově používá jen primární povrch, aby predikát
nestál na tom, že normalizace proběhla dobře.
Vedlejší nález Claudea: do specu se dostal skutečný NUL bajt a soubor se stal
binárním; opraveno.
