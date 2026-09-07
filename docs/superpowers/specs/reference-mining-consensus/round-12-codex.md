## TASK 1

### Základní normalizace a konfigurace referenční těžby

**Soubory:**

- vytvořit `src/textnorm.py`
- vytvořit `tests/test_textnorm.py`
- upravit `config.py`
- rozšířit `tests/test_config_env.py`

**Rozhraní:**

```python
def normalize_key(text: str) -> str:
    """NFC, casefold, trim a nahrazení každé sekvence whitespace jednou mezerou."""
```

Do `config.py` přidat přesně:

```python
REFERENCE_DIR = ""
REFERENCE_PATH = os.path.join(DATA_DIR, "reference.json")
REFERENCE_CACHE_PATH = os.path.join(DATA_DIR, "reference_corpus.json")

MODEL_LEXICOGRAPHER = "claude-sonnet-5"
MAX_TOKENS_LEXICOGRAPHER = 4000
REFERENCE_BATCH_SIZE = 30
REFERENCE_MIN_HITS = 5
REFERENCE_MIN_BOOKS = 2
REFERENCE_MIN_CORPUS_BOOKS = 3
REFERENCE_COOCCUR_RATIO = 0.5
```

`normalize_key` nesmí nahrazovat `guide.normalize`; použije se pouze pro identitu položek referenční těžby.

**První test:**

```python
# tests/test_textnorm.py
from src.textnorm import normalize_key


def test_normalize_key_applies_nfc_casefold_and_whitespace_collapse():
    decomposed = "  BI\u0301LA\u0301\t  RADA\n"
    assert normalize_key(decomposed) == "bílá rada"
```

**Implementace:**

```python
import re
import unicodedata


def normalize_key(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", normalized.casefold()).strip()
```

Poté spustit:

```text
pytest tests/test_textnorm.py tests/test_config_env.py -v
```

---

## TASK 2

### Audit a ruční normalizace draftu; oprava scout promptu

**Soubory:**

- vytvořit `src/draft_normalize.py`
- vytvořit `scripts/audit_reference_draft.py`
- vytvořit `tests/test_draft_normalize.py`
- upravit `src/agents/scout.py`
- rozšířit `tests/test_scout.py`
- ručně opravit `data/guide.draft.json` až po kontrole reportu

**Rozhraní:**

```python
class DraftCandidate(TypedDict):
    kind: Literal["enumeration", "alias_collision"]
    section: Literal["characters", "places", "terms"]
    canonical: str
    related_canonical: str | None
    parts: list[str]


def find_draft_candidates(draft: dict) -> list[DraftCandidate]:
    """Pouze detekuje a vrací deterministický seznam; draft nemění."""


def main(argv: Sequence[str] | None = None) -> int:
    """Načte draft a vypíše JSON report kandidátů."""
```

Audit má:

- prohledat `name_en` u `characters`/`places` a `term_en` u `terms`;
- detekovat `/` a samostatné slovo `or`, bez ohledu na mezery a velikost;
- detekovat, že `normalize_key(canonical)` jedné položky je mezi normalizovanými aliasy jiné;
- nic automaticky neslučovat ani nerozdělovat;
- řadit výstup podle sekce a pořadí položek v draftu.

`SYSTEM_PROMPT` scouta změnit tak, aby:

- každá položka reprezentovala právě jeden povrch;
- synonyma ukládal do `aliases`;
- `aliases` byly součástí schématu také pro `places` a `terms`.

**První test:**

