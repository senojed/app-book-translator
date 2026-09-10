## IMPORTANT

- **Task 12, Step 3.1 — oprava přerušení stále ztrácí záznam.** Pokud `_polish_one_chapter` vyhodí běžnou výjimku a Ctrl+C přijde během `_say(...)` v `except Exception`, `rec` je stále `None`. Sousední `except KeyboardInterrupt` výjimku z handleru nezachytí; `finally` nic nepřidá. Nový test ověřuje pouze normální návraty, takže tuto mezeru neodhalí. **Oprava:** obalit také zpracování výjimek vnějším KI handlerem; pokud `rec` dosud neexistuje, sestavit jej podle stavu DB. Přidat deterministický test: helper vyhodí `ValueError`, následný `_say` jednorázově vyhodí `KeyboardInterrupt`; report musí obsahovat právě jeden záznam kapitoly.

- **Task 13, Step 2 — přímé ověření nemá timeout ani ukončení stromu procesů.** Právě kontrolovaný problém „hang při startu MCP“ může ověřovací proces neomezeně zablokovat; přímé volání obchází cleanup z `stylist.polish`. **Oprava:** předepsat konkrétní runner s `Popen`, explicitním UTF-8, `cwd=T1`, časovým limitem a `_kill_process_tree` + omezeným `wait` při timeoutu/přerušení. Zachovat dostupné logy pro kontrolu.

## NITS

- **Task 12, Step 3.1 — identitní stráž je zbytečná a zdůvodnění nesprávné.** `finally` neběží dvakrát kvůli normálnímu průchodu a re-raise. Existuje jediný append, takže `report[-1] is not rec` nic neopravuje a odporuje požadavku „žádný dedup“. Odstranit stráž i komentář.

- **Task 13, Step 3 — chybí legitimní výsledek `unchanged`.** Spec jej explicitně podporuje; skutečný model může vrátit totožný text. Uznat jej jako úspěšné ověření této větve. Pokud je nutné živě ověřit také kontroly a commit, předepsat další vhodnou kapitolu, nikoli považovat `unchanged` za chybu implementace.

## VERDICT
CHANGES_NEEDED