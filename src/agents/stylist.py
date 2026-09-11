"""Stylistický průchod přes Codex CLI. Nepřekládá, nemění fakta - jen
učeše plynulost hotové, už schválené české věty.

Codex je obecný kódovací agent, ne jazykový nástroj na míru - jeho výstup
se NIKDY nebere jako důvěryhodný sám o sobě. Volající (main.py _cmd_polish)
musí výsledek znovu prohnat kontrolami: STEJNÝMI, jakými prochází
originální překlad (konkordance + kritik), PLUS DODATEČNÝMI, co originál
nepotřebuje (sekvence čísel, počet odstavců/poměr délky, a CZ-před vs.
CZ-po kontrola zachování významu a rejstříku - originál nemá "před"
verzi k porovnání). To je zde záměrně mimo tenhle modul, aby `stylist.py`
zůstal čistý (jen volání Codexu), bez závislosti na concordance/critic/DB.

Bezpečnostní detaily (kola 1-6, 17-20 a 25 plan-consensus review):
1. Vstup (prompt s EN + celou kapitolou CZ) jde přes STDIN, ne argument
   procesu ani soubor (kolo 4 - ověřeno přímo `codex exec --help`:
   `[PROMPT]` čte ze stdin, když je pozicionální argument `-`) -
   `subprocess.run`/`Popen` s dlouhým textem v argv naráží na limit délky
   příkazové řádky (na Windows ~32 KiB), navíc by byl vidět v seznamu
   procesů. Stdin nemá žádný z těchhle limitů a PŮVODNÍ text kapitoly se
   navíc nezapisuje jako samostatný čitelný soubor (drobný bonus k bodu 5;
   pozor - STYLIZOVANÁ verze se stejně zapíše přes `-o`, viz bod 2, jen
   dočasně a bez záruky bezpečného vymazání. Navíc kolo 27: ZAMÍTNUTÁ
   stylizovaná verze se PERZISTENTNĚ ukládá do report souboru, když
   `config.STYLIST_REPORT_REJECTED_TEXT` - viz `_write_polish_report`
   docstring "BEZPEČNOST").
2. VÝSTUP jde přes `-o out_path`/`--output-last-message` - `codex exec`
   samo zachytí POSLEDNÍ ZPRÁVU agenta a zapíše ji do souboru (capture na
   úrovni CLI, ne akce sandboxovaného procesu - `--sandbox read-only` by
   zápis SAMOTNÉHO agenta blokoval, proto se ho nikdy nežádá, aby cokoli
   zapisoval - kolo 2 nález). Přesně stejný mechanismus jako u
   plan-consensus skillu, ověřeno přímo v tomhle běhu
   (`round-1-codex.md`-`round-4-codex.md` vznikly touhle cestou).
3. `-C` (pracovní adresář) míří na IZOLOVANÝ prázdný dočasný adresář, ne
   na kořen book-translator repa - i v read-only sandboxu čte `codex exec`
   soubory daného adresáře a mohl by sebrat projektové instrukce
   (AGENTS.md apod.), které by ho zmátly o vlastní roli. Se stdin-vstupem
   (bod 1) už tenhle adresář neslouží ke čtení ničeho - jen jako izolovaný
   `-C` kořen a cíl pro `-o`.
4. Executable se hledá přes `shutil.which` - na Windows je Codex CLI
   typicky `codex.cmd`, holé `"codex"` v `subprocess.run(shell=False)`
   často neuspěje (kolo 2 nález).
5. `--ephemeral` (kolo 4 IMPORTANT, ověřeno `codex exec --help`: "Run
   without persisting session files to disk") - Codex CLI si ukládá
   historii relací nezávisle na tom, co uklidí `TemporaryDirectory`. Bez
   `--ephemeral` by text knihy mohl přežít v Codexově vlastní session
   historii i po smazání dočasného adresáře - `--ephemeral` tomu
   předchází přímo u zdroje.
6. `--ignore-user-config` (kolo 17 IMPORTANT, ověřeno přímo `codex exec
   --help`: "Do not load `$CODEX_HOME/config.toml`; auth still uses
   `CODEX_HOME`") - `-C work_dir` izoluje jen PRACOVNÍ ADRESÁŘ, ne
   uživatelův GLOBÁLNÍ Codex config (`~/.codex/config.toml`), který může
   nést libovolné MCP servery a pluginy - ty se BEZ týhle vlajky načtou
   při každém spuštění bez ohledu na `-C`. Dvojí důvod: (a) SPOLEHLIVOST -
   tenhle samotný plan-consensus proces opakovaně narazil na `codex exec`
   viset na startu kvůli MCP serveru v uživatelově globálním configu bez
   vlastního timeoutu (síťový handshake, auth) - stejné riziko by
   `polish` v PRODUKCI zdědilo při KAŽDÉM spuštění; (b) ÚTOČNÁ PLOCHA -
   ignorováním uživatelského configu se nenačtou žádné DALŠÍ MCP nástroje
   nad rámec toho, co `--sandbox read-only` samo povoluje, což zužuje, co
   by prompt injection z textu knihy mohlo zneužít. Autentizace (`auth
   still uses CODEX_HOME`) zůstává funkční - `polish` se dál umí
   přihlásit, jen nenačte pluginy/MCP servery z globálního configu.
   OVĚŘENO PŘÍMO (kolo 17 otevřelo otázku, kolo 18 ji uzavřelo živým
   testem, ne jen čtením `--help`): `--sandbox read-only` DOVOLUJE číst
   LIBOVOLNOU cestu na disku, ne jen `-C` adresář. Přímý test (`codex
   exec --sandbox read-only -C <izolovaný dočasný adresář>` s promptem
   "přečti soubor na <cestě MIMO -C> a vrať přesně jeho obsah") uspěl -
   Codex spustil `Get-Content` na cestě mimo pracovní adresář a vrátil
   přesný obsah souboru. `read-only` tedy omezuje ZÁPISY (na `-C`
   adresář), NE ČTENÍ (to zůstává neomezené na celý souborový systém,
   aspoň na týhle platformě/verzi). Prompt injection z textu knihy by
   TEORETICKY (a teď POTVRZENĚ TECHNICKY MOŽNÉ, ne jen teoreticky) mohla
   nechat Codex přečíst a "vrátit" obsah citlivého souboru jako součást
   stylizovaného textu. `--ignore-user-config` tohle NEŘEŠÍ (jde o rozsah
   ČTENÍ sandboxu, ne o config), jen ho zmírňuje nepřímo (méně MCP
   nástrojů, co by injected prompt mohl přimět něco takového udělat).

   ŘEŠENÍ (kolo 19 BLOCKING, rozhodnutí uživatele/vlastníka projektu):
   `polish` běží JEN za povinným opt-inem `config.STYLIST_ACCEPT_FS_RISK
   = True` (default `False`). ZÁVAZNÁ kontrola je PŘÍMO v `polish()` výš
   (kolo 20 BLOCKING - `polish()` je veřejná funkce, kontrola jen v CLI
   by šla obejít); `_cmd_polish` si nechává vlastní časnou hlášku jen
   jako hezčí UX. Plná OS/kontejnerová sandboxizace nebo přechod na
   neagentní API (kolo 18 navrhlo obojí) je ZDOKUMENTOVANÁ migrační
   cesta pro pozdější iteraci, ne součást tohohle plánu - viz spec
   sekce "Bezpečnostní rozhodnutí (kolo 19)" (v dokumentu NÍŽ), kde je
   i proč jde bezpečně odložit (celé riziko je uvnitř `stylist.polish()`,
   zbytek systému je provider-agnostický). Riziko je OVĚŘENÉ (ne
   domnělé), s povinným canary krokem v "Manuální ověření"."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import config
from src.llm.parsing import extract_json

SYSTEM_PROMPT_TEMPLATE = """Jsi redaktor české prózy. Dostaneš anglický
originál a jeho český překlad. Tvůj JEDINÝ úkol: uprav ČESKÝ text tak, aby
zněl plynuleji a přirozeněji - beze změny významu, faktů, jmen postav,
míst nebo termínů, beze změny počtu odstavců nebo pořadí událostí.

