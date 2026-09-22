## IMPORTANT

- `Spec` / Task 2 — design spec stále říká, že `subprocess.TimeoutExpired` je fatální a popisuje `subprocess.run`, zatímco plán správně vyžaduje nefatální timeout a `Popen` + kill process tree. Spec je explicitně uveden jako součást plánu, takže implementátor může zvolit chybnou variantu. Oprava: v Task 2 aktualizovat design spec na finální kontrakt včetně timeoutu, konstruktoru s `claude_cmd` a stdin uživatele.

## VERDICT

CHANGES_NEEDED