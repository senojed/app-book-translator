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
originál a jeho český překlad. Tvůj úkol: uprav ČESKÝ text tak, aby zněl
plynuleji, přirozeněji a čtivěji - jako profesionálně redigovaná próza, ne
jen opravená hrubka po hrubce. Máš volnost v tom, JAK to řekneš (slovosled,
volba slov, přirozenější idiomy/nadávky, sloučení nebo rozdělení pár vět či
odstavců kvůli plynulosti, drobná úprava rejstříku/tónu, když to sedí lépe
k postavě nebo scéně) - pokud zůstane přesně zachováno, CO to říká a KDO to
říká komu.

PŘÍSNÁ PRAVIDLA (tohle nesmíš porušit, ani ve jménu lepšího stylu):
- Nesmíš nic přidat, co v originále ani v překladu není (žádné nové fakty,
  detaily, popisy, vysvětlení).
- Nesmíš nic vynechat - žádná informace z překladu nesmí zmizet, ani se
  "sloučením" věty ztratit.
- Nesmíš měnit jména, tituly ani zavedené termíny - i kdyby zněly kostrbatě,
  jsou to schválené, závazné tvary. To platí i pro ZKRACOVÁNÍ nebo
  parafrázi zavedeného termínu (např. "čarodějná hůl" na pouhé "hůl",
  "Sedm zákonů magie" na "zákony magie") - i to se počítá jako změna
  termínu, ne jako stylistická drobnost.
- Nesmíš měnit žádná čísla, procenta, data ani jiné konkrétní údaje (váhy,
  teploty, vzdálenosti, časy apod.) - ani přibližně, ani kvůli plynulosti.
- Nesmíš měnit pořadí událostí ani to, kdo co řekl nebo udělal.
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


