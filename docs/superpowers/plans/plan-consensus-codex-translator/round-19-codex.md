## IMPORTANT

- Task 6, ř. 2879–2904: Bash smoke postup nastavuje `BOOK_TRANSLATOR_PROJECT_DIR` jen inline pro tři příkazy. Následně požadovaný `python main.py polish --only <idx>` nemá explicitní prefix, takže snadno poběží nad ostrým `data/state.sqlite3`. Přidej přímo do Bash bloku `BOOK_TRANSLATOR_PROJECT_DIR=/tmp/codex-translator-smoke python main.py polish --only <idx>`.

## NITS

- Task 5, ř. 2633–2636: Při `run --translator codex` hláška z `_polish_preflight()` říká „polish je vypnutý“. Zaveď neutrální zprávu pro Codex backend nebo parametrizuj kontext preflightu.

CHANGES_NEEDED