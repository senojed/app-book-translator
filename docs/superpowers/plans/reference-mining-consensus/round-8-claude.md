# Round 8 — Claude critique

## Claude's own findings

Žádné nové vlastní nálezy - oba Codexovy body jsem ověřil a oba se
potvrdily jako reálné.

## On Codex's points

2 BLOCKING, 1 IMPORTANT. Všechny přijaty po ověření.

### Agreed + fixed

- **Task 3: `manifest` v `load_corpus()` se bral jen JEDNOU, PO parsování
  všech EPUBů - ne před ním.** `_load_side` čte obsah desítek souborů, což
  chvíli trvá; změní-li se soubor UPROSTŘED (jiný proces, re-export),
  vrácený `Corpus` má STARÝ text s NOVÝM manifestem. Task 13 tenhle manifest
  ukládá jako otisk toho, co bylo vytěženo (`manifest_fingerprint`, oprava
  z kola 4) - kdyby byl sám nekonzistentní, `review` by mohl nález ze
  starého textu tiše označit za čerstvý. *Fix:* manifest se bere PŘED
  parsováním i PO něm; neshodují-li se, `load_corpus()` zvedne `ValueError`
  ("soubory se změnily během načítání") místo tichého použití kteréhokoli
  snímku. `_cmd_reference` to už převádí na `FatalRunError` beze změny
  (existující `except ValueError` větev). Nový regresní test simulující
  změnu souboru mezi dvěma `_load_side` voláními.
- **Task 2: kroky 7 a 10 dělaly `git add data/...`, ale `.gitignore` má
  bare `data/` - celá složka je mimo git.** Ověřeno přímo v `.gitignore`.
  Tyhle commity by v repozitáři reálně selhaly. *Fix:* commity odstraněny,
  zůstala jen kopie souboru (záloha) v kroku 7; krok 10 už žádnou akci
  nedělá, jen konstatuje hotovo.

### Agreed + fixed (IMPORTANT)

- **Task 12: `invalidateAcceptAllChange` mazala záznam hromadné akce při
  KAŽDÉ následné změně pole, včetně naprogramovaného "použít návrh" a jeho
  vlastního "zpět".** Konkrétní scénář: hromadně přijmi → použij
  individuální (lexikografův) návrh na tomtéž poli (záznam se smaže,
  správně - hodnota se rozešla) → klikni "zpět" u toho návrhu (pole se
  vrátí přesně na hromadně přijatou hodnotu) → záznam zůstane smazaný
  natrvalo, přestože pole teď zase odpovídá tomu, co dávka nastavila.
  "Vrátit zpět přijetí" by pak tohle pole přeskočilo.

  Tohle je přímo v napětí s nálezem z kola 4 (`current === applied` prý
  může "shodou okolností" přepsat pozdější ruční zásah) - obě obavy nejdou
  uspokojit současně bez plného undo/redo zásobníku, což je mimo rozsah
  vanilla-JS formuláře. Rozhodl jsem se pro ŽIVOU shodu hodnoty při SAMOTNÉM
  "zpět" (`pendingAcceptAllChanges()` filtruje podle `data[...] ===
  applied` v okamžiku kliknutí), ne pro jednosměrné mazání záznamu při první
  odchylce - řeší to Codexův konkrétní, demonstrovaný scénář; cenou je
  nízkopravděpodobnostní hypotetický scénář z kola 4 (nezávislá ruční
  hodnota, která náhodou vyjde stejně jako návrh). Rozhodnutí i kompromis
  zdokumentovány přímo v komentáři kódu, aby příští kolo nezačalo přešlapovat
  zpátky. Popisek a viditelnost tlačítka "vrátit zpět přijetí" teď taky
  používají tenhle živý výpočet, ne původní velikost dávky - jinak by číslo
  v popisku lhalo o tom, co tlačítko doopravdy vrátí. Tlačítko "přijmout
  všechny" se navíc samo odemkne, klesne-li živý počet čekajících změn na
  nulu (jinak by zůstalo navždy disabled, i když už není co vracet).

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Osmé kolo - oba nálezy patří do dvou různých, dosud nezasažených kategorií:
TOCTOU race v korpusu (Task 3) je první čistě filesystémová chyba mimo UI
i datový model, a git/gitignore nesoulad (Task 2) je první nález, který se
netýká kódu vůbec, jen provozní reality repozitáře - dřívějších sedm kol
tuhle konkrétní kategorii (co se vlastně dá commitnout) neprobíralo.

IMPORTANT bod o skládání vratných akcí je zajímavý tím, že staví PROTI
kola-4 nálezu - dva legitimní požadavky (nepřepisovat pozdější rozhodnutí
vs. umožnit smysluplné složení akcí) nejdou v tomhle jednoduchém modelu
uspokojit současně. Vybral jsem stranu, kterou favorizuje KONKRÉTNÍ,
demonstrovaný scénář (round 8) před HYPOTETICKÝM (round 4), a napsal do
kódu proč - aby se příští kolo nerozhodovalo znovu od nuly.

Všech 32 Python bloků a 1 JS blok znovu ověřeno strojově, test-count
komentáře skriptem přes všechny tasky.
