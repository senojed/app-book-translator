# Round 5 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`CodexLLMClient.complete()` vrací `input_tokens=0,
  output_tokens=0` natvrdo):** Souhlasím, ověřil jsem - `PipelineLLMClient.
  complete()` (`src/llm/client.py:229-230`) čte tyhle hodnoty PŘÍMO z
  vráceného `Completion` a zapíše je do `record_llm_call(...)` beze
  změny. `main._print_usage()` (main.py:77-81) je SČÍTÁ napříč celým
  `run`em pro souhrnný report. Natvrdo `0` by po zpracování CELÉ knihy
  Codexem ukázalo "0 tokenů" - cena `$0` je správně (billed_model má
  nulovou sazbu), ale objem zpracovaného textu by byl neviditelný, i
  když klient má vlastní konzervativní odhad k dispozici (`count_
  tokens()` už `(len(system)+len(user))//2` počítá).

  **Oprava:** `complete()` vrátí `input_tokens=(len(system)+len(user))
  //2` (stejný vzorec jako `count_tokens()`) a `output_tokens=len(text)
  //2` (stejná konzervativní aproximace na výstupu). Task 3 rozšířena -
  test i implementace.

### Agreed but already addressed
- **NIT (chybí test, že oba prompty obsahují `===KONEC===`):** Přidán
  `test_system_prompts_instruct_end_marker` do Tasku 2.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 5: Codex našel reálný IMPORTANT - `CodexLLMClient.complete()`'s
natvrdo nulové `input_tokens`/`output_tokens` by zkreslily `main.
_print_usage()`'s souhrnný report (cena správně $0, ale objem
neviditelný). Opraveno stejnou konzervativní aproximací, co `count_
tokens()` už používá. Přidán i drobný regresní test na NIT bod (oba
systémové prompty musí instruovat model o `===KONEC===` markeru).