def polish(en_text: str, cz_text: str, *, timeout: int | None = None,
           codex_cmd: list[str] | None = None,
           codex_model: str | None = None,
           guide_block: str = "") -> str:
    """Vrací upravený český text. Zvedá StylistError při jakémkoli selhání
    NEBO když výstup neprojde levnou strukturální kontrolou (viz níže) -
    volající (main.py) na to reaguje ponecháním původního textu, ne pádem.

    ZÁVAZNÁ bezpečnostní brána (kolo 20 BLOCKING): bez `config.STYLIST_
    ACCEPT_FS_RISK is True` funkce rovnou vyhodí `StylistError` - `codex
    exec` má ověřený neomezený čtecí přístup k disku (bezpečnostní detail
    6 v modulovém docstringu + spec sekce "Bezpečnostní rozhodnutí (kolo
    19)"). Kontrola je TADY, ne jen v `_cmd_polish`, protože tohle je
    veřejná funkce.

    `codex_cmd` jde přepsat v testech (`[sys.executable, str(fake_script)]`)
    - produkční výchozí je `["codex"]` (přes `shutil.which`, viz
    `_resolve_codex_cmd`). Vždy seznam, ne string - string by `subprocess.run`
    vzal jako JEDEN spustitelný soubor s mezerou ve jméně, ne jako "spusť
    python se skriptem jako argumentem".

    `guide_block` (kolo 6 IMPORTANT) - stejný text jako `guide_
    as_prompt_block(guide)`, co dostává translator (`translate_scene` i
    `revise_chapter` v `pipeline.process_chapter`) - NE kritik
    (`pipeline._run_critic` volá `critic.review(en, cz, client)` bez
    návodu, kolo 17 NIT opravuje dřívější nepřesné "translator/kritik",
    ověřeno přímo v `src/pipeline.py`). Stylista bez něj NEVÍ o
    rozhodnutích tykání/vykání, hlasu vypravěče ani rejstříku (EN samo
    tuhle informaci nenese - kritik EN-vs-CZ na to nemá signál), takže by
    ho mohl nepozorovaně změnit. Prázdný string,
    když návod není k dispozici (volitelný parametr, ne tvrdý požadavek).

    Levná STRUKTURÁLNÍ kontrola (počet odstavců, poměr délky, sekvence
    čísel) běží tady, PŘED tím, než se výsledek vůbec vrátí volajícímu -
    je zadarmo (žádné LLM volání) a odchytí hrubé selhání (uťatý/zkrácený
    výstup, přehozená číslice) dřív, než se zaplatí za drahou kritikovu
    kontrolu v `_cmd_polish`. Nenahrazuje kritika (ten hlídá VÝZNAM, ne
    strukturu) - jsou to nezávislé sítě.

    `config.STYLIST_MAX_CHARS` guard (kolo 17 IMPORTANT) - běží HNED, PŘED
    `_resolve_codex_cmd`/samotným voláním Codexu. Extrémně dlouhá kapitola
    by `timeout` (i zvýšený) stejně pravděpodobně vyčerpala, nebo by
    Codex narazil na vlastní kontextový limit modelu - bez týhle kontroly
    by uživatel čekal celý `timeout` nadarmo a dostal jen obecnou
    `StylistError` o timeoutu, ne jasnou zprávu, PROČ to nešlo."""
    # Bezpečnostní opt-in VYNUCEN PŘÍMO TADY (kolo 20 BLOCKING) - ne jen v
    # `_cmd_polish`. `polish()` je veřejná funkce; kontrola jen v CLI
    # obálce by šla obejít přímým voláním. `_cmd_polish` si vlastní
    # časnou hlášku nechává (hezčí UX než N per-kapitolových StylistError),
    # ale JEDINÁ závazná brána je tahle. Testy volající `polish()` přímo
    # musí `config.STYLIST_ACCEPT_FS_RISK` nastavit (autouse fixture).
    if config.STYLIST_ACCEPT_FS_RISK is not True:
        raise StylistError(
            "stylistický průchod je vypnutý: `codex exec` má ověřený "
            "neomezený čtecí přístup k disku, prompt injection z textu "
            "knihy může exfiltrovat citlivý soubor. Nastav "
            "config.STYLIST_ACCEPT_FS_RISK = True, chceš-li to i tak "
            "spustit (viz spec 'Bezpečnostní rozhodnutí (kolo 19)').")
    combined_len = len(en_text) + len(cz_text)
    if combined_len > config.STYLIST_MAX_CHARS:
        raise StylistError(
            f"kapitola je na stylistický průchod moc dlouhá "
            f"({combined_len} znaků EN+CZ, limit "
            f"config.STYLIST_MAX_CHARS={config.STYLIST_MAX_CHARS}) - "
            "přeskakuji, aby se nečekalo na jistý timeout.")
    # Konfigurační invarianty VYNUCENÉ přímo tady (kolo 22 IMPORTANT) -
    # `polish()` je veřejná funkce, nesmí tiše obcházet `_cmd_polish`'s
    # kontroly:
    #  - `codex_cmd`: `None` = "vezmi produkční", `[]` (nebo jiný prázdný)
    #    = chyba volajícího, ne tiché spadnutí na produkční Codex (to by
    #    po opt-inu nečekaně spustilo agenta s přístupem k disku).
    #  - `codex_model`: `None` → `config.CODEX_MODEL`; prázdný = chyba
    #    (auditní záznam MUSÍ znát model, stejně jako u `_cmd_polish`).
    #  - `timeout`: `None` → `config.STYLIST_TIMEOUT_SECONDS` (ne natvrdo).
    if codex_cmd is None:
        codex_cmd = ["codex"]
    if not codex_cmd or not all(codex_cmd):
        raise StylistError("prázdný nebo neúplný codex_cmd - to je chyba "
                           "volajícího, ne důvod spustit produkční Codex.")
    codex_model = ((codex_model if codex_model is not None
                    else config.CODEX_MODEL) or "").strip()
    if not codex_model:
        raise StylistError("chybí model - předej `codex_model` nebo nastav "
                           "config.CODEX_MODEL (audit musí vědět, jaký "
                           "model se použil).")
    # kolo 23 IMPORTANT: `.strip()` se PŘIŘADÍ (ne jen použije k validaci) -
    # jinak by whitespace-padded model prošel a šel s mezerami do `-m`.
    if timeout is None:
        timeout = config.STYLIST_TIMEOUT_SECONDS
    codex_cmd = _resolve_codex_cmd(list(codex_cmd))
    guide_section = (f"\n--- NÁVOD PRO PŘEKLAD (tykání/vykání, hlas, "
                     f"rejstřík - NEPORUŠUJ) ---\n{guide_block}\n"
                     if guide_block else "")
    prompt_text = SYSTEM_PROMPT_TEMPLATE.format(
        en_text=en_text, cz_text=cz_text, guide_section=guide_section)

    # TemporaryDirectory jako context manager (kolo 3 nález) - slouží jako
    # izolovaný `-C` kořen a cíl pro `-o` (VÝSTUP se sem zapíše - vstup jde
    # stdinem, viz docstring bod 1, takže PŮVODNÍ text sem jako soubor
    # nejde; STYLIZOVANÁ verze ano, viz `out_path` níže). TENHLE soubor se
    # po `with` bloku smaže; ZAMÍTNUTÝ výstup ale může skončit v report
    # souboru `main._write_polish_report` (kolo 27, JEN za explicitním
    # opt-inem `config.STYLIST_REPORT_REJECTED_TEXT is True`, default
    # `False`) - to je MIMO tenhle modul.
    with tempfile.TemporaryDirectory(prefix="stylist-") as work_dir:
        out_path = os.path.join(work_dir, "out.txt")

        cmd = _codex_argv(codex_cmd, work_dir, out_path, codex_model)

        try:
            # Popen+communicate, ne subprocess.run (kolo 5 IMPORTANT):
            # subprocess.run(timeout=...) na Windows na timeoutu ukončí jen
            # PŘÍMÉHO potomka (cmd.exe/codex.cmd wrapper) - `codex.cmd`
            # spouští node.exe jako DALŠÍHO potomka, který by běžel dál a
            # čerpal kvótu. `Popen` dá přístup k `.pid`, aby šlo při
            # timeoutu ukončit CELÝ strom přes `_kill_process_tree`.
            #
            # `encoding="utf-8"` EXPLICITNĚ (kolo 5 BLOCKING) - bez něj
            # `text=True` použije lokální kódování OS; na Windows to bývá
            # cp1252, které český prompt (diakritika) nezakóduje a volání
            # spadne na `UnicodeEncodeError` ještě PŘED spuštěním Codexu.
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", cwd=work_dir)
        except OSError as e:
            # Kolo 8 IMPORTANT: `FileNotFoundError` (podtřída `OSError`)
            # nestačí - `PermissionError` (soubor existuje, ale není
            # spustitelný) a další `OSError` varianty by unikly jako
            # neošetřená výjimka mimo `StylistError` kontrakt.
            raise StylistError(
                f"příkaz {codex_cmd!r} se nepodařilo spustit ({type(e).__name__}: "
                f"{e}) - je Codex CLI nainstalované a přihlášené?")
        try:
            stdout, stderr = proc.communicate(input=prompt_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            try:
                # OMEZENÝ wait (kolo 6 IMPORTANT) - i po taskkill/kill se
                # čeká jen konečně dlouho, ne navždy, kdyby ukončení samo
                # selhalo (proces uvízlý v nepřerušitelném stavu apod.).
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass   # udělali jsme, co šlo - nenecháme volajícího viset
            raise StylistError(f"codex exec překročil timeout {timeout}s.")
        except BaseException:
            # Odchylka od specu (plan-consensus kolo 2 IMPORTANT): spec
            # ukončí potomka JEN při TimeoutExpired. KeyboardInterrupt
            # (Ctrl+C) z communicate() by jinak nechal codex.cmd/node.exe
            # běžet dál a čerpat Codex kvótu - stejný problém, kvůli
            # kterému _kill_process_tree existuje.
            _kill_process_tree(proc)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            raise

        if proc.returncode != 0:
            # VŠECHNY chybové hlášky `polish()`, co nesou hodnotu odvozenou
            # z Codexova výstupu (`stderr`, počet odstavců, poměr délky,
            # sekvence čísel), jdou přes `_redact_detail` (kolo 32-34) -
            # bez `STYLIST_REPORT_REJECTED_TEXT is True` uvedou jen
            # generickou náhradu, ne konkrétní hodnoty (prompt injection
            # by je jinak mohla exfiltrovat / použít jako covert channel
            # do `failed` záznamu reportu).
            raise StylistError(
                f"codex exec skončil s kódem {proc.returncode}: "
                f"{_redact_detail(stderr[:500])}")
        if not os.path.exists(out_path):
            raise StylistError(
                "codex exec nevytvořil výstupní soubor (-o) - žádná "
                "poslední zpráva k zachycení.")
        with open(out_path, "r", encoding="utf-8") as f:
            styled = f.read().strip()

    if not styled:
        raise StylistError("codex exec vrátil prázdnou odpověď.")
    # Obrana proti tomu, že model přesto obalí odpověď do markdown bloku
    # navzdory promptu (kolo 4 NIT) - deterministická kontrola, ne spoléhání
    # jen na to, že model poslechne pokyn "žádné markdown bloky".
    if styled.startswith("```") or styled.endswith("```"):
        raise StylistError(
            "odpověď je obalená v markdown bloku (```) navzdory pokynu - "
            "podezřelý formát, radši zamítnout.")

    # Levná strukturální kontrola - viz docstring. Prahy jsou schválně
    # volné (skutečnou kontrolu obsahu dělá až kritik v _cmd_polish) -
    # cílem je odchytit JEN hrubé selhání (uťatý výstup, smazaný obsah).
    # Tolerance na POMĚR, ne přesná rovnost (2026-09-13, volnější polish) -
    # dřívější `!=` tvrdě zahodilo i legitimní sloučení/rozdělení pár
    # odstavců kvůli plynulosti (pilot nález: reálný Codex běh změnil počet
    # odstavců o +1 ze 64/85 - editorská drobnost, ne uťatý výstup). Stejné
    # pásmo jako kontrola délky níž (0.7-1.3, o něco přísnější než 0.5-1.5 -
    # počet odstavců je citlivější signál na useknutí než syrová délka).
    p_before, p_styled = _paragraph_count(cz_text), _paragraph_count(styled)
    p_ratio = p_styled / max(1, p_before)
    if not (0.7 <= p_ratio <= 1.3):
        raise StylistError(
            "počet odstavců se liší příliš "
            f"{_redact_detail(f'({p_styled} vs. {p_before} originál)')}"
            " - podezření na useknutý nebo přepsaný výstup.")
    ratio = len(styled) / max(1, len(cz_text))
    if not (0.5 <= ratio <= 1.5):
        raise StylistError(
            f"délka výstupu se od originálu liší {_redact_detail(f'{ratio:.1f}x')}"
            " - podezření na useknutý nebo přepsaný výstup.")
    # Sekvence arabských číslic (kolo 6 IMPORTANT, revize kol 4-5, ŘAZENÍ
    # odstraněno kolo 13 BLOCKING - viz `_number_sequence` docstring) -
    # levné, deterministické, fail-closed. Zachytí přehození číslic
    # ("12"→"21") I přehození DVOU RŮZNÝCH čísel mezi sebou (na rozdíl od
    # dřívější seřazené verze), co LLM kontroly (kritik,
    # check_meaning_preserved) mohou přehlédnout, protože oboje zůstává
    # "čitelné". Slovně vypsaná čísla mimo rozsah.
    before_nums, after_nums = _number_sequence(cz_text), _number_sequence(styled)
    if before_nums != after_nums:
        # `after_nums` pochází ze STYLIZOVANÉHO textu (Codexův výstup) -
        # přes `_redact_detail` (kolo 33-34).
        raise StylistError(
            "čísla v textu se změnila "
            f"{_redact_detail(f'({before_nums} → {after_nums})')} - "
            "podezření na faktickou změnu, ne jen styl.")
    return styled


MEANING_CHECK_PROMPT = """Dostaneš dvě verze stejného českého textu - PŘED
a PO stylistické úpravě. Posuď DVĚ VĚCI zvlášť:

1. VÝZNAM - fakta, kdo co řekl/udělal, počet/pořadí událostí, jména, čísla.
   Rozdíly ve slovosledu, synonymech nebo plynulosti věty NEJSOU význam -
   ty ignoruj.
2. REJSTŘÍK - tykání/vykání mezi postavami, formálnost oslovení, hlas
   vypravěče (ironický/vážný/atd.). I drobná změna (např. "ty" → "vy" u
   jedné repliky) se počítá.

Vrať POUZE JSON:
{{"meaning_changed": true | false,
 "register_changed": true | false,
 "issue": "stručně co se změnilo (když je aspoň jedno true)"}}

--- PŘED ---
{cz_before}

--- PO ---
{cz_after}"""


def check_meaning_preserved(cz_before: str, cz_after: str, client, *,
                            model=None, max_tokens=None) -> list:
    """Třetí, nezávislá kontrolní síť (kolo 2 nález): `critic.review`
    srovnává EN vs. CZ-po, což nemusí odhalit posun, který je vůči EN
    pořád "obhajitelný", ale liší se od PŮVODNÍHO schváleného výkladu.
    Tahle funkce srovnává přímo CZ-před vs. CZ-po - jiná otázka, jiný
    nález. Od kola 7 kontroluje i REJSTŘÍK (tykání/vykání, hlas vypravěče)
    - prompt sám stylistovi říká, ať registr nemění (viz `guide_block` v
    `polish()`), ale žádná vrstva to dřív VERIFIKOVAT neuměla - kritik na
    to nemá signál (EN sám tykání/vykání nenese) a tahle funkce dřív
    kontrolovala jen VÝZNAM v užším smyslu. Vrací seznam nálezů ve stejném
    tvaru jako `concordance`/`critic` (typ `"meaning_drift"` nebo
    `"register_drift"`), prázdný seznam = beze změny.

    Anthropic volání (přes standardní `client`, ne Codex) - počítá se do
    `llm_calls`/`MAX_SPEND_USD` stejně jako kritik."""
    def _finding(type_, issue):
        return {"source": "stylist_check", "type": type_, "severity": "critical",
                "action": "revise", "term_id": None, "expected": None,
                "actual": None, "cz_excerpt": None, "issue": issue,
                "suggestion": None}

    model = model or config.MODEL_CRITIC
    max_tokens = max_tokens or config.MAX_TOKENS_CRITIC
    prompt = MEANING_CHECK_PROMPT.format(cz_before=cz_before, cz_after=cz_after)
    comp = client.complete(system="Jsi přesný, střízlivý korektor významu a rejstříku.",
                           user=prompt, max_tokens=max_tokens, model=model)
    if comp.truncated:
        return [_finding("meaning_drift",
                         "kontrola zachování významu/rejstříku useknutá - bereme jako selhání.")]
    try:
        data = extract_json(comp.text)
    except ValueError:
        return [_finding("meaning_drift",
                         "kontrola zachování významu/rejstříku vrátila nečitelnou odpověď - bereme jako selhání.")]
    # `isinstance(..., bool)`, NE `in (True, False)` (kolo 9 IMPORTANT) -
    # v Pythonu `0 == False` a `1 == True`, takže `0 in (True, False)` je
    # `True`. Odpověď `{"meaning_changed": 0}` (model vrátil číslo místo
    # JSON boolu) by tak prošla jako platné "false", i když jde o jiný typ,
    # než jaký prompt žádá - `isinstance` tenhle gap zavírá.
    if not isinstance(data, dict) or not isinstance(data.get("meaning_changed"), bool) \
            or not isinstance(data.get("register_changed"), bool):
        issue = (data.get("issue") if isinstance(data, dict) else None) or \
                "kontrola zachování významu/rejstříku vrátila neplatný tvar - bereme jako selhání."
        return [_finding("meaning_drift", issue)]
    out = []
    if data["meaning_changed"]:
        out.append(_finding("meaning_drift", data.get("issue") or "změnil se význam."))
    if data["register_changed"]:
        out.append(_finding("register_drift", data.get("issue") or "změnil se rejstřík/oslovení."))
    return out
