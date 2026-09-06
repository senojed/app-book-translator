# Multi-agentní překladač knih (CLI, fáze 1: funkčnost)

Docker/exe záměrně vynechán - nejdřív ověřit, že pipeline funguje a dává
smysluplné výsledky. Přenositelnost na konec.

## Instalace

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Architektura

- `src/ingest.py` - načte EPUB nebo TXT, rozdělí na kapitoly
- `src/state_db.py` - SQLite stav (přerušitelný/navazatelný běh)
- `src/glossary.py` - JSON glosář a style guide (sdílený stav mezi agenty)
- `src/llm_client.py` - tenká vrstva nad Anthropic API
- `src/agents/translator.py` - překlad úseku textu
- `src/agents/terminology.py` - kontrola konzistence termínů (nezávisle na translatorovi)
- `src/agents/critic.py` - nezávislá revize věrnosti/plynulosti (nevidí translator reasoning)
- `src/agents/cross_reference.py` - periodická kontrola driftu napříč kapitolami
- `src/orchestrator.py` - řídí pořadí volání agentů, zapisuje stav

## Použití

```bash
# 1. Načtení knihy
python main.py init cesta/ke/knize.epub    # nebo .txt

# 2. Kalibrace - zpracuje prvních pár kapitol (config.CALIBRATION_CHAPTERS),
#    agent sbírá otevřené otázky (nejednoznačná jména, styl) místo hádání
python main.py calibrate

# 3. Zodpovězení otázek - odpověď se zapíše jako závazné pravidlo do style guide.
#    Jakmile jsou zodpovězené VŠECHNY otázky jedné kapitoly, kapitola se vrátí
#    do fronty a příští 'calibrate'/'run' ji přeloží znovu s doplněným pravidlem.
python main.py questions
python main.py answer 1 "Jméno Harry Dresden se neskloňuje, zůstává v 1. pádě i jinde."

# Pokud calibrate po zodpovězení otázek narazí na další pending kapitoly
# v kalibrační fázi, spusť znovu 'calibrate' - zpracuje další dávku.

# 4. Plný běh přes zbylé kapitoly
python main.py run

# 5. Přehled stavu (OK = hotovo, !! = kritik/terminologie našly problém,
#    ?? = čeká na tvou odpověď, .. = ještě nezpracováno, XX = spadlo, zkusí se znovu)
python main.py status

# 6. Export hotových kapitol do output/kniha_cz.txt
python main.py export
```

## Co znamená "critic_flagged"

Kapitola prošla translatorem, ale kritik nebo terminologický agent našel
problém (kritickou chybu věrnosti, nebo nekonzistentní termín). Detaily jsou
v DB ve sloupci `critic_notes` (JSON). Pipeline v této verzi kapitolu
NEOPRAVUJE automaticky - jen ji označí. Automatická oprava na základě
critic_notes je logický další krok, zatím záměrně vynechaný, aby šlo napřed
ověřit, jak často a jak závažně se kritik s translatorem rozchází.

## Známá omezení / co ještě není hotové

- Žádná automatická oprava po critic_flagged - jen reportuje.
- Cross-reference report se ukládá do DB, ale CLI ho zatím jen loguje počet
  nálezů, ne detail - detail je v tabulce `cross_ref_reports`.
- Cross-reference posílá modelu jen 1500 znaků z každé kapitoly - u knihy se
  stovkou kapitol se to do kontextu nevejde. Bude potřeba předělat (konkordance
  termínů z kódu, model jen posuzuje sporné případy).
- Retry na API chyby (429 rate limit, 5xx) řeší SDK - `config.API_MAX_RETRIES`
  (default 8). Když volání i tak selže, kapitola se označí `error` a běh
  pokračuje; `run` ji příště zkusí znovu.
- Odhad nákladů/času na celou knihu neznámý - `calibrate` a `run` na konci
  vypíšou spotřebu tokenů za daný běh. Změř na pilotních 2-3 kapitolách, cenu
  spočítej podle sazby modelu, než pustíš celou knihu.

## Testy

```bash
pip install pytest
python -m pytest tests/          # nebo bez pytestu: python tests/test_parsing.py
```

Pokrývají čistou logiku bez volání API: parsování odpovědi translatora,
dělení kapitol na scény, segmentaci TXT knihy.