```python
from src.draft_normalize import find_draft_candidates


def test_find_draft_candidates_reports_enumeration_and_alias_collision():
    draft = {
        "characters": [
            {"name_en": "Morgan", "aliases": ["Donald Morgan"]},
            {"name_en": "Donald Morgan", "aliases": []},
        ],
        "places": [],
        "terms": [
            {
                "term_en": "White Court / Red Court",
                "aliases": [],
                "suggested_cz": "Bílý dvůr / Rudý dvůr",
            }
        ],
    }

    assert find_draft_candidates(draft) == [
        {
            "kind": "alias_collision",
            "section": "characters",
            "canonical": "Donald Morgan",
            "related_canonical": "Morgan",
            "parts": [],
        },
        {
            "kind": "enumeration",
            "section": "terms",
            "canonical": "White Court / Red Court",
            "related_canonical": None,
            "parts": ["White Court", "Red Court"],
        },
    ]
```

Po implementaci:

```text
pytest tests/test_draft_normalize.py tests/test_scout.py -v
python scripts/audit_reference_draft.py data/guide.draft.json
```

Následuje explicitní lidský checkpoint: vytvořit zálohu, ručně provést sloučení/rozdělení a znovu spustit audit. Těžba nesmí pokračovat, dokud report není prázdný.

---

## TASK 3

### Načtení a spárování referenčního korpusu

**Soubory:**

- vytvořit `src/reference.py`
- vytvořit `tests/test_reference.py`

**Rozhraní:**

```python
from dataclasses import dataclass


@dataclass
class Evidence:
    hits: int
    books: list[int]
    per_form: dict[str, dict]
    matched_forms: list[str]


@dataclass
class Corpus:
    cz: dict[int, str]
    en: dict[int, str]
    manifest: dict[str, list[int]]
    source_root: str


def build_manifest(root: str) -> dict[str, list[int]]:
    """Vrátí relativní EPUB cestu -> [st_size, st_mtime_ns]."""


def load_corpus(root: str) -> Corpus:
    """Spáruje EN/CZ EPUBy, načte je přes ingest.load_book a spojí kapitoly."""
```

Implementace `load_corpus`:

- hledat pouze přímé `EN/*.epub` a `CZ/*.epub`;
- číslo CZ získat z `^(\d+)`, EN z `#(\d+)` nebo `Book (\d+)`;
- duplicitu čísla na stejné straně odmítnout `ValueError`;
- načíst jen čísla přítomná na obou stranách;
- kapitoly spojit přes `"\n\x00\n"` bez názvů kapitol;
- pokud načtení EN nebo CZ strany vyhodí `Exception`, varovat a vyřadit celý díl;
- minimum tří úspěšných dvojic kontrolovat až po načtení;
- chybějící adresář, prázdný korpus nebo nedostatečný počet párů hlásit `ValueError`;
- `source_root` uložit jako absolutní normalizovanou cestu;
- manifest vytvořit ze všech nalezených zdrojových EPUBů bez jejich parsování.

**První test:**

```python
from pathlib import Path

from src import reference
from src.ingest import Chapter


def test_load_corpus_pairs_books_and_joins_chapters(monkeypatch, tmp_path):
    en = tmp_path / "EN"
    cz = tmp_path / "CZ"
    en.mkdir()
    cz.mkdir()

    for number in (1, 2, 3):
        (en / f"Series Book {number}.epub").touch()
        (cz / f"{number} - Czech.epub").touch()

    def fake_load_book(path):
        language = Path(path).parent.name.lower()
        number = int(next(part for part in Path(path).stem.split() if part.isdigit()))
        return [
            Chapter(1, "One", f"{language}-{number}-a"),
            Chapter(2, "Two", f"{language}-{number}-b"),
        ]

    monkeypatch.setattr(reference.ingest, "load_book", fake_load_book)

    corpus = reference.load_corpus(str(tmp_path))

    assert sorted(corpus.en) == [1, 2, 3]
    assert sorted(corpus.cz) == [1, 2, 3]
    assert corpus.en[1] == "en-1-a\n\x00\nen-1-b"
    assert corpus.cz[1] == "cz-1-a\n\x00\ncz-1-b"
    assert corpus.source_root == str(tmp_path.resolve())
```

Poté doplnit testy duplicit, vadné jedné strany a kontroly minima a spustit:

