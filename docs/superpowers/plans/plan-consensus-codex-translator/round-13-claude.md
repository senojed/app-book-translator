# Round 13 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`CodexTranslatorFatalError` během revize zahodí `cz`
  i po kolo-10/11 fixu):** Souhlasím a ověřil jsem přesně, proč - kolo
  10/11's oprava dala `_cmd_run` schopnost označit kapitolu `flagged`
  PO tom, co `process_chapter()` vyhodí výjimku - ALE `pipeline.py`'s
  revizní smyčka (`except FatalRunError: raise`) STÁLE jen PROPAGUJE
  výjimku, NIKDY necommitne `cz` (scénový překlad, případně částečně
  revidovaný). `state.commit_chapter_result()` běží AŽ NA KONCI funkce -
  `raise`/re-raise se tam nikdy nedostane. `_cmd_run`'s `flagged` status
  je tak jen KOSMETICKÝ nálepka - `translated_text` sloupec zůstává
  prázdný/starý, skutečná (zaplacená!) práce je ztracená STEJNĚ, jako
  kdyby kolo 10/11 vůbec neexistovalo. Existující test `test_revision_
  fatal_error_propagates_not_flagged` dokonce explicitně ASSERTOVAL
  `status != "flagged"` - dokumentoval tenhle bug jako "očekávané"
  chování, aniž bych si toho všiml při psaní kola 10/11.

  **Oprava:** `except FatalRunError as e:` (v `pipeline.py`'s revizní
  smyčce, Task 2) PŘED re-raise uloží `cz` jako `flagged` - minimální
  "transakce B" (`new_candidates=[]`, `mentions=[]`, `questions=[]` -
  ty se dají dohnat později, ztráta CELÉHO překladu ne), s pseudo-
  nálezem vysvětlujícím přerušení. `_cmd_run`'s NÁSLEDNÝ `state.
  update_chapter(..., notes=...)` (Task 5) tenhle zápis NEPŘEPÍŠE co do
  `translated_text` (`update_chapter()` mění jen explicitně předané
  sloupce) - jen `notes` nahradí obecnější run-úrovňovou zprávou,
  zdokumentovaný přijatý kompromis (detail revizního nálezu se ztratí,
  `translated_text` ne).

  Přepsán/přejmenován existující test (`test_revision_fatal_error_
  preserves_translation_before_reraising`) - PŮVODNÍ verze asserovala
  přesně opačné chování, co teď záměrně měníme.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 13: jeden IMPORTANT bod, ale zásadní - odhalil, že kolo 10/11's
"flagged status" oprava byla jen KOSMETICKÁ pro revizní-fázi fatální
chyby - skutečný přeložený text se STÁLE ztrácel, protože `pipeline.py`'s
`except FatalRunError: raise` nikdy nic necommitovalo. Existující test
dokonce asserotoval opak toho, co chceme (status != flagged) - přímý
důkaz, že tenhle bug byl od kola 10 nezpozorovaný. Opraveno: revizní
smyčka teď uloží poslední platný `cz` PŘED re-raise fatální chyby,
minimální transakce B. Existující test přepsán na nové očekávané
chování.
