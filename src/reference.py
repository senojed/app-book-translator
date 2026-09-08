"""Referenční korpus profesionálních překladů a hledání v něm.

Zná EPUBy (přes `ingest`) a text. Nezná LLM, databázi, `guide` ani
`concordance` - to poslední schválně: `concordance.form_key` slévá
"Bílá rada" s "Bída rana" a `Za-Lord` nenajde ani v textu, kde stojí doslova.
Pro drift v jedné kapitole to stačí, pro doložení v milionovém korpusu ne.
"""
import json
import os
import re
import unicodedata
import warnings
from dataclasses import dataclass, field

import config
from src import ingest

SCHEMA_VERSION = 1

# Oddělovač dokumentů uvnitř jednoho dílu. NUL bajt se v próze nevyskytuje,
# takže z něj jde spolehlivě poznat hranici dokumentu při detekci začátku věty.
DOC_SEP = "\n\x00\n"

_CZ_NUMBER = re.compile(r"^(\d+)")
_EN_NUMBER = re.compile(r"#(\d+)|Book (\d+)", re.IGNORECASE)


@dataclass
class Corpus:
    cz: dict
    en: dict
    manifest: dict
    source_root: str


def _book_number(name: str, side: str):
    m = _CZ_NUMBER.match(name) if side == "cz" else _EN_NUMBER.search(name)
    if not m:
        return None
    return int(next(g for g in m.groups() if g)) if side == "en" else int(m.group(1))


def build_manifest(root: str) -> dict:
    """Jen os.stat - EPUBy se neparsují. Slouží k invalidaci cache i k otisku
    korpusu při `review`, kde by parsování dvaceti knih trvalo půl minuty."""
    out = {}
    for side in ("EN", "CZ"):
        d = os.path.join(root, side)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.lower().endswith(".epub"):
                continue
            st = os.stat(os.path.join(d, name))
            out[f"{side}/{name}"] = [st.st_size, st.st_mtime_ns]
    return out


def _strip_leading_title(text: str, title: str) -> str:
    """`Chapter.raw_text` z EPUB obsahuje i text nadpisu - `_load_epub()` ho
    získává přes `soup.get_text()`, který nadpis od těla nerozlišuje. Bez
    odstranění by titul (např. "Ch" nebo skutečný název kapitoly) zkresloval
    počty výskytů. Syntetický titul ("Kapitola N", padá při chybějícím
    nadpisu) se v textu nevyskytuje, takže se jím nic neodstraní."""
    stripped = text.lstrip()
    if title and stripped.startswith(title):
        return stripped[len(title):].lstrip("\n").lstrip()
    return text


def _load_side(root: str, side: str) -> dict:
    """Vrací {číslo dílu: text}. Duplicitní číslo je chyba - tiché přepsání
    klíče by zkreslilo důkaz."""
    d = os.path.join(root, side.upper())
    books, seen = {}, {}
    if not os.path.isdir(d):
        return books
    for name in sorted(os.listdir(d)):
        if not name.lower().endswith(".epub"):
            continue
        num = _book_number(name, side.lower())
        if num is None:
            print(f"reference: přeskakuji {side}/{name} - nerozpoznané číslo dílu")
            continue
        if num in seen:
            raise ValueError(
                f"Duplicitní číslo dílu {num} na straně {side}: "
                f"{seen[num]} a {name}")
        seen[num] = name
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                chapters = ingest.load_book(os.path.join(d, name))
        except Exception as e:
            print(f"reference: {side}/{name} se nenačetl ({type(e).__name__}), přeskakuji")
            continue
        # jen raw_text bez titulů. NFC při načtení: hledá se case-sensitive
        # (stupeň 0 na tom stojí), takže kanonicky ekvivalentní zápisy
        # (NFC vs. NFD "á") musí dojít na stejný tvar dřív, než se z nich
        # postaví regex - jinak by se stejně vypadající text nenašel.
        text = DOC_SEP.join(_strip_leading_title(c.raw_text, c.title) for c in chapters)
        books[num] = unicodedata.normalize("NFC", text)
    return books