```text
pytest tests/test_reference.py -v
```

## GUESSES

1. **Rozhraní normalizačního kroku.** Specifikace říká, že rozhoduje člověk a skript nic nemění, ale současně požaduje nový draft a zálohu. Předpokládám report-only skript a následnou ruční editaci. Alternativou je interaktivní nástroj nebo soubor s deklarativními rozhodnutími. **Záleží zásadně:** bez rozhodnutí není workflow reprodukovatelné ani jednoznačně testovatelné.

2. **Název zálohy.** Předpokládám `data/guide.draft.pre-reference.json`. Alternativy jsou `.bak`, timestamp nebo verzovaný soubor. **Záleží provozně, ne algoritmicky.**

3. **Formát reportu auditu.** Předpokládám JSON a výše uvedený `DraftCandidate`. Alternativou je pouze lidsky čitelný text. **Záleží málo**, pokud report nebude vstupem další automatizace.

4. **Význam zúžení whitespace.** Předpokládám `strip()` a nahrazení každé sekvence whitespace jednou ASCII mezerou. Alternativou je ponechání jedné mezery i na krajích. **Záleží pro stabilitu ID**, ale jde o běžné implementační rozhodnutí.

5. **Rozsah separatorů v auditu.** Předpokládám, že každý `/` a samostatné case-insensitive `or` vytvoří kandidáta, nikoli automatické rozdělení. Alternativou je rozlišovat skutečný výčet od aliasu typu `Will/Billy`. **Záleží málo**, protože rozhoduje člověk.

6. **Spojování EPUB dokumentů.** Předpokládám pouze `Chapter.raw_text`, bez titulů, oddělený `"\n\x00\n"`. Alternativou je vložit také `Chapter.title`. **Záleží pro počty výskytů a detekci začátku dokumentu.**

7. **Neodpovídající nebo nečíslované EPUBy.** Předpokládám ignorování s varováním; pouze duplicitní rozpoznané číslo je chyba. Alternativou je odmítnout celý korpus. **Záleží provozně.**

8. **Manifestový čas.** Předpokládám `st_mtime_ns`, protože je stabilnější než desetinné `st_mtime`. Specifikace uvádí jen „mtime“. **Záleží pro invalidaci cache, ale je to běžná implementační volnost.**

9. **Vstup `resolve`.** Specifikace říká „seznam povrchů“, ale nález i lexikograf potřebují také `id`, sekci, aliasy, druh a poznámku. Předpokládal bych `list[SurfaceItem]` s těmito poli. Alternativou je `list[str]` doplněný dalšími mapami nebo celý draft. **Záleží zásadně:** jde o veřejnou hranici hlavního orchestru a spec musí určit přesný typ.

10. **Fallback na draftové návrhy.** Předpokládám, že `suggested_cz` a `suggested` ze scout draftu se po zavedení těžby nikdy nepoužijí jako fallback pro `cz`/`render`, pokud je nepotvrdil stupeň 0. Alternativou je zachovat současné předvyplňování při chybějící nebo nečerstvé referenci. **Záleží zásadně:** alternativa porušuje hlavní invariant a může zanést modelový odhad do glosáře.

## CONTRADICTS EXISTING CODE

- Specifikace tvrdí, že `parsing.extract_json` umí vytáhnout pouze objekt. Současná implementace `json.loads(cleaned)` přijme i top-level seznam; pouze fallback regulárním výrazem hledá objekt.
- Požadovaný invariant zakazuje předvyplnit nedoložený modelový návrh, ale současný `merge_draft_and_guide` předvyplňuje `places` a `terms` z `suggested_cz` a postavám `render` z `suggested`. Specifikace současně požaduje zachovat tento název jako tenký obal nad `merge_sources(reference=None)`, aniž jednoznačně říká, zda se uvedený fallback musí odstranit.

## VERDICT

CHANGES_NEEDED - at least one guess is load-bearing and the spec must decide it