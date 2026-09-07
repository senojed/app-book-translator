# Round 20 — Claude critique

Dva nálezy, oba správné, oba jemné - známka blížící se konvergence.

## On Codex's points

### Agreed + fixed (BLOCKING)

- **Podmínky způsobilosti šlo splnit různými výskyty.** Napsal jsem je jako
  nezávislé („alespoň jeden výskyt shodný ve velikosti písmen" **a** „u krátkých
  povrchů výskyt mimo začátek věty"), takže u `Mab` by stačil jeden správně
  psaný výskyt na začátku věty plus nesouvisející `mab` uprostřed - každá
  podmínka splněná jiným místem, dohromady falešné potvrzení.
  *Oprava:* podmínky musí splnit **tentýž výskyt**. Doplněn kombinovaný regresní
  test na obě varianty.

### Agreed + fixed (IMPORTANT)

- **Rozpor u povrchů kratších než 3 znaky.** Tabulka je posílala rovnou do
  `unresolved`, precedence z nich při návrhu modelu dělala
  `proposed`/`not_attested`. Sjednoceno: ve **stupni 0 se nehledají** (žádný
  důkaz), do **stupně 1 jdou normálně** - model může zavedený tvar znát
  i u dvouznakového jména. Tabulka opravena na „stupeň 0 nic nedoložil **a**
  model nenavrhl nic".

## Claude's own findings

Žádné.

## Claude VERDICT

CONSENSUS
