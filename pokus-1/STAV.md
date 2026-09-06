# Pokus 1 - stav při archivaci (2026-09-06)

Multi-agentní CLI překladač knih EN→CZ. Začato v Claude chatu, dokončováno
v Claude Code. Archivováno před druhým pokusem - přechod z brainstormu rovnou
do kódu, chybí psaný spec "co je fáze 1 hotová".

Nezahazovat. Slouží jako reference pro pokus 2.

## Co funguje (otestováno bez API)

- CLI: 7 příkazů (init, calibrate, questions, answer, run, status, export)
- `src/ingest.py` - TXT (regex "Chapter N" / fallback) i EPUB (podle spine) → kapitoly, dělení na scény
- `src/state_db.py` - SQLite stav, navazatelný běh, 3 tabulky
- `src/glossary.py` - JSON glosář + style guide, sdílený stav mezi agenty
- `src/llm_client.py` - volání Anthropic API, retry (max_retries=8), detekce useknutého výstupu, počítání tokenů
- `src/agents/*` - translator, terminology, critic, cross_reference (každý = prompt + volání)
- `src/orchestrator.py` - sekvenční pipeline kapitoly
- `tests/test_parsing.py` - 11 testů čisté logiky, prošlo

## Co NENÍ ověřeno

- Nikdo to nepustil proti reálnému API. Prompty, formát odpovědí, kvalita
  překladu, chování kritika, cena/čas na kapitolu - vše nezměřeno.

## Známé slabiny / záměrně odloženo

- Auto-oprava po critic_flagged - jen označí, neopraví (záměr: nejdřív změřit rozchod kritik vs translator)
- Cross-reference: posílá jen 1500 znaků/kapitola, neškáluje přes desítky kapitol; detail jen v DB
- Terminology + cross-ref jako samostatní LLM agenti - kandidáti na nahrazení deterministickým kódem (konkordance)
- Windows konzole cp1252 spadne na českém výstupu (potřeba PYTHONIOENCODING=utf-8 nebo oprava)
- Kapitola je atomická - pád na scéně 4 z 5 → celá kapitola znovu
- Žádná ruční kontrola/editace překladu mezi `run` a `export`
- `character_register` ve style guide - pole existuje, nikdo neplní
- Docker/exe - fáze 2

## Ponaučení do pokusu 2

- Próza patří ven z JSON (dlouhý text v JSON stringu se usekává/rozbíjí) - v pokusu 1 vyřešeno oddělovačem
- Multi-agent zvyšuje cenu ~4x; ověřit že každý agent vydělává na sebe
- Nejdřív pilotní běh na 2-3 kapitoly, pak rozhodovat o architektuře
