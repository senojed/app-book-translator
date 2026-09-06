# Round 3 — Claude critique

## Claude's own findings

### IMPORTANT
- **Pseudokód `run` měl přeházené kroky 6/7** (artefakt round-1 editace): řádek
  `DELETE FROM term_mentions` visel pod krokem 7. → Přepsán celý blok kroků 0-8
  čistě, včetně nového kroku 0 (`processing`) a deterministického
  `build_mentions` v kroku 6.

### NITS
- `concordance` signatura sjednocena na `(en_text, cz_text, glossary)` napříč
  pseudokódem, sekcí concordance i testy.

## On Codex's points

### Agreed + fixed
- **BLOCKING: cost guard nemůže běžet "v pipeline před complete()"** (pipeline
  nezná system/user/max_tokens) — opraveno: guard přesunut DO
  `PipelineLLMClient.complete()`, kde ty argumenty z Protocolu má. Zároveň to
  řeší i bod o výstupní ceně (odhad = count_tokens(in)×in_rate +
  max_tokens×out_rate, konzervativně plný max_tokens).
- **IMPORTANT: `check_chapter` nemá EN, nemůže rozhodnout "očekávaný tvar
  chybí"** — opraveno: `check_chapter(en_text, cz_text, glossary)`; termín je
  "očekávaný" v CZ jen když jeho EN podoba je v EN textu. Přidán nález
  `omission` (v EN je, v CZ žádná známá podoba).
- **IMPORTANT: `term_mentions` z LLM `used_terms` nespolehlivé** — opraveno:
  `used_terms` z translatorova výstupu ODSTRANĚNO. `concordance.build_mentions`
  je staví deterministicky z EN+CZ textu + glosáře.
- **IMPORTANT: "answer nesahá na processing kapitolu" neimplementovatelné bez
  locku/stavu** — opraveno: přidán stav `processing`, `.book-translator.lock`
  (PID+čas) v `data/`; `run`/`scan`/`answer`/`init` při aktivním zámku skončí;
  read-only příkazy zámek ignorují; zastaralý zámek (mrtvý PID) se přebere;
  uvízlé `processing` kapitoly `run` na startu vrátí na `pending`.
- **IMPORTANT: cost formula bez output ceny** — opraveno (viz BLOCKING výše).
- **IMPORTANT: rollback rozpor "kapitoly beze změny" vs commitnuté kapitoly** —
  opraveno: "aktuální kapitola necommitnutá; dříve commitnuté zůstávají".
- **IMPORTANT: chunked scout merge - aliasy/kolize/konflikty vztahů** —
  opraveno: normalizační klíč `casefold()`, alias union, kolize jmen →
  `must_decide`, konfliktní `tyka/vyka` napříč chunky → `null` + `must_decide`.
- **NIT: `Stav: schváleno`** → `v revizi (plan-consensus)`.
- **NIT: `answer 3`** → `answer <question_id>`.

### Disagreed
- Nic.

## Claude VERDICT
CHANGES_NEEDED — 1 vlastní IMPORTANT (přeházený pseudokód), Codexův 1 BLOCKING
+ 6 IMPORTANT reálné. Rozsah menší než kola 1-2, konverguje. Chce potvrzovací kolo.

## Summary for log
Kolo 3: Codex 1 BLOCKING (cost guard umístění) + 6 IMPORTANT (concordance bez EN,
term_mentions z LLM, chybějící run lock, output cena, rollback wording, chunked
merge detaily) + 2 NIT. Claude 1 vlastní IMPORTANT (přeházený pseudokód po
editaci kola 1). Vše přijato: cost guard i logging teď v jednom obalu
`PipelineLLMClient.complete()`; `used_terms` z translatora pryč, `build_mentions`
deterministicky z EN+CZ; přidán stav `processing` + file lock; concordance bere
EN text + nález `omission`; chunked merge detailně (normalizace, kolize →
must_decide). Sporné: nic. Rozsah změn klesá.