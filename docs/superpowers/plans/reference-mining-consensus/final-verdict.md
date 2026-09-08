# Final verdict: CONSENSUS

Po 13 kolech (Codex read-only kritika + nezávislá Claude kritika a editace)
dosažena shoda ve stejném kole (13): Codex CONSENSUS, Claude CONSENSUS.

- Plán: `docs/superpowers/plans/2026-09-07-reference-mining.md`
- Spec: `docs/superpowers/specs/2026-09-07-reference-mining-design.md`
- Finální délka plánu: 4881 řádků (start: 3122 řádků)
- Kol do shody: 13 (bez omezení, běželo do konsensu; jeden dočasný blok
  na Codex usage limitu v kole 10, vyřešen retry po pokynu uživatele)

## Průběh

| Kolo | Codex verdikt | Claude verdikt | Klíčové nálezy |
|---|---|---|---|
| 1 | CHANGES_NEEDED (13 BLOCKING) | CHANGES_NEEDED | title-stripping v korpusu, NFC normalizace, fresh-fixture bug, Task 12 JS nikdy nezapojen do render() |
| 2 | CHANGES_NEEDED (7 BLOCKING) | CHANGES_NEEDED | regrese z kola 1 - cross_section vada, NFC/NFD mezi count_en_surface a classify() |
| 3 | CHANGES_NEEDED (5 BLOCKING) | CHANGES_NEEDED | closure stav Tasku 12 mizel při re-renderu |
| 4 | CHANGES_NEEDED (5 BLOCKING) | CHANGES_NEEDED | sdílená item.provenance mezi cz/render, undo bez ochrany |
| 5 | CHANGES_NEEDED (2 BLOCKING) | CHANGES_NEEDED | odemčení měnilo provenienci moc brzo |
| 6 | CHANGES_NEEDED (3 BLOCKING) | CHANGES_NEEDED | plánovaná oprava z kola 5 nikdy nezapsána |
| 7 | CHANGES_NEEDED (2 BLOCKING) | CHANGES_NEEDED | blur/click race (vlastní nález vložený do promptu) |
| 8 | CHANGES_NEEDED (2 BLOCKING) | CHANGES_NEEDED | TOCTOU race v load_corpus, git/gitignore nesoulad |
| 9 | CHANGES_NEEDED (0 BLOCKING) | CHANGES_NEEDED | bulk-undo nečistil per-field aktivní stav |
| 10 | CHANGES_NEEDED (0 BLOCKING, Codex usage limit → retry) | CHANGES_NEEDED | falešně zelený test, revert.onclick nečistil aktivní stav |
| 11 | CHANGES_NEEDED (0 BLOCKING) | CHANGES_NEEDED | Task 2 ruční instrukce neúplné, guide-only provenance |
| 12 | **CONSENSUS** (0 nálezů) | CHANGES_NEEDED (vlastní nález) | Přidej dvojici nemazalo relationships_reviewed |
| 13 | **CONSENSUS** (potvrdil fix z kola 12) | **CONSENSUS** | - |

## Charakter procesu

Dominantní vzorec první poloviny (kola 1-8): oprava v kole N zavedla novou,
lokalizovanou variantu stejné třídy chyby v kole N+1 - typicky proto, že
oprava řešila symptom na jednom místě, ale stejná mezera existovala na
druhém (analogickém) místě kódu. Tenhle vzorec byl výslovně pojmenovaný
a hlídaný od kola 3 dál (prompt pro Codexe explicitně žádal trasovat funkce
napříč kolama, ne jen nejnovější diff).

Task 12 (review formulář, `src/review_ui/static/index.html`) prošel
nejvíc iteracemi - stav rozeditovaných polí se přesunul z DOM closures
(kolo 1) na `item._cz*`/`item._render*` vlastnosti (kolo 4), hromadné
přijetí/vrácení se přepracovalo z jednosměrné invalidace na živou shodu
hodnoty (kolo 8), a dostalo vlastní automatizovaný test čisté JS logiky
přes Node bez DOM (kolo 9) - čtvrtý požadavek na tohle pokrytí, tentokrát
přijatý, protože se změnila data (tři kola stejné regrese ve stejné
oblasti).

Od kola 9 (Codex poprvé bez BLOCKING) se nálezy zmenšily na lokalizované
mezery bez vazby na předchozí opravy - signál skutečné konvergence, ne jen
vyčerpání kritika. Kolo 12 je jediné, kde Codex vrátil prázdnou kritiku,
ale Claude přesto pokračoval (vlastní nezávislý průchod je součást procesu
i při Codex-CONSENSUS) a našel reálnou mezeru (checkbox kontroly vztahů
nereagoval na přidání nové dvojice) - potvrzeno Codexem v kole 13.

## Stav plánu

`docs/superpowers/plans/2026-09-07-reference-mining.md` je připraven
k implementaci (`superpowers:executing-plans` nebo
`superpowers:subagent-driven-development`). Všech 33 Python kódových bloků
a JS blok formuláře ověřeny strojově (syntax) po každém kole, ne jen na
konci.
