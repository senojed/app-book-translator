"""Centrální konfigurace. API klíč z env (nebo z .env). Model IDs a ceny jsou
tady, ne v logice."""
import os


def _load_dotenv(path: str, env=None) -> None:
    """Doplní chybějící proměnné ze souboru .env. Skutečné prostředí vyhrává -
    .env je jen pohodlný fallback, ne přepisovač.

    Vlastní mini-parser, aby projekt nepotřeboval další závislost.
    Umí: komentáře, prázdné řádky, `export FOO=bar`, uvozovky, mezery kolem =.
    """
    env = os.environ if env is None else env
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        if not name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env.setdefault(name, value)


# .env hledáme vedle tohoto souboru, ne v aktuálním adresáři - CLI se pouští
# odkudkoli. Načítá se při importu, tedy dřív než se čte ANTHROPIC_API_KEY.
_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

DATA_DIR = "data"
OUTPUT_DIR = "output"
DB_PATH = os.path.join(DATA_DIR, "state.sqlite3")
GUIDE_PATH = os.path.join(DATA_DIR, "guide.json")
GUIDE_DRAFT_PATH = os.path.join(DATA_DIR, "guide.draft.json")
LOCK_PATH = os.path.join(DATA_DIR, ".book-translator.lock")
OUTPUT_TXT = os.path.join(OUTPUT_DIR, "kniha_cz.txt")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_MAX_RETRIES = 8

# Před pilotem ověřit proti Anthropic docs (model active? ceny? limity?).
MODEL_SCOUT = "claude-sonnet-5"
MODEL_TRANSLATOR = "claude-sonnet-5"
MODEL_CRITIC = "claude-sonnet-5"

# $/MTok - vstup / výstup, per model. Cost guard čte odtud.
PRICE_IN_PER_MTOK = {"claude-sonnet-5": 2.0}
PRICE_OUT_PER_MTOK = {"claude-sonnet-5": 10.0}

MAX_TOKENS_SCOUT = 16000
MAX_TOKENS_TRANSLATOR = 16000
MAX_TOKENS_CRITIC = 4000

MAX_REVIZE = 2
CHAPTER_SPLIT_WORD_THRESHOLD = 3500
CROSS_REF_EVERY_N = 10
SCOUT_CHUNK_WORD_LIMIT = 40000
MAX_SPEND_USD = 15.0

# --- těžba terminologie z profesionálních překladů ---------------------------

# Kořen se složkami EN/ a CZ/. Prázdné = nutno zadat `reference --dir CESTA`.
REFERENCE_DIR = ""
REFERENCE_PATH = os.path.join(DATA_DIR, "reference.json")
REFERENCE_CACHE_PATH = os.path.join(DATA_DIR, "reference_corpus.json")

MODEL_LEXICOGRAPHER = "claude-sonnet-5"
MAX_TOKENS_LEXICOGRAPHER = 4000
REFERENCE_BATCH_SIZE = 30

# Prahy jsou počáteční odhady bez měření; první běh je má potvrdit nebo posunout.
REFERENCE_MIN_HITS = 5          # výskytů pro `confirmed`
REFERENCE_MIN_BOOKS = 2         # dílů pro `confirmed`
REFERENCE_MIN_CORPUS_BOOKS = 3  # pod tímhle se `confirmed` netvrdí vůbec
REFERENCE_COOCCUR_RATIO = 0.5   # podíl dílů, kde musí sedět souvýskyt

