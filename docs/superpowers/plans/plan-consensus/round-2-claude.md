# Round 2 — Claude critique (plán)

## Claude's own findings

Žádné vlastní BLOCKING/IMPORTANT. Codexových 6 bodů je pokračování transakce B
+ lifecycle + guide shape z kola 1. Dobrá kontrola konzistence po velkém přepisu.

## On Codex's points

### Agreed + fixed
- **BLOCKING: `build_mentions` před vložením kandidátů → nový termín bez
  `term_mentions` řádku → requeue ho nenajde** — opraveno dvojitě:
  (1) `glossary_rows` = `all_terms(db) + new_candidates` PŘED `build_mentions`;
  (2) navíc pipeline přidá EXPLICITNÍ mention `{term_id, cz_form: cz,
  chapter_idx, source: "rendered"}` pro každý nový kandidát - nespoléhá na to,
  že jeho EN povrch je v EN textu. Test rozšířen o assertion `term_mentions`;
  nový end-to-end test v Task 15 (`test_process_chapter_then_answer_requeues_
  original_chapter`).
- **BLOCKING: `finish_run` ve `finally` i v `except` - nekonzistentní** —
  opraveno: jeden závazný lifecycle pattern v Task 15 (`status = "fatal"`
  pesimistický default, `status = "ok"` jen po úspěchu, JEDINÝ `finish_run`
  ve `finally`). Per-chapter `except FatalRunError` jen `raise` (bublá do
  lifecycle). Inline `finish_run` odstraněn.
- **IMPORTANT: `relationship_key` plán vs spec rozpor** — vyřešeno úpravou
  SPECU: `relationship_key(a,b) = "|".join(sorted(normalize(a), normalize(b)))`
  bez `resolve_surface`, s explicitním v1 omezením. Plán a spec teď souhlasí.
- **IMPORTANT: `load_guide` KeyError na chybějícím `terms`** — opraveno:
  `load_guide` doplní plný shape i pro existující soubor se starým tvarem;
  test `test_load_guide_normalizes_partial_existing_file`.
- **IMPORTANT: cost guard `scan` má tvrdě zastavit, ne se ptát** — opraveno:
  `PipelineLLMClient(..., interactive=True)` param; `interactive=False` →
  přes strop rovnou `FatalRunError`. `scan`/`run` cf předává `interactive=False`.
  Test `test_cost_guard_non_interactive_hard_stops`.
- **IMPORTANT: Task 14 chybí test requeue po kandidátovi** — opraveno:
  end-to-end test v Task 15 (viz výše), + `term_mentions` assertion v Task 14.
- **NIT: Task 6 "5 tests"** → 6; **Task 7 "6 tests"** → 8; Task 5 doplněn počet.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 2 BLOCKING (Codex) reálné (new-term mention gap, lifecycle
nekonzistence). Claude 0 vlastních. Spec upraven kvůli 1 rozporu. Chce
potvrzovací kolo.

## Summary for log
Kolo 2: Codex 2 BLOCKING (nový termín bez term_mentions řádku → requeue ho
nenajde; finish_run ve finally i except) + 4 IMPORTANT + 2 NIT. Claude 0
vlastních. Opraveno: pipeline přidá explicitní mention pro každý nový kandidát
(+ kandidáti do glossary_rows před build_mentions); jeden závazný lifecycle
pattern (status default "fatal", jediný finish_run); `interactive` param
u PipelineLLMClient (scan = hard stop); `load_guide` normalizuje chybějící
klíče; SPEC upraven - `relationship_key` bez resolve_surface (rozpor plán/spec
vyřešen). Sporné: nic.