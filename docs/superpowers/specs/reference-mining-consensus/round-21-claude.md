# Round 21 — Claude critique

Dva nálezy, oba **důsledky mé opravy z kola 20**. Vzorec „oprava rozbije něco
jiného" pokračuje, jen v čím dál menším měřítku.

## On Codex's points

### Agreed + fixed

- **Krátké povrchy by se nikdy nestaly `proposed`.** V kole 20 jsem povolil
  jedno- a dvouznakovým povrchům jít do stupně 1, ale `books_with_en` si
  ponechal délkové omezení ze stupně 0. `E` by tedy u nich bylo vždy prázdné
  a predikát souvýskytu je nemůže pustit dál. *Oprava:* `books_with_en` hledá
  **bez jakéhokoli délkového omezení**; omezení má jen stupeň 0, kde chrání před
  českými homonymy. Doplněn regresní test.
- **Věta o nezpůsobilém povrchu odporovala precedenci.** Napsal jsem „končí
  nejvýš `evidence_only`", ale precedence dává nenulovému návrhu modelu
  přednost, takže skončí `proposed` / `not_attested`. *Oprava:* nezpůsobilý
  povrch se **nikdy nestane `confirmed` ani `weak`**; skončí podle návrhu
  modelu, nebo `evidence_only`, vrátí-li model `null`.

## Claude's own findings

Žádné.

## Claude VERDICT

CONSENSUS