def load_corpus(root: str) -> Corpus:
    # Manifest se bere PŘED parsováním i PO něm a musí sedět - `_load_side`
    # čte obsah souborů, což u desítek EPUBů chvíli trvá. Změní-li se soubor
    # UPROSTŘED (přepsání, re-export), manifest vzatý jen na konci by popsal
    # NOVÝ stav disku k textu, který je pořád STARÝ - Task 13 by pak tenhle
    # manifest uložil jako otisk toho, co bylo vytěženo, a `review` by nález
    # z předchozího textu tiše označil za čerstvý.
    manifest_before = build_manifest(root)
    en, cz = _load_side(root, "EN"), _load_side(root, "CZ")
    manifest_after = build_manifest(root)
    if manifest_before != manifest_after:
        raise ValueError(
            "Referenční soubory se změnily během načítání - spusť `reference` znovu.")
    paired = sorted(set(en) & set(cz))
    for num in sorted(set(en) ^ set(cz)):
        print(f"reference: díl {num} nemá protějšek, vyřazuji obě strany")
    if len(paired) < config.REFERENCE_MIN_CORPUS_BOOKS:
        raise ValueError(
            f"Jen {len(paired)} spárovaných dílů, potřeba aspoň "
            f"{config.REFERENCE_MIN_CORPUS_BOOKS} - na menším korpusu nelze "
            "tvrdit, že překladatel termín ponechal.")
    return Corpus(cz={n: cz[n] for n in paired}, en={n: en[n] for n in paired},
                  manifest=manifest_after, source_root=os.path.abspath(root))


def save_cache(corpus: Corpus, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"schema_version": SCHEMA_VERSION,
                   "source_root": corpus.source_root,
                   "manifest": corpus.manifest,
                   "cz": {str(k): v for k, v in corpus.cz.items()},
                   "en": {str(k): v for k, v in corpus.en.items()}},
                  f, ensure_ascii=False)
    os.replace(tmp, path)


def load_cache(path: str, root: str):
    """None znamená "postav znovu" - u chybějící, poškozené i zastaralé cache.

    Validuje strukturu explicitně: cache je soubor na disku, který si mezi
    verzemi nástroje nebo ruční editací může odchýlit tvar. Bez kontroly by
    poškozená cache místo `None` shodila `reference` KeyError/ValueError
    tracebackem místo hlášky "postav znovu"."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return None
    if data.get("source_root") != os.path.abspath(root):
        return None
    cz, en, manifest = data.get("cz"), data.get("en"), data.get("manifest")
    if not isinstance(cz, dict) or not isinstance(en, dict) or not isinstance(manifest, dict):
        return None
    try:
        cz_out = {int(k): v for k, v in cz.items() if isinstance(v, str)}
        en_out = {int(k): v for k, v in en.items() if isinstance(v, str)}
    except (TypeError, ValueError):
        return None
    if len(cz_out) != len(cz) or len(en_out) != len(en):
        return None    # nečíselný klíč nebo nečíselná/nenulová hodnota
    if set(cz_out) != set(en_out):
        return None    # nespárované číslo dílu - load_corpus() by ho vyřadilo
    if len(cz_out) < config.REFERENCE_MIN_CORPUS_BOOKS:
        return None    # cache pod minimem by obešla kontrolu v load_corpus()
    try:
        # os.listdir/os.stat uvnitř build_manifest můžou selhat i tady
        # (soubor mezitím zmizel, oprávnění, síťový disk) - bereme to jako
        # "cache neplatná, postav znovu", ne jako nezachycenou výjimku.
        current_manifest = build_manifest(root)
    except OSError:
        return None
    if manifest != current_manifest:
        return None
    return Corpus(cz=cz_out, en=en_out, manifest=manifest, source_root=data["source_root"])