# --- stylistický průchod přes Codex --------------------------------------
# Prázdné = `polish` odmítne běžet (auditní záznam potřebuje vědět, JAKÝ
# model se skutečně použil - "necháme na výchozím CLI" by časem přestalo
# být dohledatelné, viz kolo 2 plan-consensus review).
CODEX_MODEL = ""
# Timeout na jedno volání `codex exec` (kolo 17 IMPORTANT). `stylist.
# polish`'s parametr `timeout` je od kola 22 `= None` a bez explicitní
# hodnoty spadne SEM (dřív byl natvrdo `= 180`, veřejné volání config
# obcházelo). Dlouhá kapitola může legitimně potřebovat víc času -
# hodnota jde upravit BEZ zásahu do kódu.
STYLIST_TIMEOUT_SECONDS = 180
# Hrubý bezpečnostní strop na délku kapitoly pro stylistický průchod
# (kolo 17 IMPORTANT) - součet znaků EN+CZ. NENÍ přesný odhad tokenového
# limitu konkrétního modelu (ten je uživatelsky konfigurovaný přes
# CODEX_MODEL, jeho přesný kontext se odsud nedá spolehlivě zjistit) -
# je to konzervativní, ručně nastavitelná pojistka, co dá RYCHLÉ a JASNÉ
# "kapitola je moc dlouhá" hlášení MÍSTO čekání na timeout, co by u
# extrémně dlouhé kapitoly stejně nikdy neuspěl. ~60 000 znaků je hrubě
# desetitisíce slov EN+CZ dohromady - běžná kapitola bezpečně projde,
# extrémně dlouhá dostane rychlé, srozumitelné selhání.
STYLIST_MAX_CHARS = 60_000
# Bezpečnostní opt-in (kolo 19 BLOCKING) - `polish` volá agentní `codex
# exec`, který má (OVĚŘENO živě, viz bezpečnostní detail 6 v `stylist.
# polish` docstringu) NEOMEZENÉ ČTENÍ celého souborového systému. Prompt
# injection z textu knihy tak MŮŽE nechat Codex přečíst a "vrátit" obsah
# citlivého souboru dřív, než výstupní kontroly vůbec proběhnou.
# `polish` proto BĚŽÍ JEN, když je tahle hodnota výslovně `True` - není
# to default. Nastavení `True` = "rozumím, že tenhle příkaz spouští
# agenta se čtecím přístupem k celému disku nad textem knihy, a beru to
# riziko". Migrace na bezpečnější variantu (neagentní API bez nástrojů,
# nebo OS/kontejnerová izolace) tohle celé nahradí - viz sekce
# "Bezpečnostní rozhodnutí (kolo 19)" níže.
STYLIST_ACCEPT_FS_RISK = False
# Kolo 27-37 - report běhu `polish` (`polish-reports/run-*.json`).
# `False` (DEFAULT) = u ZÁMÍTNUTÝCH (`rejected`) kapitol report nese JEN
# `reason_types` (normalizované kategorie `"source/type"`), žádná volná
# textová pole nálezů ani zamítnutý text; konzole vynechá popisy nálezů;
# `polish()` chybové hlášky (`StylistError`) i `failed.error` v reportu
# jdou přes `stylist._redact_detail` - žádná hodnota odvozená z Codexova
# výstupu (stderr, sekvence čísel, počet odstavců, poměr délky,
# `str(e)`). Hlavičkové `run_error`/`finalization_error` nesou jen
# hlášky programu / redigované `FatalRunError` (kolo 35), `summary` a
# `run_id`/`generated_at`/... jsou metadata - v reportu zůstávají vždy.
# `True` (jen literál, `is True`) = PLNÝ DETAIL: zamítnutý text od
# Codexu + volná pole nálezů (`issue`, `cz_excerpt`, ...) + konzolové
# popisy + raw stderr/čísla/odstavce. Ať jde očima posoudit, jestli byl
# reject oprávněný.
# PROČ NENÍ `True` DEFAULT (kolo 31 IMPORTANT): zapnutím
# `STYLIST_ACCEPT_FS_RISK` bereš, že agent SMÍ číst disk BĚHEM běhu - NE
# že se případně exfiltrovaný obsah TRVALE uloží do souboru (navíc
# `polish-reports/` je vedle repa, které bývá v synchronizované složce -
# Nextcloud apod. - takže by to teklo dál). To je samostatné rozhodnutí,
# proto samostatný explicitní opt-in. Report v redukovaném režimu
# (`False`) pořád dá reject rate + rozpad podle `reason_types`; plný text
# zapni, jen když ten konkrétní běh potřebuješ prozkoumat očima.
STYLIST_REPORT_REJECTED_TEXT = False
