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
