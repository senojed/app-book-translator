# Round 8 — Claude critique

## Claude's own findings

### BLOCKING
(žádné vlastní)

### IMPORTANT
(žádné vlastní nad rámec Codexových)

### NITS
Před zápisem tohohle souboru jsem udělal vlastní grep sweep na
`_kill_process_tree(pid)` starý vzor, `codex_cmd: str`, protichůdné
"mimo rozsah" bully - nic dalšího nenalezeno nad rámec toho, co Codex
označil.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - baseline-z-notes próza pořád na dvou místech:** ověřil
  jsem přímo - `_polish_rejected` docstring (kolo 3 bullet v "Rozhodnutí")
  pořád tvrdil "notes z doby, kdy kapitola dostala done" i po kole 4
  opravě KÓDU. Opraveno na obou nalezených místech.
- **IMPORTANT - záloha DB přepisuje poslední užitečnou zálohu:**
  přesvědčivý bod - eager záloha na začátku `_cmd_polish` by se přepsala
  i během, co nakonec nic nezapsal, čímž by se ztratila zpětná cesta k
  poslednímu skutečně úspěšnému průchodu. Přesunuto do `_backup_db_once`,
  volané těsně PŘED prvním `commit_chapter_result`, s příznakem
  `backup_state["done"]` sdíleným napříč kapitolami v jednom běhu.
- **Manuální integrační ověření příliš obecné:** rozšířeno na konkrétní
  checklist (6 položek - executable, `--ephemeral`, stdin, `-m`, `-C`
  izolace, `-o`), aby jediný ruční test nezůstal na úrovni "spusť a
  koukni", co by nekompatibilitu jednoho konkrétního přepínače snadno
  přehlédlo.
- **IMPORTANT - `Popen` chytá jen `FileNotFoundError`, ne širší `OSError`:**
  ověřil jsem si Python sémantiku - `PermissionError` JE `OSError`, ale
  NENÍ `FileNotFoundError` (sourozenecké podtřídy `OSError`, ne jedna
  druhou zahrnuje). Rozšířeno na `except OSError`, přidán test s
  `PermissionError`.
- **Rozhodnutí `guide_block` stale:** ověřil jsem - starý kolo-6 bullet
  a shrnutí tří vrstev (na začátku sekce "Guardrail") pořád popisovaly
  `check_meaning_preserved` jako kontrolu JEN významu, i po kole 7
  přidání registru. Opraveno na obou místech.

### Agreed but already addressed
(žádné nové)

### Vlastní doplněk
- Codexův NIT o `_resolve_codex_cmd` volaném znovu na každou kapitolu byl
  přesný - opraveno DŮSLEDNĚJI, než jen úpravou tvrzení: `codex_cmd` se
  teď SKUTEČNĚ řeší jednou (preflight výsledek se uchová a posílá dál),
  ne jen že se tvrzení v komentáři zjemnilo.

## Claude VERDICT

Po aplikaci 5 IMPORTANT + 5 NITS z kola 8 (žádný nový BLOCKING) a
vlastním sweepu nenacházím nic dalšího.

`CONSENSUS`

## Summary for log

Kolo 8: Codex nenašel žádný nový BLOCKING, ale 5 IMPORTANT (dvě z nich
skutečně substantivní - časování zálohy DB přepisovalo poslední užitečnou
zálohu; `Popen` nechytal širší `OSError` - a tři pokračující próza-vs-kód
nesoulady, potvrzující vzorec z kol 6-7) + 5 NITS. `codex_cmd` teď
skutečně (ne jen podle tvrzení) řešen jen jednou za běh. Design je teď
kompletní - čeká se na kolo 9 Codexu, jestli konečně potvrdí konsensus.
