"""
Centrální konfigurace. Žádné tajné klíče natvrdo - API klíč se čte z env proměnné.
"""
import os

# Klíč se záměrně nekontroluje tady, ale až v llm_client.py při skutečném volání
# API - příkazy jako 'init', 'status', 'export' ho nepotřebují a neměly by kvůli
# němu selhávat.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Model pro jednotlivé role - lze odlišit (např. levnější model pro terminologii,
# silnější pro překlad a kritiku). Zatím jednotně, uprav podle potřeby a rozpočtu.
MODEL_TRANSLATOR = "claude-sonnet-4-6"
MODEL_TERMINOLOGY = "claude-sonnet-4-6"
MODEL_CRITIC = "claude-sonnet-4-6"
MODEL_CROSS_REF = "claude-sonnet-4-6"

# Strop výstupních tokenů na jedno volání. Když ho model přerazí, výstup se
# usekne - llm_client to pozná a vyhodí chybu (u překladu je useknutý text
# tichá ztráta kapitoly). Translator má velký strop, protože český překlad
# scény bývá delší než anglický originál.
MAX_TOKENS_TRANSLATOR = 16000
MAX_TOKENS_TERMINOLOGY = 3000
MAX_TOKENS_CRITIC = 4000
MAX_TOKENS_CROSS_REF = 6000

# Kolikrát Anthropic SDK samo zopakuje volání při rate-limitu (429) nebo chybě
# serveru (5xx), s exponenciálním backoffem. Default SDK jsou 2 - u běhu přes
# celou knihu (stovky volání) je to málo.
API_MAX_RETRIES = 8

# Práh v přibl. počtu slov, nad kterým se kapitola interně dělí na scény
# (dělení podle prázdných řádků / typických oddělovačů scén).
CHAPTER_SPLIT_WORD_THRESHOLD = 3500

# Kolik kapitol proběhne ve fázi 0 (kalibrace) před plným během.
CALIBRATION_CHAPTERS = 2

# Jak často (v kapitolách) se spouští cross-reference kontrola během plného běhu.
CROSS_REF_EVERY_N_CHAPTERS = 10

DATA_DIR = "data"
OUTPUT_DIR = "output"
DB_PATH = os.path.join(DATA_DIR, "state.sqlite3")
GLOSSARY_PATH = os.path.join(DATA_DIR, "glossary.json")
STYLE_GUIDE_PATH = os.path.join(DATA_DIR, "style_guide.json")
