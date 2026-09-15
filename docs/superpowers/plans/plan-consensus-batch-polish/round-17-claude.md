# Round 17 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **BLOCKING - `_polish_one_chapter`'s `except FatalRunError as fe:
  raise FatalRunError(...)` (main.py:620-624, existující kód) PŘEBALUJE
  `LockLostError` na obyčejný `FatalRunError` - typ se ztrácí, kolo-16
  fix (`except main.LockLostError` v regenerate endpointu) by ho NIKDY
  nechytil.** Ověřeno čtením main.py - potvrzeno. Přidán `except Lock
  LostError: raise` PŘED `except FatalRunError as fe:` (specifičtější
  klauzule musí být první). CLI cesta beze změny (podtřída, `except
  FatalRunError` ji pořád chytá). Codex navíc správně upozornil, že MŮJ
  kolo-16 test mockoval `_polish_one_chapter` tak, aby `LockLostError`
  vyhodilo PŘÍMO - obcházel tak přesně tenhle bug. Test PŘEPSÁN na
  reálný běh přes `_polish_one_chapter` → `PipelineLLMClient.complete()`
  (skutečný `AnthropicClient` nahrazen `FakeLLMClient`, `require_lock`
  vrací `True` jen napoprvé).

- **IMPORTANT - `POST /api/findings/resolve`'s `scope="history"` větev
  edituje `polish.history.json` NEZÁVISLE na `chapters.notes`, ale UI/
  report čtou VÝHRADNĚ notes - endpoint vrátí 200, nic viditelného se
  nezmění, možná DIVERGENCE `resolved` hodnot.** Ověřeno grepem - ŽÁDNÝ
  prvek frontendu (`toggleResolved`, editor.html) `scope: 'history'`
  nikdy neposílá, natvrdo vždy `'notes'` - historie-scope byla mrtvý
  kód od začátku. Odstraněno (Codexova první navržená alternativa,
  jednodušší než atomicky provazovat dvě nezávislé úložiště) - endpoint
  teď akceptuje JEN `scope="notes"`, `else` větev (history) smazána,
  test přepsán na ověření 400 pro `scope="history"`. `scope` pole v
  payloadu ZŮSTÁVÁ kvůli vpřed kompatibilitě kontraktu.

## Claude VERDICT

CHANGES_NEEDED (souhlas s oběma body, plná implementace)

## Summary for log

Kolo 17 odhalilo, že kolo-16 fix byl NEÚPLNÝ (existující, nedotčený kód
uvnitř `_polish_one_chapter` LockLostError identitu přebaloval pryč) -
a že MŮJ VLASTNÍ test tenhle bug maskoval mockem, co obcházel právě tu
cestu, co selhávala. Druhý bod (dead code scope="history") je první
"najdi a smaž nepoužívanou funkčnost" nález v týhle sérii kol - přímý
YAGNI případ, ne bug fix.
