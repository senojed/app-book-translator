# Book Translator

> ⚠️ **Work in progress** — osobní projekt, není produkční kvalita. API se může měnit bez ohlášení.

*[English version](README.en.md)*

Multiagentní CLI překladač knih EN→CZ. Pipeline scout → translator → kritik →
revizor, orchestrace v kódu. Stav v SQLite, takže běh jde kdykoli přerušit
a navázat.

Návrh a zdůvodnění rozhodnutí: [`docs/superpowers/specs/2026-09-06-book-translator-design.md`](docs/superpowers/specs/2026-09-06-book-translator-design.md).
Před prvním reálným během projdi [`docs/pilot-checklist.md`](docs/pilot-checklist.md).

## Instalace

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-..."
```

Python 3.11+.

## Fáze běhu

```bash
python main.py init kniha.epub    # kniha → kapitoly do DB (status pending)
python main.py scan               # scout projede knihu → data/guide.draft.json
python tools/check_draft.py                   # zkontroluj draft (report-only)
python main.py reference --dir "<cesta k referencím>"   # vytěž terminologii
python main.py review             # web UI: potvrdíš/upravíš návod → data/guide.json
python main.py run                # překladová smyčka přes kapitoly
python main.py questions          # otázky nadhozené během běhu
python main.py answer 7 "Bílá rada"   # odpověď → glosář/pravidlo + přepočet kapitol
python main.py status             # přehled stavu kapitol
python main.py export             # hotové kapitoly → output/kniha_cz.txt
```

Užitečné varianty:

- `init kniha.epub --reset` - zahodí dosavadní stav knihy a nahraje novou
- `scan --chunked` - když se kniha nevejde do jednoho volání scouta
- `run --retry-flagged [IDX...]` - vrátí označené kapitoly do fronty (vynuluje kola revize)
- `export --only-done` - jen čisté kapitoly (vynechané stejně vypíše na stdout)
- `answer 7 "Bílá rada | Bílé rady"` - první tvar je kanonický, další jsou schválené alternativy

## Terminologie z předchozích dílů

Máš-li předchozí díly série v EN i CZ, `reference` z nich vytěží zavedené
překlady. Složka musí mít podsložky `EN/` a `CZ/` a soubory číslované dílem.

Nejdřív `tools/check_draft.py` - vypíše, co je ve scoutově draftu rozbité
(výčty místo jednoho termínu, duplicitní entity, otázky odkazující nikam).
Nic nemění; opravíš to ručně v `data/guide.draft.json`.

Ve formuláři pak: **předvyplněné je jen to, co je doložené** v profesionálním
překladu, a vedle stojí důkaz („112× v 8 dílech"). Odhady modelu čekají vedle
prázdného pole na tlačítko „použít návrh".

## Stavy kapitol

| Marker | Stav | Co to znamená |
|---|---|---|
| `..` | pending | čeká na překlad |
| `~~` | processing | právě se zpracovává (uvízlé vrátí další `run` na pending) |
| `OK` | done | přeloženo, bez otevřených nálezů |
| `!!` | flagged | vážný nález přežil `MAX_REVIZE` kol - překlad je, ale projdi ho |
| `??` | needs_human | translator narazil na něco, co bez tebe nerozhodne (`questions`) |
| `XX` | error | technická chyba; běžný `run` to zkusí znovu |

`run` bere do fronty `pending` a `error`. `flagged` a `needs_human` přeskočí -
vrátí je do hry `answer`, resp. `run --retry-flagged`. Žádná kapitola nezastaví dávku.

## Kde co leží

- `data/` (gitignored) - `state.sqlite3`, `guide.json`, `guide.draft.json`, zámek běhu
- `output/` (gitignored) - `kniha_cz.txt`
- `config.py` - model IDs, ceny za tokeny, prahy, `MAX_REVIZE`, `MAX_SPEND_USD`

Glosář termínů je v SQLite (ne v JSON), aby jeho zápis a commit kapitoly byly
jedna transakce. Návod (`guide.json`) je soubor - edituje ho člověk přes review UI.

## Peníze

Každé volání se zapisuje do tabulky `llm_calls` (tokeny + cena). Cost guard
před každým voláním odhadne cenu; při překročení `MAX_SPEND_USD` se `run`
zeptá na nový strop, `scan` tvrdě zastaví.

```sql
SELECT agent, COUNT(*), SUM(cost_usd) FROM llm_calls GROUP BY agent;
```

## Testy

```bash
python -m pytest
```

Testy nesahají na API - agenti se testují přes `FakeLLMClient`, pipeline přes
monkeypatchnuté agenty.

## Archiv

`pokus-1/` je předchozí pokus (kompletní kostra, nikdy neběžela proti API).
Nedotýkat, slouží jen jako reference.
