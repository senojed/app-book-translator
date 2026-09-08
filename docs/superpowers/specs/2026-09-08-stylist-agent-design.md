# Stylistický průchod přes Codex - design

## Kontext a cíl

Pilotní běh (Turn Coat, kap. 1-3) ukázal: překlad je věcně správný a
konzistentní (glosář, konkordance, kritik to hlídají), ale čeština je místy
neobratná/krkolomná. Uživatel má zkušenost, že OpenAI modely (Codex) píší
plynulejší českou prózu než současný translator (Claude). Cíl: přidat
volitelný krok, který HOTOVÝ, už schválený překlad kapitoly stylisticky
učeše - beze změny faktů, jmen, termínů nebo struktury děje.

Riziko, které to musí zvládnout: Codex jako obecný kódovací agent má sklon
"halucinovat" - přidávat, měnit nebo mazat obsah, když dostane volnou ruku.
Řešení: stylizace se nikdy nepřijme naslepo, vždy prochází stejnou
kontrolou (konkordance + kritik), jakou prochází původní překlad. Neprojde-li,
zahodí se a použije se původní text.

## Mimo rozsah

- Žádná změna translator/critic/revizní smyčky - stylista běží AŽ PO ní, na
  kapitolách se `status == "done"`.
- Žádné opakování/retry stylisty samotného - jeden pokus na kapitolu, selže-li
  (timeout, prázdný výstup, zamítnutí kontrolou), kapitola zůstává beze
  změny a lze to zkusit znovu příštím spuštěním `polish`.
- Žádné dělení kapitoly na scény pro stylistu - jede na celou kapitolu
  najednou (na rozdíl od translatoru, který pracuje po scénách).
- Žádná migrace DB schématu - žádný nový sloupec, jen existující
  `translated_text`/`notes` přes `state.update_chapter`.
- Žádné napojení na `MAX_SPEND_USD`/`llm_calls` - Codex je jiný poskytovatel
  s jiným účtováním (uživatelův vlastní Codex plán/kvóta), sleduje se jen
  počet volání a úspěšnost, ne cena v USD.

## Architektura

Nový modul `src/agents/stylist.py`, nový CLI příkaz `python main.py polish`.
Žádný zásah do `src/pipeline.py` ani `process_chapter` - stylista je
samostatný, po běhu `run` spustitelný krok, ne součást hlavní smyčky.

```
python main.py run       # scout → translator → kritik → revize (jako dnes)
python main.py polish    # NOVÉ: nad status=="done" kapitolami, volitelné
```

### `src/agents/stylist.py`

```python
"""Stylistický průchod přes Codex CLI. Nepřekládá, nemění fakta - jen
učeše plynulost hotové, už schválené české věty.

Codex je obecný kódovací agent, ne jazykový nástroj na míru - dostane
přísný prompt (jen text, žádné soubory, žádné vysvětlení) a jeho výstup se
NIKDY nebere jako důvěryhodný sám o sobě. Volající (main.py _cmd_polish)
musí výsledek znovu prohnat stejnou kontrolou (concordance + critic), jakou
prochází originální překlad - to je zde záměrně mimo tenhle modul, aby
`stylist.py` zůstal čistý (jen volání Codexu), bez závislosti na
concordance/critic/DB.
"""
import subprocess
import tempfile
import os

SYSTEM_PROMPT_TEMPLATE = """Jsi redaktor české prózy. Dostaneš anglický
originál a jeho český překlad. Tvůj JEDINÝ úkol: uprav ČESKÝ text tak, aby
zněl plynuleji a přirozeněji - beze změny významu, faktů, jmen postav,
míst nebo termínů, beze změny počtu odstavců nebo pořadí událostí.

PŘÍSNÁ PRAVIDLA:
- Nesmíš nic přidat, co v překladu není (žádné nové věty, detaily, popisy).
- Nesmíš nic vynechat.
- Nesmíš měnit jména, tituly ani zavedené termíny - i kdyby zněly kostrbatě,
  jsou to schválené, závazné tvary.
- Nepiš ŽÁDNÝ text kolem - žádné vysvětlení, žádné poznámky, žádné markdown
  bloky (```). Vrať POUZE opravený český text kapitoly, nic jiného.
- Neupravuj žádné soubory na disku. Tvůj výstup je jen text, co vrátíš.

