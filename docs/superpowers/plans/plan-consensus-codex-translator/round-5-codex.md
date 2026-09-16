## IMPORTANT

- Task 3, `CodexLLMClient.complete()` — vrací `input_tokens=0, output_tokens=0` pro každé úspěšné volání. Audit i `_print_usage()` pak falešně vykážou nulový objem, přestože klient má vlastní konzervativní odhad vstupu. Oprava: do `Completion` ukládat explicitně zdokumentované odhady vstupu i výstupu (`len(text)//2`); doplnit test auditního řádku s nenulovými odhady a nulovou cenou.

## NITS

- Task 2 — chybí test, že oba translator prompty skutečně obsahují `===KONEC===`. Parser-testy nezachytí regresi, kdy se kontrola ponechá, ale instrukce modelu se omylem vynechá.

## VERDICT
CHANGES_NEEDED