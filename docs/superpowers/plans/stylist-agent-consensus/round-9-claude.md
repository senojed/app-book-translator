# Round 9 — Claude critique

Codex: CHANGES_NEEDED (1 IMPORTANT).

## Claude's own findings
Žádné nové vlastní.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `guide_block` předání netestováno (spec 2520-2523):** `_polish_env` vždy mockuje `guide_as_prompt_block` → `""`; fake Codex testy kontrolují jen CZ text. Odstranění `guide_block` / `{guide_section}` by prošlo. Návod nese schválená pravidla rejstříku (tykání/vykání) - stylista bez něj může registr nepozorovaně změnit. **Fix:**
  - Task 5: `test_polish_forwards_guide_block_into_prompt` - fake skript asserty `'NEPORUS-VYKANI-XYZ' in received` (stdin); když chybí, fake exit 1 → StylistError → test selže.
  - Task 12: `test_cmd_polish_passes_nonempty_guide_block` - mock `guide_as_prompt_block` na reálný string, spy na `stylist.polish` `guide_block` kwarg.
  - "executor doplní" zrušeno pro tenhle bod.

### Disagreed
Žádné.

## Claude VERDICT

`CHANGES_NEEDED` - 1 IMPORTANT (chybějící test klíčové rejstříkové cesty), aplikováno. Vlastních 0.

## Summary for log

Kolo 9: Codex 1 IMPORTANT - `guide_block` předání netestované, odstranění by prošlo. +test v Task 5 (stdin) i Task 12 (kwarg spy). Sporné: 0. 0 BLOCKING 6 kol. IMPORTANT výhradně "chybí test X" - designové díry vyčerpané.
