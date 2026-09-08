# Round 5 — Claude critique

## Claude's own findings

Žádné nové vlastní nálezy - soustředil jsem se na ověření Codexových bodů,
z nichž první je obzvlášť závažný a vyžadoval skutečné trasování, ne jen
přečtení.

## On Codex's points

2 BLOCKING, 3 IMPORTANT. Všechny přijaty po ověření.

### Agreed + fixed

- **Task 12: odemčení pole (`unlock.onclick`) přepínalo `_czProvenance` na
  "human" HNED, ne až skutečnou editací.** Ověřeno trasováním: `backed`
  (dřívější jméno) se počítal z `fieldProvenance(item,"cz")==="reference"` -
  jakmile odemčení nastavilo provenienci na "human", `backed` se stal
  `false` a CELÝ blok s tlačítkem "vrátit zpět" přestal existovat při
  příštím `render()`. Uživatel, který jen klikl "změnit předvyplněné" (ale
  nic nenapsal) a pak provedl JAKOUKOLI jinou akci (přijmout všechny, přidat
  vztah), ztratil možnost vrátit se zpět natrvalo - přesně situace, kterou
  celý mechanismus `item._cz*` v kole 4 měl řešit, ale nová chyba vznikla na
  jiném místě téhož mechanismu. *Fix:* rozdělil jsem "může být doloženo"
  (`canBeReference` - třída + čerstvost, nemění se odemčením) od "je právě
  zamčené" (`locked` - navíc vyžaduje `!unlocked`). Provenience se teď mění
  AŽ v `oninput`/`onchange` (skutečná editace), ne v `unlock.onclick`.
  Revert cílí na `ref.matched_cz` (stabilní, ze serveru), ne na hodnotu
  zachycenou v uzávěru při konstrukci - ta by po editaci+re-renderu už
  neodpovídala originálu. Stejná oprava v `renderField` (cíl revertu je
  vždy doslova `"keep"` - jediná hodnota, kterou `ref_render` v `guide.py`
  kdy nastaví).
- **Tasky 8-9: type-validní, ale sémanticky nekonzistentní nález
  (`classification="proposed", cz="Vymyšleno"`) by prošel `load_reference`
  a `_merge_section` by ho vzal jako doložený.** Ověřeno: `resolve()` sám
  nikdy takovou kombinaci nevyrobí (viz `classify()` - `cz` se plní jen ve
  větvi confirmed/weak), ale `load_reference` validuje jen typy, ne
  sémantiku napříč poli - ručně upravený/poškozený soubor by prošel.
  *Fix:* `_finding_is_well_formed` nově vyžaduje `(cz is not None) ==
  (classification in confirmed/weak)` a totéž pro `navrh` vs.
  proposed/not_attested. NAVÍC obrana do hloubky v `_merge_section` -
  `ref_cz` se plní jen když `finding.get("classification") in
  (confirmed, weak)`, nezávisle na tom, co validace `load_reference` už
  odchytila (kdyby ho někdy něco obešlo). Čtyři nové testy (dva na validaci,
  jeden na merge_sources gate).

### Agreed + fixed (IMPORTANT)

- **Task 9/12: vazba důkazu na hodnotu měla dvě chyby najednou, opačným
  směrem.** (1) `_reference_block`'s `shown_cz and shown_cz != matched_cz`
  - prázdné `shown_cz` (validní stav u postavy s `render="keep"`) je falsy,
    takže podmínka "liší se" se vůbec nevyhodnotila a číselný důkaz zůstal,
    ačkoli prázdné pole zjevně neodpovídá `matched_cz`. *Fix:* odstraněna
    zbytečná `shown_cz and` podmínka - `shown_cz != matched_cz` sama stačí
    a správně zachytí i prázdný řetězec jako neshodu.
  - (2) `valueField` vázala zobrazení důkazu na `backed`/zamčení, takže
    ruční hodnota, která náhodou vyjde stejně jako `matched_cz`, důkaz
    neukázala, ačkoli backend (po opravě (1)) ho posílá. *Fix:* zobrazení
    důkazu přesunuto MIMO blok zamčení, řízené přímo `item.cz ===
    ref.matched_cz` (živě, ne jen podle toho, co server řekl při GET) -
    důkaz se tak ukáže i po ruční editaci, pokud výsledná hodnota souhlasí,
    a zmizí, jakmile se rozejde.
- **Task 12: tři testy nespouštějí JS.** Stejné škálovací rozhodnutí jako
  v kolech 2 a 4 - žádná nová DOM test infrastruktura v tomhle plánu. Stav
  je teď navíc kompletně v `item._*` vlastnostech (žádné closures), takže
  by ho šlo pokrýt čistě datovými testy bez prohlížeče, kdyby se DOM
  testování do projektu později přidalo.
- **Task 12: `aliasCollisionWarnings` - `owners[key]` držela jen JEDNOHO
  vlastníka, pozdější alias přepsal dřívějšího.** Ověřeno konkrétním
  scénářem: `Bar` má alias `Foo`; `Foo` má (autorskou nepřesností) i sebe
  sama v `aliases`. Přepsání by skrylo kolizi s `Bar` za sebeodkaz `Foo` na
  sebe sama - kontrola `owner === self` by u položky `Foo` vrátila "shoda",
  ačkoli `Bar` pořád koliduje. *Fix:* `owners[key]` je teď pole všech
  vlastníků; varování se generuje, zůstane-li po odečtení sebe sama
  aspoň jeden jiný.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Páté kolo - Codexův první BLOCKING je nejpřesnější nález celé oponentury:
moje vlastní kolo-4 oprava (přesun stavu z closures na `item._cz*`) sama
zavedla NOVOU variantu stejné třídy chyby, kterou měla opravit - odemčení
teď měnilo provenienci moc brzo, takže "vrátit zpět" mizelo přesně tou
cestou (nesouvisející re-render), kterou měl fix z kola 4 řešit. Opravil
jsem to rozdělením "může být doloženo" od "je právě zamčené" a přesunem
přepnutí provenience z kliknutí na odemčení do SKUTEČNÉ editace.

Druhý BLOCKING (sémantická konzistence `cz`/`navrh` vůči `classification`)
je první nález v celé oponentuře, který se netýká regrese - je to mezera,
co tu byla od Tasku 8/9 vzniku (validace kontrolovala typy, ne vztahy mezi
poli). Přidána jako obrana do hloubky na dvou místech nezávisle.

Vazba důkazu na hodnotu (`shown_cz and ...`) měla chybu v OBOU směrech
najednou -děravou i příliš přísnou zároveň - což je přesně ten typ chyby,
který jednosměrný test snadno přehlédne (test na "liší se" prošel, protože
netestoval prázdný řetězec; test na "shoda" prošel, protože netestoval
lidskou provenienci).

Všech 32 Python bloků a 1 JS blok znovu ověřeno strojově. Test-count
komentáře znovu zkontrolovány skriptem přes všechny tasky.
