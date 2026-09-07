# Round 14 — Claude critique

## On Codex's points

Všech sedm nálezů ověřeno **měřením na skutečném draftu**, ne úvahou. Všechny
platí.

### Agreed + fixed (BLOCKING)

- **Devět `must_decide` klíčů neukazuje na žádnou položku ve své sekci.**
  Ověřeno: `Warden`, `the Nevernever`, `Za-Lord's Militia`,
  `grasshopper_nickname`, `Mouse (pes)`, `grasshopper (Molly's nickname)`,
  `the Ostentatiatory`, `Shagnasty/skinwalker`, `Injun Joe`. Spec zmiňoval
  jen dva. `apply_must_decide` při nenalezení klíče **založí nový řádek**,
  takže by z nich vznikly duplicitní nebo špatně zařazené položky. Doplněno
  pravidlo: po normalizaci musí každý klíč ukazovat právě na jednu položku;
  pro každý dnešní se ručně zvolí oprava klíče / povýšení na položku / smazání.
- **Čtyři vztahy mají lomítko ve jméně.** Ověřeno: `Billy/Will`,
  `Gatekeeper/Rashid`, `Rashid/Gatekeeper` (duplicitní zápisy téže dvojice)
  a `Will/Georgia` (dva různí lidé). Bez opravy je zaškrtnutí „vztahy
  zkontrolovány" bezobsažné a jména vztahů navíc nejdou ve formuláři editovat.
- **Alias s vlastním překladem se do glosáře nevejde.** `Injun Joe` je alias
  `Listens-to-Wind` a zároveň má vlastní otázku na překlad, ale glosářový řádek
  má jedno `cz` pro kanonický tvar i všechny aliasy. Doplněno pravidlo: taková
  položka se povýší na samostatnou a její povrch se odebere z aliasů, aby
  nespustil guard proti kolizi.

### Agreed + fixed (IMPORTANT)

- **POST čistil jen bloky `reference`.** `provenance`, `scout_suggestion`,
  `lexicographer_suggestion` a příznak o vztazích by zůstaly v `guide.json`.
  Nahrazeno **allowlistem** ukládaných polí.
- **`Finding.source` neměl hodnotu pro `unresolved`** - doplněno `none`.
- **Rozpor v chování při nečerstvé referenci** - jedna část specu říkala
  „zobrazí se jen poznámka", druhá „klasifikace a návrh se zobrazují vždy".
  Sjednoceno na první variantu.
- **Zaškrtnutí vztahů nemělo kontrakt** - doplněno pole
  `relationships_reviewed`, jeho validace a odstranění před uložením.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Sedm nálezů, všechny ověřeny měřením na skutečném draftu. Krok 0 (normalizace)
byl specifikovaný proti neúplnému obrazu poškození: k 11 výčtům a 15 duplicitám
přibylo 9 must_decide klíčů, které neukazují na žádnou položku, a 4 vztahy
s lomítkem ve jméně. Celkem ~39 řádků. Doplněno i pravidlo pro aliasy
s vlastním překladem (do glosářového řádku se nevejdou, patří povýšit).
Dále: POST musí čistit allowlistem, ne jen bloky reference; Finding.source
doplněn o none; sjednoceno chování při nečerstvé referenci; zaškrtnutí vztahů
dostalo kontrakt.
