# Round 14 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`_parse()` nevaliduje typy polí uvnitř položek):**
  Souhlasím, ověřil jsem trasováním - `{"new_terms":[{"term_en":1}]}`
  projde kolo-12's kontrolou (JE seznam, položka JE dict), ale
  `pipeline.py`'s `(nt.get("term_en") or "").strip()` (`src/pipeline.py:83`)
  na INTU spadne na `AttributeError` (`1` je truthy, `or ""` fallback se
  nepoužije) - stejná mezera pro `_scope_key_for(q)`'s `scope_key` pole.
  Neklasifikované jako `InvalidTranslationOutput`, tedy přesně ten
  stav, co má tahle výjimka zabránit.

  **Oprava:** `_parse()` navíc validuje typ OČEKÁVANÝCH textových polí
  uvnitř každé `new_terms`/`rendered_terms`/`questions` položky
  (`term_en`/`cz`/`note`/`type`, `term_id`/`cz_as_used`,
  `kind`/`scope_key`/`guess_answer`/`text`/`severity`) - musí být
  string nebo `None`/chybí. Přidán regresní test.

- **IMPORTANT (`CodexLLMClient` jde zkonstruovat/zavolat mimo
  `_client_factory`'s gate):** Souhlasím - ověřil jsem `stylist.
  polish()`'s vlastní kód (`src/agents/stylist.py:505-511`) - MÁ
  identickou `STYLIST_ACCEPT_FS_RISK` kontrolu UVNITŘ SEBE, nezávisle
  na volajícím. `CodexLLMClient` tenhle vzor nedodržoval - spoléhal
  VÝHRADNĚ na `_client_factory`'s caller-side gate.

  **Oprava:** `complete()` zkontroluje `config.STYLIST_ACCEPT_FS_RISK
  is not True` JAKO PRVNÍ krok, vyhodí `CodexTranslatorFatalError` -
  stejný vzor jako `polish()`, jen jiný výjimkový typ (patří
  `CodexLLMClient`, ne `stylist.py`). Přidán test.

### Disagreed (částečně)

- **IMPORTANT (Task 6 DB kopie + "polish jen po done"):** Souhlasím s
  PRVNÍ částí - prostý `cp`/`Copy-Item` nad `state.sqlite3` může
  zachytit nekonzistentní snapshot, pokud DB není quiescent. Opraveno
  na `sqlite3 ... ".backup"` (SQLite's oficiální konzistentní kopie),
  `guide.json` zůstává prostý `cp` (obyčejný JSON soubor, bez
  souběžných zapisovačů).

  NESOUHLASÍM s DRUHOU částí - tvrzení "`flagged` kapitolu polish
  správně odmítne" jsem OVĚŘIL přímo v `main.py` a je FAKTICKY
  NEPRAVDIVÉ. `_cmd_polish`'s fronta (main.py:1276) je `all_pending =
  state.chapters_by_status(db, ("done", "flagged", "needs_human"))` -
  `flagged` je EXPLICITNĚ zahrnutý, s komentářem vysvětlujícím PROČ
  (uživatel chce stylizovat celou knihu, kritické nálezy řešit ručně
  v editoru, ne nechat flagged kapitolu trčet). Tohle je ZÁMĚRNÝ,
  dřívější (před tímhle plánem) design fix z tohohle projektu - ne
  mezera, co bych měl "opravit" přidáním umělého omezení do manuálního
  ověřovacího kroku. Instrukce v plánu ("polish --only... projde
  stejně jako dřív") zůstává BEZE ZMĚNY - je správná.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 14: dva IMPORTANT body plně přijaty (validace typů polí uvnitř
metadata položek, vlastní FS_RISK gate v CodexLLMClient - obojí
"obrana do hloubky" proti mezerám, co by jinak unikly klasifikaci/
kontrole). Třetí bod (Task 6 DB kopie) přijat ČÁSTEČNĚ - kopie DB
opravena na SQLite's `.backup` (konzistentní snapshot), ale odmítnuto
tvrzení, že `polish` odmítá `flagged` kapitoly - ověřeno přímo v
`main.py`, `_cmd_polish` je EXPLICITNĚ a záměrně zahrnuje (starší,
již-implementovaný design rozhodnutí tohohle projektu). Fakt od
Codexu ověřen proti datům a vyvrácen - první případ v tomhle
plan-consensus, kdy recenzentovo tvrzení bylo přímo v rozporu se
skutečným kódem.
