# Round 28 — Claude critique

Druhé review kola-27 dodatku. Codex našel 6 IMPORTANT, všechny platné.
Dodatek je zjevně reálný subsystém (report s bezpečnostními a
robustnostními dopady), ne "aditivní próza" - proto pořád generuje
nálezy.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `STYLIST_REPORT_REJECTED_TEXT=False` netěsní:**
  `reasons`/`findings` mají volná pole (`issue`, `cz_excerpt`, `actual`)
  co můžou zopakovat exfiltrovaný úryvek, a `issue` se vždy tiskl do
  konzole. → `False` teď ukládá i tiskne JEN `reason_types`
  (normalizované `"src/type"` kategorie, žádný volný text).
- **IMPORTANT - `incomplete = run_status != "ok"` chybná odvozenina:**
  dávka, kde všechny kapitoly `failed`, doběhla celá, ale
  `run_status="fatal"`. → samostatný `batch_completed` + `planned_count`/
  `attempted_count`, `run_status` už nesuplu je úplnost.
- **IMPORTANT - "report vždy po Fatal" neplatilo:** (a) výjimka po
  `create_run` před 1. kapitolou → `if not report: return` → žádný
  report; zrušeno, píše se vždy když je `rid`. (b) fatální commit
  aktuální kapitoly ji nezapsal → `_polish_one_chapter` teď před raise
  appendne `{"outcome": "fatal", "stage": "commit", "error"}`. Přidán
  top-level `run_error`.
- **IMPORTANT - "failed = žádné findings, je PŘED kontrolami"
  nepravdivé:** neočekávaná výjimka může spadnout uprostřed konkordance/
  kritika. → kontrakt honestně: `failed` VŽDY jen `error`, bez ohledu na
  fázi; částečné mid-computation findings se vědomě nezachovávají.
- **IMPORTANT - duplicitní důvod (nový klíč + syntetický nárůst) se
  agreguje dvakrát:** → `_rejection_reasons` cíleně přeskočí syntetický
  "nárůst výskytu" důvod, když `(type, term_id)` už je mezi
  konkordančními důvody. `reason_types` je stejně set. Nekonkordanční
  důvody se nededupují (dva kritikovy `fidelity` = dvě informace).
- **IMPORTANT - report psán PŘED `finish_run`:** když finalizace DB
  selže, report tvrdí `run_status="ok"` ale `runs` řádek je nedokončený.
  → přehozeno: `finish_run` first (best-effort, `finalization_error`
  zachyceno), pak report.

## Claude's own findings
Při přepisu jsem si sám zavlekl bug (dedent `for s` loop mimo `for f`) -
zachyceno vlastní kontrolou struktury přes `ast`, opraveno.

## Claude VERDICT

`CHANGES_NEEDED` - 6 platných IMPORTANT, vše aplikováno. Report subsystém
je teď výrazně robustnější. Čeká se na kolo 29 (poslední z 3
požadovaných).

## Summary for log

Kolo 28: 6 IMPORTANT ve stále doplňovaném report subsystému. Klíčové:
(1) `=False` opt-out netěsnil přes volná pole nálezů + konzoli (→ jen
`reason_types`); (2) `incomplete` chybně odvozený ze `status` (→
`batch_completed`/`planned_count`/`attempted_count`); (3) report se
nezapsal při pádu před 1. kapitolou ani u fatálního commitu (→ vždy
když `rid`, + `fatal` záznam); (4) `failed` kontrakt honestně "jen
error, bez ohledu na fázi"; (5) dedup duplicitních důvodů;
(6) `finish_run` → report pořadí (`finalization_error`). Čeká se na
kolo 29.
