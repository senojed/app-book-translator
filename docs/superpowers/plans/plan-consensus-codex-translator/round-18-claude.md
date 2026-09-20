# Round 18 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexova bodu)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`mentions=[]` v kolo-13's fatal-commit větvi maže
  existující mentions):** Souhlasím a ověřil jsem přesně - `state.
  commit_chapter_result()` (`src/state.py:660`) dělá `DELETE FROM
  term_mentions WHERE chapter_idx=?` BEZPODMÍNEČNĚ, PŘED vložením
  `mentions` parametru, bez ohledu na jeho obsah. Pro kapitolu, co se
  překládá PRVNÍKRÁT, žádné existující mentions nejsou (moje kolo-13
  tvrzení "jen bez nových mentions" bylo v tomhle případě neškodné) -
  ALE pro `--retry-flagged` kapitolu, co UŽ MĚLA mentions z dřívějšího
  úspěšného commitu, teď probíhajícího fatálního selhání revize, by
  `mentions=[]` ty existující NENÁVRATNĚ smazal, i když `translated_
  text` zůstal (díky kolo-13's fixu) zachovaný - tvrzení bylo FAKTICKY
  nepřesné, ne jen zjednodušení.

  **Oprava:** `mentions` se DETERMINISTICKY znovu sestaví ze
  zachovaného `cz` a existujícího glosáře (`concordance.build_mentions
  (en, cz, glossary_rows, rendered)`) - STEJNÉ volání, co normální
  "transakce B" prep používá pár řádků níž v tomtéž souboru, jen bez
  `new_candidates` (ty se v tomhle zkráceném, fatálním-přerušení-
  commitu vědomě nedohánějí). Přidán regresní test s existujícím
  glosářovým termínem/mentionem, co ověřuje jeho zachování PO fatální
  chybě.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 18: jeden IMPORTANT bod, ale přesný a dobře odůvodněný - kolo-13's
fatal-commit větev poslala `mentions=[]`, což jsem popsal jako
neškodné zjednodušení ("jen bez nových mentions"), ale
`commit_chapter_result()`'s bezpodmínečný DELETE znamená, že to je ve
skutečnosti DESTRUKTIVNÍ pro `--retry-flagged` scénář s existujícími
mentions. Opraveno deterministickým znovusestavením mentions ze
zachovaného překladu a existujícího glosáře, reuse stejného volání,
co normální commit cesta používá.
