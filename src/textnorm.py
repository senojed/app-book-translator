"""Normalizace řetězců na identifikační klíč.

Bez závislostí schválně: používá to `guide`, `reference` i `review_ui`,
a kdyby modul cokoli importoval, protáhl by tu závislost všemi třemi.

POZOR: `normalize_key` slouží JEN k identitě položek, nikdy k hledání v textu.
Dělá `casefold()`, takže by zahodil velikost písmen, na které stojí rozlišení
vlastního jména od obecného slova ve stupni 0 těžby.
"""
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize_key(s) -> str:
    """NFC → casefold → jedna mezera místo každé sekvence bílých znaků → strip."""
    text = unicodedata.normalize("NFC", s or "")
    return _WHITESPACE.sub(" ", text.casefold()).strip()
