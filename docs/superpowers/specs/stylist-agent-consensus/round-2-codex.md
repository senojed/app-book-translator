## BLOCKING

- `stylist.polish`, ř. 154–177: Codex má `--sandbox read-only`, ale má vytvořit `out.txt`. Agent zápis nedostane povolení, takže produkční běh skončí „nezapsal výstupní soubor“. Fix: použít CLI volbu `-o/--output-last-message <out_path>` a požadovat opravený text jako finální odpověď; případně přesně omezený zapisovatelný sandbox.
- `stylist.polish`, ř. 149: výchozí `["codex"]` na cílových Windows nefunguje přes `subprocess.run(..., shell=False)`. Zde je instalace dostupná jako `codex.cmd`; přímé spuštění `codex` končí `FileNotFoundError`. Fix: výchozí executable získat přes `shutil.which("codex")`, uložit absolutní cestu a přidat test Windows rozlišení.
- Testy, ř. 391–403: oba pozitivní testy odporují kontrole poměru délky 0,5–1,5. První výstup je více než dvojnásobný, druhý vrací `"OK"` proti textu přes 32 KiB. Oba musí vyhodit `StylistError`, takže navržená sada nemůže projít. Fix: fake musí vracet text stejné struktury a přibližné délky; test dlouhého argv může například opsat český vstup z `prompt.txt`.

## IMPORTANT

- Guardrail, ř. 321–324: kritik dostává pouze EN originál a nový CZ text. Nekontroluje rozdíl proti původnímu schválenému CZ textu, takže neumí spolehlivě poznat přidanou, odstraněnou či změněnou interpretaci, která je vůči EN stále obhajitelná. Fix: samostatná kontrola dostávající `EN + CZ před + CZ po` a explicitně hodnotící pouze významové změny; jakákoli nejistota musí vést k zamítnutí.
- `_cmd_polish`, ř. 306–334: per-kapitolový `try` obaluje jen `stylist.polish`. Výjimka z konkordance, tvorby mentions nebo commitu ukončí celou dávku, což odporuje komentáři, tabulce chybových stavů a testovacím požadavkům. Fix: přesně vymezit celý per-kapitolový blok a rozlišit obnovitelné chyby od DB/infrastrukturních chyb, které mají být fatální.
- `_cmd_polish`, ř. 302–342: `FatalRunError` z kritika nebo cost guardu není obsloužen jako v `_cmd_run`; unikne z CLI s tracebackem. Fix: přidat vnější `except FatalRunError`, vypsat stručnou chybu, vrátit nenulový kód a ponechat `finish_run(..., "fatal")`.
- Konfigurace a audit, ř. 60 a 364–368: při `CODEX_MODEL=None` marker ukládá pouze `"výchozí"`. To neumožňuje později zjistit použitý model a přímo odporuje tvrzení, že audit zůstane dohledatelný při změně defaultu CLI. Fix: vyžadovat explicitní model nebo získat a uložit skutečný model spolu s verzí Codex CLI.
- Testovací strategie: všechny testy mockují samotné CLI, takže nezachytí oba produkční problémy s executable a sandboxem. Fix: přidat platformní preflight/smoke test ověřující nalezení CLI, podporu použitých voleb a zápis přes CLI-managed output.

## NITS

- `_already_styled`, ř. 252–257: validní JSON objekt místo seznamu způsobí `AttributeError`. Ověřit `isinstance(findings, list)` a ignorovat položky, které nejsou objekty.
- `_cmd_polish`: po běhu chybí `_print_usage(db, rid)`, přestože kritik se účtuje do `llm_calls`. Doplnit stejné vyúčtování jako u `run`.
- Cesty vložené do přirozeného promptu nejsou ohraničené a testovací regex nezvládá mezery. Po přechodu na `--output-last-message` ponechat v promptu pouze jednoznačně označenou cestu ke vstupu.

## VERDICT

CHANGES_NEEDED