--- ANGLICKÝ ORIGINÁL ---
{en_text}

--- ČESKÝ PŘEKLAD K UPRAVENÍ ---
{cz_text}

Vrať upravenou verzi ČESKÉHO textu."""


class StylistError(Exception):
    """Codex selhal, vrátil prázdno, nebo timeoutoval. Volající to bere
    jako 'stylizace se nepovedla', ne jako fatální chybu běhu."""


def polish(en_text: str, cz_text: str, *, timeout: int = 180,
           codex_cmd: str = "codex") -> str:
    """Vrací upravený český text. Zvedá StylistError při jakémkoli selhání -
    volající (main.py) na to reaguje ponecháním původního textu, ne pádem.

    `codex_cmd` jde přepsat v testech (fake skript) - produkční výchozí je
    `"codex"` z PATH.
    """
    prompt = SYSTEM_PROMPT_TEMPLATE.format(en_text=en_text, cz_text=cz_text)
    fd, out_path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        result = subprocess.run(
            [codex_cmd, "exec", "--sandbox", "read-only",
             "--skip-git-repo-check", "-o", out_path, prompt],
            capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise StylistError(
                f"codex exec skončil s kódem {result.returncode}: "
                f"{result.stderr[:500]}")
        with open(out_path, "r", encoding="utf-8") as f:
            styled = f.read().strip()
        if not styled:
            raise StylistError("codex exec vrátil prázdný výstup.")
        return styled
    except subprocess.TimeoutExpired:
        raise StylistError(f"codex exec překročil timeout {timeout}s.")
    except FileNotFoundError:
        raise StylistError(
            f"příkaz '{codex_cmd}' nenalezen - je Codex CLI nainstalované "
            "a přihlášené?")
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass
```

**Poznámka k `-o out_path` vs. čtení stdout:** stejný vzor jako
plan-consensus skill - Codexův finální text se zapíše do souboru, ne se
parsuje ze stdout (tam jde i debug/progress výstup agenta). Robustnější pro
delší text (celá kapitola, ne jen krátká kritika).

## Guardrail: `_cmd_polish` v `main.py`

```python
def _cmd_polish(args) -> int:
    from src.agents import stylist
    db = config.DB_PATH
    idxs = args.only
    chapters = (state.chapters_by_status(db, ("done",)) if not idxs
                else [c for c in state.chapters_by_status(db, ("done",))
                      if c["idx"] in idxs])
    if not chapters:
        print("Žádné kapitoly ve stavu 'done' k vylepšení.")
        return 0

    glossary_rows = glossary.all_terms(db)
    cf = _client_factory(state.create_run(db, "polish"), interactive=False)
    polished, rejected, failed = 0, 0, 0
    for c in chapters:
        idx, en, cz = c["idx"], c["raw_text"], c["translated_text"]
        try:
            styled = stylist.polish(en, cz)
        except stylist.StylistError as e:
            print(f"Kapitola {idx}: stylista selhal ({e}), ponechávám původní.")
            failed += 1
            continue

        # STEJNÁ kontrola jako u původního překladu - žádná výjimka.
        findings = concordance.check_chapter(en, styled, glossary_rows, [])
        critic_findings, critic_failed = pipeline._run_critic(en, styled, cf("critic"))
        findings += critic_findings
        if critic_failed or pipeline.has_revise_triggers(findings):
            print(f"Kapitola {idx}: stylizace zamítnuta kontrolou, ponechávám původní.")
            rejected += 1
            continue

        state.update_chapter(db, idx, translated_text=styled)
        print(f"Kapitola {idx}: vylepšeno.")
        polished += 1

    print(f"Vylepšeno: {polished}, zamítnuto kontrolou: {rejected}, "
          f"selhalo: {failed}")
    return 0
```

Registrace v `_build_parser()`:

```python
p_pol = sub.add_parser("polish", help="stylistický průchod přes Codex (nad hotovými kapitolami)")
p_pol.add_argument("--only", nargs="+", type=int, default=None,
                   help="jen tyhle kapitoly (musí být status=='done')")
p_pol.set_defaults(func=_cmd_polish)
```

A přidat `"polish"` do `_MUTATING` (drží zámek, mění `data/`).

`pipeline._run_critic` už existuje a je přesně to, co polish potřebuje -
volá se modulově-kvalifikovaně (`pipeline._run_critic`), žádná duplikace
kódu kritika.

## Testování

`stylist.polish()` se testuje s `codex_cmd` ukazujícím na fake skript
(žádné reálné volání Codexu v testech - stejný princip jako `FakeLLMClient`
u Anthropic agentů):

```python
def test_polish_returns_output_file_contents(tmp_path, monkeypatch):
    fake = tmp_path / "fake_codex.py"
    fake.write_text(
        "import sys\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "open(out, 'w', encoding='utf-8').write('Stylizovany text.')\n")
    result = stylist.polish("EN text", "CZ text",
                            codex_cmd=f"{sys.executable} {fake}")
    # POZOR: subprocess.run bere command jako list - fake_cmd s mezerou
    # (python + skript) potřebuje shlex.split nebo rozdělit na dva prvky;
    # doladí se v implementaci (Task plánu), tady jde o princip testu.
    assert result == "Stylizovany text."


def test_polish_raises_on_nonzero_exit(tmp_path):
    fake = tmp_path / "boom.py"
    fake.write_text("import sys; sys.exit(1)")
    with pytest.raises(stylist.StylistError):
        stylist.polish("EN", "CZ", codex_cmd=f"{sys.executable} {fake}")


def test_polish_raises_on_empty_output(tmp_path):
    fake = tmp_path / "empty.py"
    fake.write_text("pass")   # nezapíše nic do -o souboru
    with pytest.raises(stylist.StylistError):
        stylist.polish("EN", "CZ", codex_cmd=f"{sys.executable} {fake}")


def test_polish_raises_on_timeout(tmp_path):
    fake = tmp_path / "slow.py"
    fake.write_text("import time; time.sleep(5)")
    with pytest.raises(stylist.StylistError, match="timeout"):
        stylist.polish("EN", "CZ", codex_cmd=f"{sys.executable} {fake}", timeout=1)


def test_polish_raises_on_missing_command():
    with pytest.raises(stylist.StylistError, match="nenalezen"):
        stylist.polish("EN", "CZ", codex_cmd="prikaz-co-neexistuje-xyz")
```

`_cmd_polish` se testuje monkeypatchnutím `stylist.polish` (fake funkce
vracející pevný text) a `pipeline._run_critic`/`concordance.check_chapter`
- stejný vzor jako existující `tests/test_cli.py`. Klíčové scénáře:

- stylista vrátí text bez nových `revise` nálezů → `translated_text` se
  změní, `polished == 1`.
- stylista vrátí text, kde kritik/konkordance najde `revise` nález →
  `translated_text` zůstává původní, `rejected == 1`.
- `stylist.polish` zvedne `StylistError` → `translated_text` zůstává
  původní, `failed == 1`.
- kapitola se `status != "done"` (např. `flagged`) se do zpracování vůbec
  nedostane, i když je zadaná v `--only`.
- `--only` bez odpovídající `done` kapitoly → nic se nezpracuje, `polished
  == 0`, žádná chyba.

## Chybové stavy a jejich zpracování

| Stav | Reakce |
|---|---|
| Codex CLI není nainstalované/přihlášené | `StylistError`, kapitola beze změny, pokračuje se další |
| Codex timeoutuje | `StylistError`, kapitola beze změny |
| Codex vrátí prázdný text | `StylistError`, kapitola beze změny |
| Codex vrátí text s `revise` nálezem (halucinace/změna obsahu) | zahozeno, kapitola beze změny |
| Codex vrátí jen `note`/`question` nálezy (drobnosti) | **přijato** - stejné pravidlo jako u hlavního `has_revise_triggers`, jen `revise` blokuje |
| `--only` míří na kapitolu, co není `done` | tiše přeskočena (není v seznamu ke zpracování) |

## Otevřené otázky pro plan-consensus

- Má `polish` být idempotentní (spustitelný opakovaně na už vylepšené
  kapitole), nebo má nějak značit "už stylizováno", aby se neplýtvalo
  Codex voláními na kapitole, která už prošla? (Tenhle draft to neřeší -
  bez značky by opakovaný `polish` pokaždé poslal kapitolu znovu.)
- Má `_run_critic`'s `client_factory("critic")` u `polish` používat STEJNÝ
  `run_id`/`_client_factory` jako běžný `run`, nebo samostatný typ běhu
  (`state.create_run(db, "polish")`, jak návrh výše počítá)?