PŘÍSNÁ PRAVIDLA:
- Nesmíš nic přidat, co v překladu není (žádné nové věty, detaily, popisy).
- Nesmíš nic vynechat.
- Nesmíš měnit jména, tituly ani zavedené termíny - i kdyby zněly kostrbatě,
  jsou to schválené, závazné tvary.
- Nesmíš měnit tykání/vykání, hlas vypravěče ani rejstřík postav - drž se
  toho, co je v předchozím textu, i v návodu níže (je-li přiložen).
- Nesmíš měnit žádná čísla, procenta ani data.
- Zachovej přesně stejný počet odstavců jako má český text níže.
- Neupravuj žádné soubory na disku. Tvůj jediný úkol je vrátit text jako
  SVOU ODPOVĚĎ.
- Odpověz POUZE opraveným českým textem kapitoly - žádné vysvětlení,
  žádné poznámky, žádné markdown bloky (```), nic navíc kolem.
{guide_section}
--- ANGLICKÝ ORIGINÁL ---
{en_text}

--- ČESKÝ PŘEKLAD K UPRAVENÍ ---
{cz_text}

Odpověz upravenou verzí ČESKÉHO textu - a jenom jí."""


class StylistError(Exception):
    """Codex selhal, vrátil prázdno, timeoutoval, nebo výstup neprošel
    základní strukturální kontrolou. Volající to bere jako 'stylizace se
    nepovedla', ne jako fatální chybu běhu."""


_LINE_ENDING_RE = re.compile(r"\r\n|\r")


def _paragraph_count(text: str) -> int:
    # Kolo 16 NIT: holé `text.split("\n\n")` nezachytí CRLF konce řádků
    # (`\r\n\r\n` neobsahuje dva `\n` za sebou) ani prázdný řádek s jen
    # mezerami/tabulátory. Normalizace na `\n` + rozdělení regexem
    # (prázdný řádek, i s bílými znaky) je odolnější, i když v týhle
    # konkrétní cestě (LLM API text + `open(..., "r")` s výchozím
    # universal-newlines čtením) je CRLF spíš teoretické riziko.
    normalized = _LINE_ENDING_RE.sub("\n", text)
    return len([p for p in re.split(r"\n[ \t]*\n", normalized) if p.strip()])


# Kolo 6 IMPORTANT - PŘEHODNOCENO (kola 4-5 to odmítala jako "mimo rozsah,
# vlastní NLP úloha"): arabské číslice/procenta jsou levné a spolehlivé
# extrahovat, na rozdíl od plného číselného NLP extraktoru. Zachytí
# přehození číslic ("12"→"21"), které LLM kontroly (kritik i
# check_meaning_preserved) mohou přehlédnout, protože oboje zůstává
# "čitelné". Slovně vypsaná čísla ("pět") záměrně MIMO ROZSAH - detekce by
# vyžadovala jazykový slovník/NLP, přesně to draho.
#
# `[   ]?%?` (ne jen `%?`) - kolo 10 IMPORTANT: česká typografie
# píše "12 %" S MEZEROU před znakem procenta, anglická "12%" bez ní. Bez
# týhle úpravy regex mezeru před "%" vůbec nepovoloval, takže na běžném
# českém textu ("12 %") znak "%" NIKDY nezachytil jako součást čísla -
# kontrola "%" byla na reálném českém textu prakticky mrtvá (ztráta "%"
# by prošla beze změny sekvence). Kolo 11 IMPORTANT rozšířilo mezerové
# znaky ze samotné NBSP (U+00A0) i o úzkou nezalomitelnou mezeru (U+202F) -
# LLM výstup (překladač i stylista) může použít kteroukoli variantu,
# regex musí pokrýt obě, ne jen tu nejběžnější. Znaménko (`-12` → `12`)
# ZÁMĚRNĚ MIMO ROZSAH (kola 10-11) - pomlčka je v běžné próze silně
# přetížená (rozsahy stran "12-14", vsuvky s pomlčkou, spojovník ve
# složenině), takže "opravit" znaménko by riskovalo NOVÉ falešné poplachy
# přesně tam, kde dřív žádné nebyly (např. stylista přepíše "strany 12-14"
# na "strany 12 až 14" - legitimní úprava, co by s naivním "-12"→znaménko
# vyšla jako změna čísla). Stejná filozofie jako slovně vypsaná čísla o pár
# řádků výš - cena falešných poplachů na přetíženém znaku je vyšší než
# přínos zachycení řídkého případu úmyslně otočeného znaménka (to navíc
# pořád hlídá `check_meaning_preserved`, jen ne deterministicky).
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?[ \xa0 ]?%?")


_REDACTED = "(hodnoty potlačeny - config.STYLIST_REPORT_REJECTED_TEXT není True)"


def _redact_detail(detail: str) -> str:
    """Konkrétní hodnoty odvozené z Codexova výstupu (stderr, sekvence
    čísel, počty odstavců, poměr délky, `str(e)` neočekávané výjimky) do
    chybové hlášky JEN za `config.STYLIST_REPORT_REJECTED_TEXT is True`
    (kolo 32-34). Bez toho by je prompt injection mohla použít jako
    covert channel / je nechat perzistovat v `failed`/`error` záznamu
    reportu. `is True` (ne truthiness) - `1`/`"False"`/`None` = redigovat.
    `main.py` (`_cmd_polish` obecný `except`) to volá přes
    `stylist._redact_detail`."""
    return detail if config.STYLIST_REPORT_REJECTED_TEXT is True else _REDACTED


def _number_sequence(text: str) -> list:
    """Vrácí čísla v POŘADÍ VýSKYTU, NESEŘAZENÁ (kolo 13 BLOCKING - dřív
    `_number_multiset` řadila výstup, čímž z kontroly udělala pouhé
    srovnání MNOŽIN. Přehození DVOU RŮZNÝCH čísel mezi dvěma místy v textu
    (např. "3" a "5" prohozené mezi dvěma postavami, nebo den/měsíc
    prohozené v datu - "2026-09-08" → "2026-08-09" dá STEJNOU seřazenou
    množinu {"08","09","2026"} jako originál) by tak prošlo beze
    povšimnutí, přestože jde přesně o tu třídu chyby ("přehození číslic"),
    kterou tahle kontrola má zachytit. Porovnání SEKVENCE (ne množiny)
    tuhle mezeru zavírá - a je to bezpečné, protože `SYSTEM_PROMPT_TEMPLATE`
    výše stylistovi explicitně zakazuje měnit "pořadí událostí" i čísla
    samotná, takže shodná posloupnost čísel je u DODRŽUJÍCÍHO stylisty
    očekávaná, ne jen náhodná shoda.

    DESETINNÝ ODDĚLOVAČ SE NENORMALIZUJE (kolo 14 IMPORTANT, revize kola
    13) - kolo 13 zavedlo normalizaci `,`/`.` s odůvodněním "tečka v už
    přeloženém českém textu je téměř vždy reziduální anglicismus, ne
    záměrně jiná hodnota". Codex v kole 14 dal KONKRÉTNÍ protipříklad,
    co tohle vyvrací: "Python 3.5" (verze softwaru, technický identifikátor,
    ne desetinné číslo) → "Python 3,5" by normalizace tiše PŘIJALA jako
    "jen jinou notaci", přestože jde o VIDITELNÉ poškození technického
    termínu (verzová čísla se v češtině NEpřevádí na desetinnou čárku,
    zůstávají s tečkou jako mezinárodní konvence). Regex `_NUMBER_RE`
    nemá jak rozlišit "desetinné číslo" od "identifikátoru, co vypadá
    jako desetinné číslo" - to by vyžadovalo kontextovou/sémantickou
    analýzu (jaké slovo číslo předchází), přesně tu "drahou NLP úlohu",
    co tenhle deterministický guard záměrně nedělá (viz slovně vypsaná
    čísla/data výš). U bezpečnostní brány je falešné ZAMÍTNUTÍ (stylista
    legitimně opraví "3.5 metru" na "3,5 metru", ale konkordance/
    strukturální kontrola to jednou odmítne jako "změněné číslo",
    kapitola zůstane beze změny) levnější než falešné PŘIJETÍ (skutečná
    korupce identifikátoru tiše projde jako "jen formátování") - proto
    normalizace ZRUŠENA, ne zúžena. Mezerová varianta (obyčejná, NBSP,
    úzká nezalomitelná) před "%" se ODSTRAŇUJE dál (viz komentář u
    `_NUMBER_RE`) - "12 %" a "12%" musí dát STEJNÝ token, jinak by
    legitimní přeformátování mezery prošlo jako falešný poplach; na
    rozdíl od desetinného oddělovače tu neexistuje žádný plausibilní
    identifikátor, kde by mezera před "%" nesla jiný význam."""
    out = []
    for t in _NUMBER_RE.findall(text):
        for space_char in (" ", "\xa0", " "):
            t = t.replace(space_char, "")
        out.append(t)
    return out


def _resolve_codex_cmd(codex_cmd: list) -> list:
    """`codex_cmd[0]` se hledá přes `shutil.which`, jen když je to holé
    jméno bez cesty (testy dávají `sys.executable` - absolutní cestu, tu
    `which` nemusí hledat, stačí ji použít přímo). Chybí-li, `StylistError`
    s jasnou hláškou - ne matoucí `FileNotFoundError` z `subprocess.run`."""
    exe = codex_cmd[0]
    resolved = exe if os.path.isabs(exe) else shutil.which(exe)
    if not resolved:
        raise StylistError(
            f"příkaz {exe!r} nenalezen - je Codex CLI nainstalované a "
            "přihlášené (`codex login`)?")
    return [resolved] + codex_cmd[1:]


# Bezpečnostní přepínače (viz "Bezpečnostní detaily" v `polish` docstringu):
# read-only sandbox, izolovaný `-C`, `--ephemeral` (nepersistovat session),
# `--ignore-user-config` (nenačítat globální MCP/pluginy - kolo 17; ověřený
# důvod SPOLEHLIVOSTI - viset na startu MCP serveru - plus vedlejší zúžení
# útočné plochy). Vstup stdinem (`-`), výstup přes `-o`.
#
# `--ignore-rules` se VĚDOMĚ NEPOUŽÍVÁ (kolo 23 ho přidalo, kolo 25 vrátilo):
# ten flag NEnačte user/project execpolicy `.rules`, čímž útočnou plochu
# ROZŠIŘUJE, ne zužuje - `codex exec` je agentní a shell příkazy SPOUŠTÍ
# (canary test v `polish` docstringu bod 6 - Codex spustil `Get-Content`),
# takže případná restriktivní pravidla `forbidden`/`prompt` v uživatelových
# `.rules` můžou exfiltraci omezit. Kolo-23 zdůvodnění ("stylista nespouští
# shell příkazy, nejrestriktivnější execpolicy") bylo obrácené a věcně chybné.
_CODEX_STATIC_FLAGS = ["exec", "--sandbox", "read-only", "--skip-git-repo-check",
                       "--ephemeral", "--ignore-user-config"]


def _codex_argv(codex_cmd: list, work_dir: str, out_path: str,
                codex_model: str | None) -> list:
    """JEDINÉ místo v PRODUKCI, kde se skládá argv pro `codex exec` (kolo
    19 IMPORTANT - dřív inline v `polish`, tři místa co se rozjížděla).
    Volá to `polish()` a odkazuje "Manuální ověření" canary. Argv test
    (`test_polish_invokes_codex_with_expected_argv`) ho VĚDOMĚ NEVOLÁ -
    má ručně zapsaný oracle, aby zachytil i odstranění `--sandbox
    read-only`/`--ephemeral`/atd. z týhle funkce (kolo 20 IMPORTANT)."""
    argv = list(codex_cmd) + _CODEX_STATIC_FLAGS + ["-C", work_dir, "-o", out_path]
    if codex_model:
        argv += ["-m", codex_model]
    argv.append("-")   # prompt jde stdinem - viz `polish` docstring bod 1
    return argv


def _kill_process_tree(proc) -> None:
    """`subprocess.run(timeout=...)`/`Popen.kill()` na Windows ukončí jen
    PŘÍMÉHO potomka (cmd.exe/codex.cmd wrapper) - `codex.cmd` spouští
    `node.exe` jako DALŠÍHO potomka, který by na timeoutu běžel dál a čerpal
    Codex kvótu (kolo 5 IMPORTANT). `taskkill /T /F` ukončí celý strom
    procesů, ne jen jeden PID.

    Kolo 6 IMPORTANT: `taskkill` může SELHAT (proces mezitím sám skončil,
    nedostatečná oprávnění) - bez fallbacku by volající čekal na proces,
    co se nikdy neukončí. `proc.kill()` jako záchranná síť (ukončí aspoň
    hlavní proces, i když ne nutně celý strom) - lepší než nic.

    Kolo 7 IMPORTANT: `taskkill` sám potřebuje VLASTNÍ timeout - bez něj by
    tahle funkce (volaná právě proto, že něco viselo) mohla sama viset na
    `taskkill`, a fallback na `proc.kill()` by se nikdy nespustil. `timeout=10`
    + `except (TimeoutExpired, OSError)` řeší i tenhle vnořený případ."""
    killed_tree = False
    if sys.platform == "win32":
        try:
            result = subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                    capture_output=True, timeout=10)
            killed_tree = result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            killed_tree = False
    if not killed_tree:
        try:
            proc.kill()
        except OSError:
            pass
