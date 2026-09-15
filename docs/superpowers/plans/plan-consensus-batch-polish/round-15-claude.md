# Round 15 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `btn-regen` a `revertChapter()` nemají `catch` kolem
  `fetch` - síťová chyba = nezachycená promise rejection, `finally`
  editor odemkne, ale BEZ chybové hlášky.** Ověřeno čtením - potvrzeno,
  oba handlery mají jen `try/finally`, žádný `catch`. Opraveno
  ROZDÍLNĚ podle povahy operace (přesně jak Codex navrhl): regenerace
  je čistě read-only (Task 10 - "NIC nezapisuje do chapters/historie"),
  takže `catch` jen zobrazí chybu do `errBox`, žádná nejistota o stavu.
  Revert NAPROTI TOMU zapisuje - `fetch` výjimka může nastat PŘED
  odesláním (nic se nestalo) NEBO PO serverovém commitu, jen odpověď se
  ztratila cestou zpátky - nejde z ní rozlišit který případ nastal, takže
  `catch` NEPŘEDPOKLÁDÁ "nic se nestalo", ale explicitně přizná nejistotu
  (`alert`) a vynutí `window.location.reload()` PŘED další úpravou.

## Claude VERDICT

CHANGES_NEEDED (1 reálná oprava, žádný vlastní nález)

## Summary for log

Pokračování kola 14 (frontend fetch error handling), teď v editoru
místo chapters.html - stejná třída mezery (chybějící `try/catch` kolem
`fetch`), stejný etablovaný vzor (`loadChapter()`) jako referenční
řešení. Rozlišení read-only (regenerace) vs. zapisující (revert)
operace v odpovědi na chybu je jediný nový nuance tohohle kola.
