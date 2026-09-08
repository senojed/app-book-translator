# Těžba terminologie z profesionálních překladů - implementační plán

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Přidat příkaz `python main.py reference`, který z deseti profesionálně přeložených dílů (EN+CZ EPUBy) vytěží doložitelnou terminologii, uloží ji do `data/reference.json`, a review formulář ji zobrazí s důkazem - aniž by se jakýkoli nedoložený odhad předvyplnil.

**Architecture:** Dva stupně. Stupeň 0 hledá anglický povrch v českém textu (zdarma, deterministicky) - najde-li se, překladatel ho ponechal. Stupeň 1 se na zbytek zeptá modelu a jeho návrh ověří proti korpusu. Výsledek žije ve vlastním souboru, glosář se plní beze změny obvyklou cestou přes `review`. Předvyplňuje se jen doložené; odhady čekají vedle prázdného pole na kliknutí.

**Tech Stack:** Python 3.11+, stávající `ebooklib`/`beautifulsoup4` přes `src/ingest.py`, `anthropic` přes `src/llm/client.py`, `fastapi` pro review UI, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-07-reference-mining-design.md` - plán argumentuje ze specu, executor čte oba.

## Global Constraints

- **Python 3.11+.** Žádné nové runtime závislosti - vše se staví na tom, co projekt už má.
- **Import layout:** moduly v `src/` importují sourozence jako `from src import X`, kořenový config jako `import config`. Nikdy `import reference` jako top-level.
- **UTF-8:** testy i CLI musí projít v `cp1252` konzoli. `main.py` už má `_bootstrap_stdout()`; pomocné skripty spouštěné mimo `main.py` si UTF-8 musí zajistit samy.
- **`concordance` se NEMĚNÍ a `reference.py` ho NEPOUŽÍVÁ.** Ověřeno: `form_key("Bílá rada") == form_key("Bída rana")` a `find_form_occurrences("Byl to Za-Lord.", "Za-Lord") == []`.
- **`textnorm.normalize_key()` slouží jen k identitě položek, nikdy k hledání** - `casefold()` by zahodil velikost písmen, na které stupeň 0 stojí.
- **Invariant:** odhad se nikdy nesmí tvářit jako důkaz. U glosářových polí (`cz`, `render` u postav/míst/termínů) se předvyplňuje **jen** to, co je doloženo referencemi.
- **Selhání je atomické:** selže-li cokoli během těžby, předchozí `reference.json` zůstane nedotčený a běh skončí nenulovým kódem.
- **Commity často** - každý task končí commitnutým, samostatně testovatelným deliverable.
- Konfigurační výchozí hodnoty (v `config.py`): `REFERENCE_MIN_HITS = 5`, `REFERENCE_MIN_BOOKS = 2`, `REFERENCE_MIN_CORPUS_BOOKS = 3`, `REFERENCE_COOCCUR_RATIO = 0.5`, `REFERENCE_BATCH_SIZE = 30`, `MAX_TOKENS_LEXICOGRAPHER = 4000`.

---

## Task 1: textnorm + konfigurační klíče

**Files:**
- Create: `src/textnorm.py`
- Create: `tests/test_textnorm.py`
- Modify: `config.py` (přidat blok `REFERENCE_*` a `*_LEXICOGRAPHER`)

**Interfaces:**
- Consumes: nic
- Produces:
  - `textnorm.normalize_key(s: str) -> str` - NFC → `casefold()` → sekvence bílých znaků na jednu ASCII mezeru → `strip()`
  - konfigurační klíče `REFERENCE_DIR`, `REFERENCE_PATH`, `REFERENCE_CACHE_PATH`, `MODEL_LEXICOGRAPHER`, `MAX_TOKENS_LEXICOGRAPHER`, `REFERENCE_BATCH_SIZE`, `REFERENCE_MIN_HITS`, `REFERENCE_MIN_BOOKS`, `REFERENCE_MIN_CORPUS_BOOKS`, `REFERENCE_COOCCUR_RATIO`

- [ ] **Step 1: Write the failing test** — `tests/test_textnorm.py`

```python
import unicodedata
from src import textnorm
from src import guide


def test_normalize_key_nfc_and_casefold():
    # NFD zápis "á" (a + kombinující čárka) musí dát stejný klíč jako NFC
    nfd = unicodedata.normalize("NFD", "Bílá Rada")
    assert textnorm.normalize_key(nfd) == textnorm.normalize_key("Bílá Rada")
    assert textnorm.normalize_key("Bílá Rada") == "bílá rada"


def test_normalize_key_collapses_whitespace():
    assert textnorm.normalize_key("  White   Council \t\n") == "white council"


def test_normalize_key_handles_none_and_empty():
    assert textnorm.normalize_key("") == ""
    assert textnorm.normalize_key(None) == ""


def test_guide_normalize_unchanged():
    """relationship_key stojí na guide.normalize - nesmí se posunout,
    jinak by se rozešly klíče existujících vztahů."""
    assert guide.normalize("  Harry  ") == "harry"
    assert guide.relationship_key("Harry", "murphy") == "harry|murphy"


def test_config_has_reference_keys():
    import config
    for key in ("REFERENCE_DIR", "REFERENCE_PATH", "REFERENCE_CACHE_PATH",
                "MODEL_LEXICOGRAPHER", "MAX_TOKENS_LEXICOGRAPHER",
                "REFERENCE_BATCH_SIZE", "REFERENCE_MIN_HITS",
                "REFERENCE_MIN_BOOKS", "REFERENCE_MIN_CORPUS_BOOKS",
                "REFERENCE_COOCCUR_RATIO"):
        assert hasattr(config, key), key
    assert config.PRICE_IN_PER_MTOK.get(config.MODEL_LEXICOGRAPHER) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_textnorm.py -v`
Expected: FAIL - `ImportError: cannot import name 'textnorm' from 'src'`

- [ ] **Step 3: Implement `src/textnorm.py`**

```python
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
```

- [ ] **Step 4: Add config keys** — připoj na konec `config.py`

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_textnorm.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add src/textnorm.py tests/test_textnorm.py config.py
git commit -m "feat: textnorm.normalize_key + konfigurace těžby referencí"
```

---

## Task 2: normalizační skript draftu (krok 0, report-only)

Samostatný nástroj, nezávislý na zbytku těžby. Dělá se první, aby mohla ruční
oprava draftu běžet paralelně se stavbou zbytku.

**Files:**
- Create: `tools/check_draft.py`
- Create: `tests/test_check_draft.py`

**Interfaces:**
- Consumes: `src/textnorm.py`, `src/guide.py` (`load_draft`, `relationship_key`)
- Produces:
  - `check_draft.find_issues(draft: dict) -> dict` - vrací
    `{"compound": [...], "alias_collision": [...], "bad_scope_key": [...], "bad_relationship": [...], "parenthesized": [...], "cross_section": [...], "weak_alias": [...], "short_relationship": [...]}`,
    každá položka je dict s `section`, `surface` a `detail`
  - `check_draft.main(argv=None) -> int` - vypíše report, vrátí 0 když je draft čistý, 1 když ne

- [ ] **Step 1: Write the failing test** — `tests/test_check_draft.py`

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import check_draft


def _draft(**over):
    base = {"characters": [], "places": [], "terms": [], "relationships": [],
            "style_notes": "", "must_decide": []}
    base.update(over)
    return base


def test_detects_compound_surface():
    d = _draft(terms=[{"term_en": "White Court / Red Court", "suggested_cz": "", "note": ""}])
    issues = check_draft.find_issues(d)
    assert [i["surface"] for i in issues["compound"]] == ["White Court / Red Court"]


def test_detects_or_separator_case_insensitive():
    d = _draft(terms=[{"term_en": "veil OR veiling spell", "suggested_cz": "", "note": ""}])
    assert check_draft.find_issues(d)["compound"]


def test_detects_alias_collision():
    d = _draft(characters=[
        {"name_en": "Morgan", "aliases": [], "suggested": "keep", "note": ""},
        {"name_en": "Donald Morgan", "aliases": ["Morgan"], "suggested": "keep", "note": ""}])
    coll = check_draft.find_issues(d)["alias_collision"]
    assert [c["surface"] for c in coll] == ["Morgan"]


def test_detects_parenthesized_surface():
    d = _draft(terms=[{"term_en": "Warden(s)", "suggested_cz": "", "note": ""}])
    assert check_draft.find_issues(d)["parenthesized"]


def test_detects_cross_section_homonym():
    d = _draft(characters=[{"name_en": "Demonreach", "aliases": [], "suggested": "keep", "note": ""}],
               places=[{"name_en": "Demonreach", "suggested_cz": "", "note": ""}])
    assert check_draft.find_issues(d)["cross_section"]


def test_detects_weak_alias():
    d = _draft(characters=[{"name_en": "Ebenezar McCoy", "aliases": ["sir", "Eb"],
                            "suggested": "keep", "note": ""}])
    weak = {w["detail"] for w in check_draft.find_issues(d)["weak_alias"]}
    assert weak == {"sir", "Eb"}   # 'sir' je v seznamu rolí, 'Eb' má <= 3 znaky


def test_style_scope_key_is_not_an_issue():
    """Styl není kolekce klíčovaných položek - jeho odpověď jde do rules."""
    d = _draft(must_decide=[{"kind": "style", "scope_key": "nicknames",
                             "question": "?", "default": ""}])
    assert check_draft.find_issues(d)["bad_scope_key"] == []


def test_detects_scope_key_pointing_nowhere():
    d = _draft(terms=[{"term_en": "Nevernever", "suggested_cz": "", "note": ""}],
               must_decide=[{"kind": "term", "scope_key": "the Nevernever",
                             "question": "?", "default": ""}])
    assert check_draft.find_issues(d)["bad_scope_key"]


def test_detects_relationship_with_slash_and_short_form():
    d = _draft(characters=[{"name_en": "Ebenezar McCoy", "aliases": [], "suggested": "keep", "note": ""},
                           {"name_en": "Harry Dresden", "aliases": [], "suggested": "keep", "note": ""}],
               relationships=[{"a": "Harry", "b": "Will/Georgia", "suggested": "tyka"},
                              {"a": "Harry", "b": "Ebenezar", "suggested": "vyka"}])
    issues = check_draft.find_issues(d)
    assert issues["bad_relationship"]      # lomítko ve jméně
    assert issues["short_relationship"]    # 'Ebenezar' není kanonické jméno


def test_clean_draft_has_no_issues():
    d = _draft(characters=[{"name_en": "Harry Dresden", "aliases": ["Dresden"],
                            "suggested": "keep", "note": ""}],
               terms=[{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
               relationships=[],
               must_decide=[{"kind": "term", "scope_key": "Nevernever",
                             "question": "?", "default": ""}])
    assert all(v == [] for v in check_draft.find_issues(d).values())
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_check_draft.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 3: Implement `tools/check_draft.py`** (nezapomeň `tools/__init__.py`)

```python
"""Report-only kontrola draftu od scouta před těžbou referencí.

Scoutův draft obsahuje vady, které by těžbu a formulář rozbily: výčty místo
jednoho povrchu, duplicitní entity, otázky odkazující nikam. Tenhle skript je
NAJDE A VYPÍŠE, ale nic nemění - opravu dělá člověk ručně v `guide.draft.json`.

Proč report-only: rozhodnutí "je `White Court / Red Court` jedna entita se
synonymy, nebo tři různé?" automat neudělá. Je to jednorázová práce na ~39
řádcích, takže interaktivní nástroj by se nevyplatil.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src import guide, textnorm

# Aliasy, které jako dotaz do korpusu nic neurčují - rozšířily by důkaz o šum.
ROLE_ALIASES = {"sir", "captain", "kid", "apprentice", "boss", "boy", "girl",
                "master", "mister", "miss"}

_OR_SEPARATOR = re.compile(r"\bor\b", re.IGNORECASE)
SECTIONS = (("characters", "name_en"), ("places", "name_en"), ("terms", "term_en"))
KIND_TO_SECTION = {"name": "characters", "place": "places", "term": "terms"}


def _items(draft):
    """Vrací (sekce, klíčové_pole, položka) pro všechny tři sekce."""
    for section, field in SECTIONS:
        for item in draft.get(section) or []:
            yield section, field, item


def _issue(section, surface, detail):
    return {"section": section, "surface": surface, "detail": detail}


def find_issues(draft: dict) -> dict:
    issues = {k: [] for k in ("compound", "alias_collision", "bad_scope_key",
                              "bad_relationship", "parenthesized",
                              "cross_section", "weak_alias",
                              "short_relationship")}

    # mapa normalizovaný klíč -> sekce (pro homonyma) a alias -> vlastník
    key_sections, alias_owner = {}, {}
    for section, field, item in _items(draft):
        surface = item.get(field) or ""
        key = textnorm.normalize_key(surface)
        if key:
            key_sections.setdefault(key, set()).add(section)
        for alias in item.get("aliases") or []:
            alias_owner.setdefault(textnorm.normalize_key(alias), []).append(surface)

    for section, field, item in _items(draft):
        surface = item.get(field) or ""
        if "/" in surface or _OR_SEPARATOR.search(surface):
            issues["compound"].append(_issue(section, surface, "výčet variant"))
        if "(" in surface or ")" in surface:
            issues["parenthesized"].append(
                _issue(section, surface, "poznámka v závorce - přesné hledání ji nenajde"))
        owners = [o for o in alias_owner.get(textnorm.normalize_key(surface), [])
                  if textnorm.normalize_key(o) != textnorm.normalize_key(surface)]
        if owners:
            issues["alias_collision"].append(
                _issue(section, surface, "je aliasem u: " + ", ".join(owners)))
        for alias in item.get("aliases") or []:
            a = textnorm.normalize_key(alias)
            if a in ROLE_ALIASES or len(alias.strip()) <= 3 or (alias[:1].islower() if alias else False):
                issues["weak_alias"].append(_issue(section, surface, alias))

    for key, sections in key_sections.items():
        if len(sections) > 1:
            issues["cross_section"].append(
                _issue("/".join(sorted(sections)), key, "homonymum napříč sekcemi"))

    # kanonická jména postav - pro kontrolu konců vztahů
    char_keys = {textnorm.normalize_key(c.get("name_en") or "")
                 for c in draft.get("characters") or []}
    for rel in draft.get("relationships") or []:
        for end in (rel.get("a") or "", rel.get("b") or ""):
            if "/" in end:
                issues["bad_relationship"].append(
                    _issue("relationships", end, "lomítko ve jméně"))
            elif textnorm.normalize_key(end) not in char_keys:
                issues["short_relationship"].append(
                    _issue("relationships", end, "není kanonické jméno postavy"))

    for md in draft.get("must_decide") or []:
        kind = md.get("kind")
        scope = md.get("scope_key") or ""
        if kind == "style":
            continue          # styl nemá klíčované položky, odpověď jde do rules
        if kind == "relationship":
            a, _, b = scope.partition("|")
            if not b or textnorm.normalize_key(a) not in char_keys \
                    or textnorm.normalize_key(b) not in char_keys:
                issues["bad_scope_key"].append(
                    _issue("must_decide", scope, "vztah: čekej tvar a|b s kanonickými jmény"))
            continue
        section = KIND_TO_SECTION.get(kind)
        if section is None:
            issues["bad_scope_key"].append(_issue("must_decide", scope, f"neznámý kind {kind!r}"))
            continue
        if textnorm.normalize_key(scope) not in {
                textnorm.normalize_key(i.get(f) or "")
                for s, f, i in _items(draft) if s == section}:
            issues["bad_scope_key"].append(
                _issue("must_decide", scope, f"neukazuje na položku v sekci {section}"))

    return issues


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    path = (argv or sys.argv[1:] or [config.GUIDE_DRAFT_PATH])[0]
    draft = guide.load_draft(path)
    issues = find_issues(draft)
    total = sum(len(v) for v in issues.values())
    if not total:
        print(f"{path}: čistý, všech šest postpodmínek splněno.")
        return 0
    print(f"{path}: {total} věcí k ruční opravě\n")
    for name, rows in issues.items():
        if not rows:
            continue
        print(f"== {name} ({len(rows)}) ==")
        for r in rows:
            print(f"   [{r['section']}] {r['surface']!r} - {r['detail']}")
        print()
    print("Skript nic nemění. Oprav guide.draft.json ručně a spusť znovu.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_check_draft.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Run against the real draft** (jen se podívej, nic neopravuj)

Run: `python tools/check_draft.py`
Expected: vypíše ~39 položek v osmi kategoriích, exit 1.

- [ ] **Step 6: Commit**

```bash
git add tools/__init__.py tools/check_draft.py tests/test_check_draft.py
git commit -m "feat: report-only kontrola draftu (krok 0 těžby referencí)"
```

---

## Task 3: reference.py - načtení a cache korpusu

**Files:**
- Create: `src/reference.py`
- Create: `tests/test_reference_corpus.py`

**Interfaces:**
- Consumes: `src/ingest.py` (`load_book`), `config`
- Produces:
  - `reference.DOC_SEP = "\n\x00\n"` - oddělovač dokumentů uvnitř jednoho dílu
  - `@dataclass Corpus(cz: dict[int, str], en: dict[int, str], manifest: dict, source_root: str)`
  - `reference.build_manifest(root) -> dict` - `{relativní cesta: [velikost, st_mtime_ns]}`, jen `os.stat`
  - `reference.load_corpus(root) -> Corpus`
  - `reference.save_cache(corpus, path) -> None`, `reference.load_cache(path, root) -> Corpus | None`

- [ ] **Step 1: Write the failing test** — `tests/test_reference_corpus.py`

```python
import os
import pytest
from src import reference


def _fake_epub(tmp_path, subdir, name, text):
    """Vyrobí minimální EPUB, který ingest.load_book přečte."""
    import warnings
    warnings.filterwarnings("ignore")
    from ebooklib import epub
    d = tmp_path / subdir
    d.mkdir(parents=True, exist_ok=True)
    b = epub.EpubBook()
    b.set_identifier("id"); b.set_title("T"); b.set_language("en")
    c = epub.EpubHtml(title="Ch", file_name="c1.xhtml", uid="c1")
    c.content = f"<h1>Ch</h1><p>{text}</p>"
    b.add_item(c); b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    b.spine = [c]
    p = str(d / name)
    epub.write_epub(p, b)
    return p


def _corpus_root(tmp_path, pairs):
    """pairs = [(cislo, en_text, cz_text)]"""
    for num, en, cz in pairs:
        _fake_epub(tmp_path, "EN", f"Book (#{num:02d}) title.epub", en)
        _fake_epub(tmp_path, "CZ", f"{num} nazev - Jim Butcher.epub", cz)
    return str(tmp_path)


def test_load_corpus_pairs_books_by_number(tmp_path):
    long_en = "Harry Dresden walked into the room. " * 30
    long_cz = "Harry Dresden vesel do mistnosti. " * 30
    root = _corpus_root(tmp_path, [(1, long_en, long_cz), (2, long_en, long_cz),
                                   (3, long_en, long_cz)])
    c = reference.load_corpus(root)
    assert sorted(c.cz) == [1, 2, 3]
    assert sorted(c.en) == [1, 2, 3]
    assert "Harry Dresden" in c.cz[1]
    assert c.source_root == root


def test_load_corpus_rejects_too_small_corpus(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en)])
    with pytest.raises(ValueError, match="spárovan"):
        reference.load_corpus(root)


def test_load_corpus_rejects_duplicate_book_number(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    # druhý soubor se stejným číslem na CZ straně
    _fake_epub(tmp_path, "CZ", "1 jiny nazev.epub", long_en)
    with pytest.raises(ValueError, match="[Dd]uplicit"):
        reference.load_corpus(root)


def test_unpaired_book_drops_both_sides(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    _fake_epub(tmp_path, "EN", "Book (#09) solo.epub", long_en)   # bez CZ protějšku
    c = reference.load_corpus(root)
    assert 9 not in c.en and 9 not in c.cz


def test_documents_joined_with_separator_and_without_titles(tmp_path):
    long_en = "Some sentence about things. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    c = reference.load_corpus(root)
    assert "Ch" not in c.en[1].split(".")[0]   # nadpis dokumentu se nepřipojuje


def test_manifest_and_cache_roundtrip(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    c = reference.load_corpus(root)
    cache = str(tmp_path / "cache.json")
    reference.save_cache(c, cache)
    back = reference.load_cache(cache, root)
    assert back is not None and back.cz.keys() == c.cz.keys()


def test_cache_invalidated_when_file_changes(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    cache = str(tmp_path / "cache.json")
    reference.save_cache(reference.load_corpus(root), cache)
    _fake_epub(tmp_path, "CZ", "1 nazev - Jim Butcher.epub", long_en + " navic")
    assert reference.load_cache(cache, root) is None


def test_cache_invalidated_for_different_root(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    cache = str(tmp_path / "cache.json")
    reference.save_cache(reference.load_corpus(root), cache)
    assert reference.load_cache(cache, str(tmp_path / "jinde")) is None
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_reference_corpus.py -v`
Expected: FAIL - `ImportError: cannot import name 'reference' from 'src'`

- [ ] **Step 3: Implement korpusovou část `src/reference.py`**

```python
"""Referenční korpus profesionálních překladů a hledání v něm.

Zná EPUBy (přes `ingest`) a text. Nezná LLM, databázi, `guide` ani
`concordance` - to poslední schválně: `concordance.form_key` slévá
"Bílá rada" s "Bída rana" a `Za-Lord` nenajde ani v textu, kde stojí doslova.
Pro drift v jedné kapitole to stačí, pro doložení v milionovém korpusu ne.
"""
import json
import os
import re
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
        # jen raw_text, bez titulů - ty bývají "Chapter 1" a zkreslily by počty
        books[num] = DOC_SEP.join(c.raw_text for c in chapters)
    return books


def load_corpus(root: str) -> Corpus:
    en, cz = _load_side(root, "EN"), _load_side(root, "CZ")
    paired = sorted(set(en) & set(cz))
    for num in sorted(set(en) ^ set(cz)):
        print(f"reference: díl {num} nemá protějšek, vyřazuji obě strany")
    if len(paired) < config.REFERENCE_MIN_CORPUS_BOOKS:
        raise ValueError(
            f"Jen {len(paired)} spárovaných dílů, potřeba aspoň "
            f"{config.REFERENCE_MIN_CORPUS_BOOKS} - na menším korpusu nelze "
            "tvrdit, že překladatel termín ponechal.")
    return Corpus(cz={n: cz[n] for n in paired}, en={n: en[n] for n in paired},
                  manifest=build_manifest(root), source_root=os.path.abspath(root))


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
    """None znamená "postav znovu" - u chybějící, poškozené i zastaralé cache."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if data.get("schema_version") != SCHEMA_VERSION:
        return None
    if data.get("source_root") != os.path.abspath(root):
        return None
    if data.get("manifest") != build_manifest(root):
        return None
    return Corpus(cz={int(k): v for k, v in data["cz"].items()},
                  en={int(k): v for k, v in data["en"].items()},
                  manifest=data["manifest"], source_root=data["source_root"])
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_reference_corpus.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/reference.py tests/test_reference_corpus.py
git commit -m "feat: reference korpus - párování dílů, manifest, cache"
```

---

## Task 4: reference.py - hledání stupně 0 (co je důkaz ponechání)

Nejcitlivější část celého plánu. `stole` má v referencích 79 výskytů v 10/10
dílech a je to český lokativ slova *stůl* - ne ponechaný termín.

**Files:**
- Modify: `src/reference.py` (append)
- Create: `tests/test_reference_stage0.py`

**Interfaces:**
- Consumes: `Corpus`, `DOC_SEP`
- Produces:
  - `@dataclass Evidence(hits: int, books: list[int], per_form: dict, matched_forms: list[str], confirm_eligible: bool)`
    kde `per_form = {tvar: {"hits": int, "books": list[int], "case_exact": bool}}`
  - `reference.count_en_surface(corpus, surface: str, aliases: list[str] = (), side: str = "cz") -> Evidence`

- [ ] **Step 1: Write the failing test** — `tests/test_reference_stage0.py`

```python
from src import reference


def _corpus(cz_texts):
    return reference.Corpus(cz={i + 1: t for i, t in enumerate(cz_texts)},
                            en={i + 1: "" for i in range(len(cz_texts))},
                            manifest={}, source_root="/x")


def test_lowercase_common_word_is_never_eligible():
    """`stole` = český lokativ slova stůl. Najde se, ale nesmí být způsobilé."""
    c = _corpus(["Kniha ležela na stole a vedle na stole byl hrnek."] * 6)
    ev = reference.count_en_surface(c, "stole")
    assert ev.hits > 0                 # důkaz existuje
    assert ev.confirm_eligible is False


def test_capitalized_name_is_eligible():
    c = _corpus(["Mab se usmála. Potkal Mab v lese."] * 3)
    ev = reference.count_en_surface(c, "Mab")
    assert ev.confirm_eligible is True


def test_case_insensitive_only_match_is_not_eligible():
    """Anglický povrch nesmí 'potvrdit' nesouvisející české slovo jinou velikostí."""
    c = _corpus(["Bylo to mab a zase mab uprostřed věty."] * 3)
    ev = reference.count_en_surface(c, "Mab")
    assert ev.hits > 0
    assert ev.confirm_eligible is False


def test_short_surface_needs_occurrence_outside_sentence_start():
    """Jméno, které je zároveň českým slovem, na začátku věty nic nedokazuje."""
    only_start = _corpus(["Bob je luštěnina. Bob roste na poli."] * 3)
    assert reference.count_en_surface(only_start, "Bob").confirm_eligible is False
    mid = _corpus(["Potkal jsem Boba. Viděl jsem Bob uprostřed."] * 3)
    assert reference.count_en_surface(mid, "Bob").confirm_eligible is True


def test_eligibility_needs_one_occurrence_meeting_all_conditions():
    """Podmínky musí splnit TENTÝŽ výskyt, ne každá jiný."""
    # 'Mab' správně psané jen na začátku věty; uprostřed jen 'mab'
    split = _corpus(["Mab přišla. Byl tam mab uprostřed věty."] * 3)
    assert reference.count_en_surface(split, "Mab").confirm_eligible is False
    # jeden výskyt splňující obojí naráz
    both = _corpus(["Přišla Mab uprostřed věty."] * 3)
    assert reference.count_en_surface(both, "Mab").confirm_eligible is True


def test_one_and_two_char_surfaces_are_not_searched():
    c = _corpus(["Ed a Ed a zase Ed."] * 3)
    ev = reference.count_en_surface(c, "Ed")
    assert ev.hits == 0 and ev.confirm_eligible is False


def test_hyphen_and_apostrophe_stay_part_of_the_query():
    c = _corpus(["Byl to Za-Lord osobně. A Listens-to-Wind mlčel."] * 3)
    assert reference.count_en_surface(c, "Za-Lord").hits > 0
    assert reference.count_en_surface(c, "Listens-to-Wind").hits > 0


def test_word_boundary_prevents_substring_match():
    c = _corpus(["Mabel byla jiná osoba."] * 3)
    assert reference.count_en_surface(c, "Mab").hits == 0


def test_alias_hits_are_union_not_sum():
    """`Dresden` uvnitř `Harry Dresden` se nesmí započítat dvakrát."""
    c = _corpus(["Harry Dresden dorazil pozdě."] * 2)
    ev = reference.count_en_surface(c, "Harry Dresden", aliases=["Dresden"])
    assert ev.hits == 2                      # dva díly, jeden výskyt v každém
    assert set(ev.matched_forms) == {"Harry Dresden", "Dresden"}


def test_per_form_tracks_each_alias_separately():
    c = _corpus(["Harry Dresden a pak jen Dresden."] * 3)
    ev = reference.count_en_surface(c, "Harry Dresden", aliases=["Dresden", "Hoss"])
    assert ev.per_form["Harry Dresden"]["hits"] == 3
    assert ev.per_form["Dresden"]["hits"] == 6      # i uvnitř celého jména
    assert ev.per_form["Hoss"]["hits"] == 0


def test_books_lists_only_books_with_hits():
    c = reference.Corpus(cz={1: "Mab tady byla uprostřed.", 2: "nic", 3: "Mab zase uprostřed."},
                         en={}, manifest={}, source_root="/x")
    assert reference.count_en_surface(c, "Mab").books == [1, 3]


def test_document_separator_counts_as_sentence_start():
    text = "Bob uprostřed." + reference.DOC_SEP + "Bob na začátku dokumentu."
    c = _corpus([text] * 3)
    ev = reference.count_en_surface(c, "Bob")
    # první výskyt je uprostřed věty -> způsobilé
    assert ev.confirm_eligible is True
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_reference_stage0.py -v`
Expected: FAIL - `AttributeError: module 'src.reference' has no attribute 'count_en_surface'`

- [ ] **Step 3: Implement hledání stupně 0** — připoj do `src/reference.py`

```python
_SENTENCE_END = ".!?…"


@dataclass
class Evidence:
    hits: int = 0
    books: list = field(default_factory=list)
    per_form: dict = field(default_factory=dict)
    matched_forms: list = field(default_factory=list)
    confirm_eligible: bool = False


def _word_pattern(surface: str, ignore_case: bool):
    """Hranice slova přes lookaround, ne \\b - aby pomlčka a apostrof uvnitř
    povrchu zůstaly součástí dotazu (`Listens-to-Wind`, `Za-Lord`)."""
    flags = re.UNICODE | (re.IGNORECASE if ignore_case else 0)
    return re.compile(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", flags)


def _at_sentence_start(text: str, pos: int) -> bool:
    """Začátek věty = pozice 0, první nebílý znak po .!?… nebo po oddělovači
    dokumentů. Chrání krátká jména, která jsou zároveň českými slovy."""
    i = pos - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i < 0:
        return True
    return text[i] in _SENTENCE_END or text[i] == "\x00"


def count_en_surface(corpus: Corpus, surface: str, aliases=(), side: str = "cz") -> Evidence:
    """Hledá anglický povrch (a jeho aliasy) v textu dané strany korpusu.

    Nález sám o sobě neznamená, že překladatel povrch ponechal - viz
    `confirm_eligible`. Prahy pro `confirmed` se počítají výhradně
    z primárního tvaru, aliasy jsou doplňkový důkaz pro člověka.
    """
    ev = Evidence()
    surface = (surface or "").strip()
    if not surface:
        return ev
    texts = corpus.cz if side == "cz" else corpus.en
    forms = [surface] + [a for a in (aliases or []) if a and a.strip()]
    # Malé počáteční písmeno = obecné slovo. Hledá se case-sensitive (slabý
    # filtr) a nikdy nebude způsobilé - `stole` je toho důvodem.
    lowercase_surface = surface[:1].islower()

    spans_by_book, books_with_hit = {}, set()
    for form in forms:
        per = {"hits": 0, "books": [], "case_exact": False}
        if len(form.strip()) < 3:
            ev.per_form[form] = per          # 1-2 znaky se nehledají vůbec
            continue
        pattern = _word_pattern(form, ignore_case=not lowercase_surface)
        for num, text in texts.items():
            found = list(pattern.finditer(text))
            if not found:
                continue
            per["hits"] += len(found)
            per["books"].append(num)
            books_with_hit.add(num)
            spans_by_book.setdefault(num, []).extend((m.start(), m.end()) for m in found)
            for m in found:
                exact = m.group(0) == form
                if exact:
                    per["case_exact"] = True
                if form == surface and exact and not lowercase_surface:
                    if len(surface) >= 5 or not _at_sentence_start(text, m.start()):
                        ev.confirm_eligible = True
        ev.per_form[form] = per
        if per["hits"]:
            ev.matched_forms.append(form)

    # hits = sjednocení rozsahů, ne součet: `Dresden` uvnitř `Harry Dresden`
    # je jeden výskyt, ne dva
    total = 0
    for num, spans in spans_by_book.items():
        merged = []
        for start, end in sorted(spans):
            if merged and start < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        total += len(merged)
    ev.hits = total
    ev.books = sorted(books_with_hit)
    return ev
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_reference_stage0.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add src/reference.py tests/test_reference_stage0.py
git commit -m "feat: hledání stupně 0 - způsobilost, aliasy, sjednocení rozsahů"
```

---

## Task 5: reference.py - stupeň 1 a souvýskyt

**Files:**
- Modify: `src/reference.py` (append)
- Create: `tests/test_reference_stage1.py`

**Interfaces:**
- Consumes: `Corpus`, `_word_pattern`
- Produces:
  - `reference.count_cz_form(corpus, form: str) -> Evidence` - přesná shoda celého slova, case-insensitive
  - `reference.books_with_en(corpus, surface: str) -> set[int]` - EN strana, bez délkového omezení, bez pravidla o začátku věty

- [ ] **Step 1: Write the failing test** — `tests/test_reference_stage1.py`

```python
from src import reference


def _corpus(cz=None, en=None):
    cz = cz or {}
    en = en or {}
    return reference.Corpus(cz=cz, en=en, manifest={}, source_root="/x")


def test_cz_form_exact_whole_word_match():
    c = _corpus(cz={1: "Sešla se Bílá rada.", 2: "nic tu není"})
    ev = reference.count_cz_form(c, "Bílá rada")
    assert ev.hits == 1 and ev.books == [1]


def test_cz_form_does_not_match_inflection():
    """Přesná shoda skloňování netoleruje - vědomé rozhodnutí, `not_attested`
    je slabý signál, ne vyvrácení."""
    c = _corpus(cz={1: "Řekl to Bílé radě večer."})
    assert reference.count_cz_form(c, "Bílá rada").hits == 0


def test_cz_form_does_not_confuse_similar_words():
    c = _corpus(cz={1: "Byla to bída rana jako hrom."})
    assert reference.count_cz_form(c, "Bílá rada").hits == 0


def test_cz_form_is_case_insensitive():
    c = _corpus(cz={1: "bílá rada rozhodla"})
    assert reference.count_cz_form(c, "Bílá rada").hits == 1


def test_books_with_en_finds_surface_on_en_side():
    c = _corpus(en={1: "The White Council met.", 2: "nothing", 3: "White Council again"})
    assert reference.books_with_en(c, "White Council") == {1, 3}


def test_books_with_en_has_no_length_limit():
    """Délkové omezení má jen stupeň 0 (ochrana před českými homonymy).
    Kdyby ho měl i books_with_en, krátké povrchy by měly vždy prázdné E
    a nikdy by se nestaly `proposed`."""
    c = _corpus(en={1: "Ed arrived.", 2: "no one"})
    assert reference.books_with_en(c, "Ed") == {1}


def test_books_with_en_ignores_sentence_start_rule():
    c = _corpus(en={1: "Bob arrived first."})
    assert reference.books_with_en(c, "Bob") == {1}


def test_books_with_en_uses_word_boundary():
    c = _corpus(en={1: "Mabel was someone else."})
    assert reference.books_with_en(c, "Mab") == set()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_reference_stage1.py -v`
Expected: FAIL - `AttributeError: ... has no attribute 'count_cz_form'`

- [ ] **Step 3: Implement** — připoj do `src/reference.py`

```python
def count_cz_form(corpus: Corpus, form: str) -> Evidence:
    """Doložení navrženého českého tvaru. PŘESNÁ shoda celého slova.

    Skloňování se netoleruje schválně: stupeň 1 nikdy nic nepředvyplňuje,
    takže tolerance kupuje málo, zatímco stojí morfologii, kterou tři pokusy
    nedokázaly napsat správně. `not_attested` proto znamená "v tomto přesném
    tvaru nedoloženo", ne "model se plete".
    """
    ev = Evidence()
    form = (form or "").strip()
    if not form:
        return ev
    pattern = _word_pattern(form, ignore_case=True)
    books = []
    for num, text in corpus.cz.items():
        n = len(pattern.findall(text))
        if n:
            ev.hits += n
            books.append(num)
    ev.books = sorted(books)
    if ev.hits:
        ev.matched_forms = [form]
        ev.per_form[form] = {"hits": ev.hits, "books": ev.books, "case_exact": False}
    return ev


def books_with_en(corpus: Corpus, surface: str) -> set:
    """Díly, kde je primární anglický povrch na EN straně.

    Jen primární povrch, ne aliasy: alias typu `sir` nebo `kid` by `E` rozšířil
    skoro na celý korpus a klasifikaci `proposed` znehodnotil.
    Žádné délkové omezení ani pravidlo o začátku věty - to je ochrana proti
    českým homonymům a v anglickém textu nedává smysl.
    """
    surface = (surface or "").strip()
    if not surface:
        return set()
    pattern = _word_pattern(surface, ignore_case=True)
    return {num for num, text in corpus.en.items() if pattern.search(text)}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_reference_stage1.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/reference.py tests/test_reference_stage1.py
git commit -m "feat: hledání stupně 1 (přesná shoda) a books_with_en"
```

---

## Task 6: agent lexicographer

**Files:**
- Create: `src/agents/lexicographer.py`
- Create: `tests/test_lexicographer.py`

**Interfaces:**
- Consumes: `src/llm/client.py` (`OutputTruncated`), `src/llm/parsing.py` (`extract_json`), `config`
- Produces:
  - `lexicographer.SYSTEM_PROMPT`
  - `lexicographer.propose(items: list[dict], client, *, model=None, max_tokens=None) -> dict[str, str | None]` - vstup `[{id, term_en, kind, note}]`, výstup mapa `id -> cz | None`

- [ ] **Step 1: Write the failing test** — `tests/test_lexicographer.py`

```python
import json
import pytest
from src.agents import lexicographer
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

ITEMS = [{"id": "terms/white council", "term_en": "White Council",
          "kind": "term", "note": "organizace"},
         {"id": "terms/warlock", "term_en": "warlock", "kind": "term", "note": ""}]


def _resp(pairs):
    return json.dumps({"proposals": [{"id": i, "cz": c} for i, c in pairs]})


def test_propose_maps_ids_to_values():
    fake = FakeLLMClient([Completion(
        _resp([("terms/white council", "Bílá rada"), ("terms/warlock", "černokněžník")]),
        False, 10, 10)])
    out = lexicographer.propose(ITEMS, fake)
    assert out == {"terms/white council": "Bílá rada", "terms/warlock": "černokněžník"}


def test_explicit_null_means_model_does_not_know():
    fake = FakeLLMClient([Completion(
        _resp([("terms/white council", "Bílá rada"), ("terms/warlock", None)]),
        False, 10, 10)])
    assert lexicographer.propose(ITEMS, fake)["terms/warlock"] is None


def test_duplicate_id_raises():
    fake = FakeLLMClient([Completion(
        _resp([("terms/white council", "A"), ("terms/white council", "B"),
               ("terms/warlock", "C")]), False, 10, 10)])
    with pytest.raises(ValueError, match="[Dd]uplicit"):
        lexicographer.propose(ITEMS, fake)


def test_unknown_id_is_ignored():
    fake = FakeLLMClient([Completion(
        _resp([("terms/white council", "Bílá rada"), ("terms/warlock", "x"),
               ("terms/neznamy", "y")]), False, 10, 10)])
    out = lexicographer.propose(ITEMS, fake)
    assert "terms/neznamy" not in out


def test_missing_id_raises_because_result_is_incomplete():
    """Chybějící položka != explicitní null. Model na ni zapomněl, výsledek je
    neúplný a běh musí selhat atomicky."""
    fake = FakeLLMClient([Completion(_resp([("terms/white council", "Bílá rada")]),
                                     False, 10, 10)])
    with pytest.raises(ValueError, match="chyb"):
        lexicographer.propose(ITEMS, fake)


def test_non_string_cz_raises():
    raw = json.dumps({"proposals": [{"id": "terms/white council", "cz": 42},
                                    {"id": "terms/warlock", "cz": None}]})
    with pytest.raises(ValueError):
        lexicographer.propose(ITEMS, FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_truncated_retries_once_with_double_tokens():
    seen = []
    def gen(**kw):
        seen.append(kw["max_tokens"])
        if len(seen) == 1:
            return Completion("{partial", True, 5, 5)
        return Completion(_resp([("terms/white council", "A"), ("terms/warlock", "B")]),
                          False, 5, 5)
    out = lexicographer.propose(ITEMS, FakeLLMClient(gen), max_tokens=1000)
    assert seen == [1000, 2000]
    assert out["terms/warlock"] == "B"


def test_truncated_twice_raises():
    fake = FakeLLMClient([Completion("{a", True, 5, 5), Completion("{b", True, 5, 5)])
    with pytest.raises(OutputTruncated):
        lexicographer.propose(ITEMS, fake)


def test_prompt_contains_ids_and_notes():
    seen = {}
    def gen(**kw):
        seen.update(kw)
        return Completion(_resp([("terms/white council", "A"), ("terms/warlock", "B")]),
                          False, 5, 5)
    lexicographer.propose(ITEMS, FakeLLMClient(gen))
    assert "terms/white council" in seen["user"]
    assert "organizace" in seen["user"]
    assert "null" in lexicographer.SYSTEM_PROMPT
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_lexicographer.py -v`
Expected: FAIL - no module `src.agents.lexicographer`

- [ ] **Step 3: Implement `src/agents/lexicographer.py`**

```python
"""Lexikograf - navrhne zavedený český tvar termínu z české edice série.

Jeho návrh sám o sobě nemá váhu; teprve `reference_mine` ho ověří proti korpusu.
Agent proto nezná korpus, databázi ani soubory - dostane seznam, vrátí mapu.
"""
import config
from src.llm.client import OutputTruncated
from src.llm.parsing import extract_json

SYSTEM_PROMPT = """Jsi znalec české edice knižní série. Dostaneš seznam
anglických termínů a jmen a u každého vrátíš **zavedený český tvar**, jak se
používá v oficiálním překladu téhle série.

Vrať POUZE JSON, žádný text kolem:
{"proposals": [{"id": "<id z dotazu, doslova>", "cz": "<český tvar nebo null>"}]}

Pravidla:
- **Když termín neznáš, vrať `null`. Nehádej a nevymýšlej.** Tvůj návrh se bude
  ověřovat proti skutečnému textu překladů; vymyšlený tvar tam nebude a jen
  přidá práci člověku.
- `id` opiš přesně, jak přišlo v dotazu. Podle něj se odpověď páruje.
- Vrať položku pro **každé** `id` z dotazu, i kdyby byla `null`.
- `cz` je jen samotný tvar, žádná věta ani vysvětlení."""


def _format_items(items) -> str:
    lines = []
    for it in items:
        note = f"  (poznámka: {it['note']})" if it.get("note") else ""
        lines.append(f"- id={it['id']} | {it.get('kind', 'term')}: "
                     f"{it['term_en']}{note}")
    return "\n".join(lines)


def propose(items, client, *, model=None, max_tokens=None):
    """Vrací {id: cz | None}. Neúplná nebo rozbitá odpověď = ValueError."""
    if not items:
        return {}
    model = model or config.MODEL_LEXICOGRAPHER
    tokens = max_tokens or config.MAX_TOKENS_LEXICOGRAPHER
    user = ("Vrať zavedené české tvary pro tyto položky:\n\n"
            + _format_items(items))

    comp = None
    for attempt in range(2):
        comp = client.complete(system=SYSTEM_PROMPT, user=user,
                               max_tokens=tokens, model=model)
        if not comp.truncated:
            break
        tokens *= 2          # jeden pokus s dvojnásobným prostorem
    if comp.truncated:
        raise OutputTruncated(
            "Lexikograf vrátil useknutý výstup i po zvýšení max_tokens.")

    data = extract_json(comp.text)
    wanted = {it["id"] for it in items}
    out, seen = {}, set()
    for row in data.get("proposals") or []:
        rid = row.get("id")
        if rid in seen:
            raise ValueError(f"Duplicitní id v odpovědi lexikografa: {rid!r}")
        seen.add(rid)
        if rid not in wanted:
            print(f"lexikograf: ignoruji cizí id {rid!r}")
            continue
        cz = row.get("cz")
        if cz is not None and not isinstance(cz, str):
            raise ValueError(f"cz u {rid!r} není řetězec ani null: {cz!r}")
        out[rid] = cz.strip() if isinstance(cz, str) and cz.strip() else None
    missing = wanted - set(out)
    if missing:
        # Chybějící položka není totéž co explicitní null - model na ni
        # zapomněl, výsledek je neúplný a běh selže atomicky.
        raise ValueError(
            f"Lexikograf vynechal {len(missing)} položek, výsledek je neúplný: "
            + ", ".join(sorted(missing)[:5]))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_lexicographer.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agents/lexicographer.py tests/test_lexicographer.py
git commit -m "feat: agent lexicographer (návrh českých tvarů, null = neznám)"
```

---

## Task 7: reference_mine - klasifikace a resolve

**Files:**
- Create: `src/reference_mine.py`
- Create: `tests/test_reference_mine.py`

**Interfaces:**
- Consumes: `src/reference.py`, `src/agents/lexicographer.py`, `config`
- Produces:
  - `reference_mine.SurfaceItem` / `Finding` (TypedDict, tvary ze specu)
  - `reference_mine.classify(ev0, proposal, cz_ev, cooccurrence, e_books, cfg) -> str` - vrací název třídy
  - `reference_mine.resolve(corpus, items, client_factory, cfg) -> list[Finding]`

- [ ] **Step 1: Write the failing test** — `tests/test_reference_mine.py`

```python
import pytest
from src import reference, reference_mine
from src.llm.client import Completion, FakeLLMClient
from src.agents import lexicographer
import config


def _corpus(cz=None, en=None):
    return reference.Corpus(cz=cz or {}, en=en or {}, manifest={}, source_root="/x")


def _items(*surfaces):
    return [{"id": f"terms/{s.lower()}", "section": "terms", "surface": s,
             "aliases": [], "note": ""} for s in surfaces]


def _client_factory(mapping):
    """Fake lexikograf vracející danou mapu id -> cz."""
    import json
    def factory(_agent):
        payload = json.dumps({"proposals": [{"id": k, "cz": v}
                                            for k, v in mapping.items()]})
        return FakeLLMClient([Completion(payload, False, 10, 10)])
    return factory


def test_confirmed_when_eligible_and_above_thresholds(monkeypatch):
    monkeypatch.setattr(config, "REFERENCE_MIN_HITS", 3)
    monkeypatch.setattr(config, "REFERENCE_MIN_BOOKS", 2)
    cz = {i: "Potkal Mab uprostřed věty." for i in (1, 2, 3)}
    f = reference_mine.resolve(_corpus(cz=cz), _items("Mab"),
                               _client_factory({}), config)[0]
    assert f["classification"] == "confirmed"
    assert f["cz"] == "Mab" and f["primary_attested"] is True


def test_weak_when_eligible_but_below_thresholds(monkeypatch):
    monkeypatch.setattr(config, "REFERENCE_MIN_HITS", 50)
    cz = {1: "Potkal Mab uprostřed věty."}
    f = reference_mine.resolve(_corpus(cz=cz), _items("Mab"),
                               _client_factory({}), config)[0]
    assert f["classification"] == "weak" and f["cz"] == "Mab"


def test_lowercase_word_becomes_evidence_only_and_goes_to_stage1(monkeypatch):
    """`stole` se najde, ale nesmí se předvyplnit ani zabránit dotazu modelu."""
    cz = {i: "Kniha na stole a zase na stole." for i in (1, 2, 3)}
    factory = _client_factory({"terms/stole": None})
    f = reference_mine.resolve(_corpus(cz=cz), _items("stole"), factory, config)[0]
    assert f["classification"] == "evidence_only"
    assert f["cz"] is None
    assert f["hits"] > 0


def test_proposed_when_model_suggests_and_cooccurrence_holds(monkeypatch):
    monkeypatch.setattr(config, "REFERENCE_COOCCUR_RATIO", 0.5)
    corpus = _corpus(cz={1: "Sešla se Bílá rada.", 2: "Bílá rada opět."},
                     en={1: "The White Council met.", 2: "White Council again."})
    factory = _client_factory({"terms/white council": "Bílá rada"})
    f = reference_mine.resolve(corpus, _items("White Council"), factory, config)[0]
    assert f["classification"] == "proposed"
    assert f["navrh"] == "Bílá rada"
    assert f["cz"] is None                       # návrh se NEPŘEDVYPLŇUJE
    assert f["cooccurrence"] == [1, 2]


def test_not_attested_when_form_missing_in_corpus():
    corpus = _corpus(cz={1: "nic tu není", 2: "ani tady"},
                     en={1: "The White Council met.", 2: "White Council again."})
    factory = _client_factory({"terms/white council": "Vymyšlená rada"})
    f = reference_mine.resolve(corpus, _items("White Council"), factory, config)[0]
    assert f["classification"] == "not_attested" and f["cz"] is None


def test_not_attested_when_cooccurrence_below_ratio(monkeypatch):
    monkeypatch.setattr(config, "REFERENCE_COOCCUR_RATIO", 0.5)
    # EN termín ve 4 dílech, český tvar jen v jednom -> 1 < ceil(0.5*4)=2
    corpus = _corpus(cz={1: "Bílá rada", 2: "x", 3: "y", 4: "z"},
                     en={i: "White Council" for i in (1, 2, 3, 4)})
    factory = _client_factory({"terms/white council": "Bílá rada"})
    f = reference_mine.resolve(corpus, _items("White Council"), factory, config)[0]
    assert f["classification"] == "not_attested"


def test_empty_e_gives_not_attested():
    """Termín, který je nový až v jedenáctce - korpus k němu nemá co říct."""
    corpus = _corpus(cz={1: "Nikdykdy je divné"}, en={1: "nothing here"})
    factory = _client_factory({"terms/nevernever": "Nikdykdy"})
    f = reference_mine.resolve(corpus, _items("Nevernever"), factory, config)[0]
    assert f["classification"] == "not_attested"


def test_unresolved_when_nothing_found_and_model_returns_null():
    corpus = _corpus(cz={1: "nic"}, en={1: "nic"})
    factory = _client_factory({"terms/nevernever": None})
    f = reference_mine.resolve(corpus, _items("Nevernever"), factory, config)[0]
    assert f["classification"] == "unresolved" and f["source"] == "none"


def test_alias_only_is_evidence_only_without_prefill():
    corpus = _corpus(cz={i: "Přišel Dresden pozdě." for i in (1, 2, 3)},
                     en={1: "Harry Dresden"})
    items = [{"id": "characters/harry dresden", "section": "characters",
              "surface": "Harry Dresden", "aliases": ["Dresden"], "note": ""}]
    factory = _client_factory({"characters/harry dresden": None})
    f = reference_mine.resolve(corpus, items, factory, config)[0]
    assert f["classification"] == "evidence_only"
    assert f["primary_attested"] is False and f["cz"] is None
    assert "Dresden" in f["matched_forms"]


def test_stage1_only_gets_unresolved_surfaces(monkeypatch):
    """Do stupně 1 nesmí jít to, co stupeň 0 doložil jako způsobilé - platilo
    by se za dotaz, který nic nepřinese."""
    monkeypatch.setattr(config, "REFERENCE_MIN_HITS", 1)
    monkeypatch.setattr(config, "REFERENCE_MIN_BOOKS", 1)
    corpus = _corpus(cz={1: "Potkal Mab uprostřed."}, en={1: "Mab"})
    asked = []
    def factory(_agent):
        import json
        def gen(**kw):
            asked.append(kw["user"])
            return Completion(json.dumps({"proposals": []}), False, 5, 5)
        return FakeLLMClient(gen)
    reference_mine.resolve(corpus, _items("Mab"), factory, config)
    assert asked == []          # model se vůbec nevolal


def test_batches_respect_configured_size(monkeypatch):
    monkeypatch.setattr(config, "REFERENCE_BATCH_SIZE", 2)
    corpus = _corpus(cz={1: "nic"}, en={1: "nic"})
    items = _items("Aaa", "Bbb", "Ccc", "Ddd", "Eee")
    calls = []
    def factory(_agent):
        import json
        def gen(**kw):
            ids = [l.split("id=")[1].split(" |")[0]
                   for l in kw["user"].splitlines() if "id=" in l]
            calls.append(len(ids))
            return Completion(json.dumps(
                {"proposals": [{"id": i, "cz": None} for i in ids]}), False, 5, 5)
        return FakeLLMClient(gen)
    reference_mine.resolve(corpus, items, factory, config)
    assert calls == [2, 2, 1]
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_reference_mine.py -v`
Expected: FAIL - no module `src.reference_mine`

- [ ] **Step 3: Implement `src/reference_mine.py`**

```python
"""Orchestrace těžby: korpus + lexikograf → nálezy.

Jediné místo, které drátuje hledání a agenta dohromady. Nezná databázi ani
glosář - výsledek jen vrací; zápis dělá volající.
"""
import math

from src import reference
from src.agents import lexicographer


def _finding(item, ev0, cz_ev, proposal, cooccurrence, classification, cz):
    source = ("kept" if classification in ("confirmed", "weak", "evidence_only")
              else "proposed" if classification in ("proposed", "not_attested")
              else "none")
    return {
        "id": item["id"],
        "section": item["section"],
        "surface": item["surface"],
        "cz": cz,
        "classification": classification,
        "primary_attested": bool(ev0.per_form.get(item["surface"], {}).get("hits")),
        "navrh": proposal,
        "hits": ev0.hits,
        "books": ev0.books,
        "per_form": ev0.per_form,
        "cooccurrence": sorted(cooccurrence),
        "matched_forms": ev0.matched_forms,
        "matched_cz": (item["surface"] if classification in ("confirmed", "weak")
                       else (proposal if cz_ev and cz_ev.hits else None)),
        "source": source,
    }


def classify(ev0, proposal, cz_ev, cooccurrence, e_books, cfg) -> str:
    """Precedence tříd. Kroky 1 a 2 se týkají JEN způsobilých povrchů - bez
    toho by `stole` (79 výskytů, malé písmeno) spadlo do `weak`, `weak`
    předvyplňuje, a byla by zpět chyba, kvůli které tenhle aparát existuje."""
    primary_hits = ev0.hits
    if ev0.confirm_eligible:
        if (primary_hits >= cfg.REFERENCE_MIN_HITS
                and len(ev0.books) >= cfg.REFERENCE_MIN_BOOKS):
            return "confirmed"
        return "weak"
    if proposal:
        needed = max(1, math.ceil(cfg.REFERENCE_COOCCUR_RATIO * len(e_books)))
        if e_books and len(cooccurrence) >= needed:
            return "proposed"
        return "not_attested"
    if ev0.hits:
        return "evidence_only"
    return "unresolved"


def resolve(corpus, items, client_factory, cfg):
    """Vrací list[Finding]. Selhání kdekoli propaguje výjimku - běh je atomický."""
    stage0, pending = {}, []
    for item in items:
        ev = reference.count_en_surface(corpus, item["surface"], item.get("aliases") or [])
        stage0[item["id"]] = ev
        # Do stupně 1 jde jen to, co stupeň 0 nedoložil jako přímý důkaz
        # ponechání. Nezpůsobilý povrch (obecné slovo, jen alias) tam jde taky.
        if not ev.confirm_eligible:
            pending.append(item)

    proposals = {}
    size = max(1, cfg.REFERENCE_BATCH_SIZE)
    for start in range(0, len(pending), size):
        batch = pending[start:start + size]
        payload = [{"id": i["id"], "term_en": i["surface"],
                    "kind": i["section"], "note": i.get("note", "")} for i in batch]
        proposals.update(lexicographer.propose(
            payload, client_factory("lexicographer"),
            model=cfg.MODEL_LEXICOGRAPHER,
            max_tokens=cfg.MAX_TOKENS_LEXICOGRAPHER))

    findings = []
    for item in items:
        ev0 = stage0[item["id"]]
        proposal = proposals.get(item["id"])
        cz_ev = reference.count_cz_form(corpus, proposal) if proposal else None
        e_books = reference.books_with_en(corpus, item["surface"]) if proposal else set()
        cooccurrence = (e_books & set(cz_ev.books)) if cz_ev else set()
        classification = classify(ev0, proposal, cz_ev, cooccurrence, e_books, cfg)
        # Předvyplňuje se JEN doložené ponechání; návrhy nikdy.
        cz = item["surface"] if classification in ("confirmed", "weak") else None
        findings.append(_finding(item, ev0, cz_ev, proposal, cooccurrence,
                                 classification, cz))
    return findings
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_reference_mine.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/reference_mine.py tests/test_reference_mine.py
git commit -m "feat: reference_mine - precedence klasifikace, souvýskyt, dávkování"
```

---

## Task 8: persistence reference.json + fingerprint

**Files:**
- Modify: `src/reference_mine.py` (append)
- Create: `tests/test_reference_persist.py`

**Interfaces:**
- Consumes: `src/reference.py` (`build_manifest`)
- Produces:
  - `reference_mine.SCHEMA_VERSION = 1`
  - `reference_mine.draft_fingerprint(draft) -> str` - sha1 klíčů, aliasů a poznámek
  - `reference_mine.thresholds_fingerprint(cfg) -> str`
  - `reference_mine.corpus_fingerprint(root) -> str | None` - `None` když je kořen nedostupný
  - `reference_mine.write_reference(findings, path, run_id, fingerprint, source_root) -> None`
  - `reference_mine.load_reference(path) -> dict | None`

- [ ] **Step 1: Write the failing test** — `tests/test_reference_persist.py`

```python
import json
import os
from src import reference_mine
import config


def _finding(**over):
    base = {"id": "terms/x", "section": "terms", "surface": "X", "cz": None,
            "classification": "unresolved", "primary_attested": False,
            "navrh": None, "hits": 0, "books": [], "per_form": {},
            "cooccurrence": [], "matched_forms": [], "matched_cz": None,
            "source": "none"}
    base.update(over)
    return base


def _fp():
    return {"draft": "a", "corpus": "b", "thresholds": "c"}


def test_write_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "reference.json")
    reference_mine.write_reference([_finding()], p, 7, _fp(), "/root")
    data = reference_mine.load_reference(p)
    assert data["run_id"] == 7 and data["source_root"] == "/root"
    assert data["findings"][0]["id"] == "terms/x"


def test_write_is_atomic_no_tmp_left(tmp_path):
    p = str(tmp_path / "reference.json")
    reference_mine.write_reference([_finding()], p, 1, _fp(), "/root")
    assert not os.path.exists(p + ".tmp")


def test_load_missing_file_returns_none(tmp_path):
    assert reference_mine.load_reference(str(tmp_path / "nic.json")) is None


def test_load_broken_json_returns_none(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text("{tohle neni json", encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_unknown_schema_version_returns_none(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 99, "findings": []}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_duplicate_ids(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(), _finding()]}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_unknown_classification(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(classification="nesmysl")]}),
                 encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_draft_fingerprint_changes_with_notes():
    a = {"characters": [{"name_en": "Harry", "aliases": ["Dresden"], "note": "hrdina"}],
         "places": [], "terms": [], "relationships": [], "must_decide": []}
    b = {"characters": [{"name_en": "Harry", "aliases": ["Dresden"], "note": "jiná"}],
         "places": [], "terms": [], "relationships": [], "must_decide": []}
    # poznámka se posílá lexikografovi a mění jeho návrh, takže musí být v otisku
    assert reference_mine.draft_fingerprint(a) != reference_mine.draft_fingerprint(b)


def test_thresholds_fingerprint_ignores_paths(monkeypatch):
    before = reference_mine.thresholds_fingerprint(config)
    monkeypatch.setattr(config, "REFERENCE_PATH", "data/jinak.json")
    assert reference_mine.thresholds_fingerprint(config) == before
    monkeypatch.setattr(config, "REFERENCE_MIN_HITS", 99)
    assert reference_mine.thresholds_fingerprint(config) != before


def test_corpus_fingerprint_none_for_missing_root(tmp_path):
    assert reference_mine.corpus_fingerprint(str(tmp_path / "neexistuje")) is None
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_reference_persist.py -v`
Expected: FAIL - `AttributeError: ... has no attribute 'write_reference'`

- [ ] **Step 3: Implement** — připoj do `src/reference_mine.py`

```python
import hashlib
import json
import os

SCHEMA_VERSION = 1
_SECTIONS = {"characters", "places", "terms"}
_CLASSES = {"confirmed", "weak", "evidence_only", "proposed", "not_attested",
            "unresolved"}
_REQUIRED = ("id", "section", "surface", "cz", "classification",
             "primary_attested", "navrh", "hits", "books", "per_form",
             "cooccurrence", "matched_forms", "matched_cz", "source")


def _sha1(obj) -> str:
    return hashlib.sha1(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def draft_fingerprint(draft: dict) -> str:
    """Klíče, aliasy a poznámky. Poznámky proto, že se posílají lexikografovi
    a mění jeho návrh - draft se stejnými klíči, ale jinými poznámkami, může
    dát jiný výsledek."""
    rows = []
    for section, key in (("characters", "name_en"), ("places", "name_en"),
                         ("terms", "term_en")):
        for item in draft.get(section) or []:
            rows.append([section, item.get(key) or "",
                         sorted(item.get("aliases") or []), item.get("note") or ""])
    return _sha1(sorted(rows))


def thresholds_fingerprint(cfg) -> str:
    """Jen hodnoty, které ovlivňují důkaz - ne cesty, model ani velikost dávky."""
    return _sha1([cfg.REFERENCE_MIN_HITS, cfg.REFERENCE_MIN_BOOKS,
                  cfg.REFERENCE_MIN_CORPUS_BOOKS, cfg.REFERENCE_COOCCUR_RATIO])


def corpus_fingerprint(root: str):
    """None = kořen není dostupný; volající to musí brát jako 'nevím'."""
    if not root or not os.path.isdir(root):
        return None
    return _sha1(reference.build_manifest(root))


def write_reference(findings, path, run_id, fingerprint, source_root) -> None:
    """Nahrazuje soubor celý. Žádné slévání s předchozím - selhání je atomické,
    takže se sem dostane jen kompletní výsledek."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"schema_version": SCHEMA_VERSION, "run_id": run_id,
                   "source_root": source_root, "fingerprint": fingerprint,
                   "findings": findings}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_reference(path: str):
    """None u chybějícího, nečitelného i schématu neodpovídajícího souboru.
    Poškozený soubor nesmí shodit `review`."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        return None
    except ValueError:
        print(f"reference: {path} není platný JSON, ignoruji")
        return None
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        print(f"reference: {path} má neznámou verzi schématu, ignoruji")
        return None
    findings = data.get("findings")
    if not isinstance(findings, list):
        print(f"reference: {path} nemá seznam nálezů, ignoruji")
        return None
    seen = set()
    for f in findings:
        if not isinstance(f, dict) or any(k not in f for k in _REQUIRED):
            print(f"reference: {path} má nález s chybějícím polem, ignoruji")
            return None
        if f["section"] not in _SECTIONS or f["classification"] not in _CLASSES:
            print(f"reference: {path} má neznámou sekci nebo třídu, ignoruji")
            return None
        if f["id"] in seen:
            print(f"reference: {path} má duplicitní id {f['id']!r}, ignoruji")
            return None
        seen.add(f["id"])
    return data
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_reference_persist.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/reference_mine.py tests/test_reference_persist.py
git commit -m "feat: reference.json - atomický zápis, validace schématu, otisky"
```

---

## Task 9: guide.merge_sources - slití tří zdrojů a provenience

**Files:**
- Modify: `src/guide.py`
- Create: `tests/test_merge_sources.py`

**Interfaces:**
- Consumes: `src/textnorm.py`, `src/reference_mine.py` (`corpus_fingerprint`, `draft_fingerprint`, `thresholds_fingerprint`)
- Produces:
  - `guide.merge_sources(draft, guide_data, reference=None, *, cfg=None) -> dict` - přednost `guide` > `reference` > `draft`
  - `guide.merge_draft_and_guide(draft, guide_data)` zůstává jako tenký obal (`reference=None`)
  - každá položka nese `provenance` (`human`/`reference`/`none`), `scout_suggestion`, `lexicographer_suggestion` a blok `reference`

- [ ] **Step 1: Write the failing test** — `tests/test_merge_sources.py`

```python
from src import guide, reference_mine
import config


def _draft():
    return {"characters": [{"name_en": "Harry", "aliases": ["Dresden"],
                            "suggested": "keep", "note": "hrdina"}],
            "places": [],
            "terms": [{"term_en": "White Council", "suggested_cz": "Rada scouta",
                       "note": ""}],
            "relationships": [], "style_notes": "sarkastický", "must_decide": []}


def _empty_guide():
    return {"characters": [], "places": [], "terms": [], "relationships": [],
            "style": "", "rules": []}


def _reference(findings, fp=None):
    return {"schema_version": 1, "run_id": 1, "source_root": "/root",
            "fingerprint": fp or {"draft": "?", "corpus": "?", "thresholds": "?"},
            "findings": findings}


def _f(**over):
    base = {"id": "terms/white council", "section": "terms",
            "surface": "White Council", "cz": None, "classification": "unresolved",
            "primary_attested": False, "navrh": None, "hits": 0, "books": [],
            "per_form": {}, "cooccurrence": [], "matched_forms": [],
            "matched_cz": None, "source": "none"}
    base.update(over)
    return base


def _fresh_fp(draft):
    return {"draft": reference_mine.draft_fingerprint(draft),
            "corpus": None,
            "thresholds": reference_mine.thresholds_fingerprint(config)}


def test_confirmed_prefills_cz_and_sets_provenance():
    d = _draft()
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", hits=12, books=[1, 2])],
                     _fresh_fp(d))
    m = guide.merge_sources(d, _empty_guide(), ref, cfg=config)
    term = [t for t in m["terms"] if t["term_en"] == "White Council"][0]
    assert term["cz"] == "White Council"
    assert term["provenance"] == "reference"
    assert term["reference"]["hits"] == 12


def test_proposed_leaves_cz_empty_and_keeps_suggestion_separate():
    d = _draft()
    ref = _reference([_f(classification="proposed", navrh="Bílá rada",
                         matched_cz="Bílá rada")], _fresh_fp(d))
    m = guide.merge_sources(d, _empty_guide(), ref, cfg=config)
    term = m["terms"][0]
    assert term["cz"] == ""                       # NEPŘEDVYPLNĚNO
    assert term["provenance"] == "none"
    assert term["lexicographer_suggestion"] == "Bílá rada"
    assert term["scout_suggestion"] == "Rada scouta"   # oba návrhy současně


def test_scout_suggestion_never_prefills_glossary_field():
    """guide.py dřív předvyplňoval cz ze suggested_cz - to je odhad bez důkazu."""
    m = guide.merge_sources(_draft(), _empty_guide(), None, cfg=config)
    assert m["terms"][0]["cz"] == ""
    assert m["terms"][0]["scout_suggestion"] == "Rada scouta"


def test_human_value_wins_over_reference():
    d = _draft()
    g = _empty_guide()
    g["terms"] = [{"term_en": "White Council", "cz": "Moje rada"}]
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", hits=9, books=[1, 2])],
                     _fresh_fp(d))
    m = guide.merge_sources(d, g, ref, cfg=config)
    term = m["terms"][0]
    assert term["cz"] == "Moje rada" and term["provenance"] == "human"


def test_stale_fingerprint_suppresses_everything_from_reference():
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", hits=12, books=[1, 2])],
                     {"draft": "jiny", "corpus": None, "thresholds": "jiny"})
    m = guide.merge_sources(_draft(), _empty_guide(), ref, cfg=config)
    term = m["terms"][0]
    assert term["cz"] == ""
    assert term["reference"]["fresh"] is False
    assert "hits" not in term["reference"]         # žádné číselné důkazy


def test_stale_reference_does_not_suppress_human_value():
    g = _empty_guide()
    g["terms"] = [{"term_en": "White Council", "cz": "Moje rada"}]
    ref = _reference([_f(classification="confirmed", cz="White Council")],
                     {"draft": "jiny", "corpus": None, "thresholds": "jiny"})
    m = guide.merge_sources(_draft(), g, ref, cfg=config)
    assert m["terms"][0]["cz"] == "Moje rada"


def test_evidence_binding_hides_numbers_when_value_differs():
    d = _draft()
    g = _empty_guide()
    g["terms"] = [{"term_en": "White Council", "cz": "Něco jiného"}]
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", hits=12, books=[1])],
                     _fresh_fp(d))
    m = guide.merge_sources(d, g, ref, cfg=config)
    assert "hits" not in m["terms"][0]["reference"]


def test_evidence_only_always_shows_its_evidence():
    """Třída, jejímž jediným obsahem je důkaz, ho musí ukázat i s prázdným cz."""
    d = _draft()
    ref = _reference([_f(classification="evidence_only", hits=79, books=[1, 2, 3],
                         matched_forms=["stole"])], _fresh_fp(d))
    m = guide.merge_sources(d, _empty_guide(), ref, cfg=config)
    assert m["terms"][0]["reference"]["hits"] == 79


def test_merge_draft_and_guide_still_works():
    m = guide.merge_draft_and_guide(_draft(), _empty_guide())
    assert m["terms"][0]["term_en"] == "White Council"
    assert m["style"] == "sarkastický"


def test_missing_reference_block_does_not_break():
    m = guide.merge_sources(_draft(), _empty_guide(), None, cfg=config)
    assert m["characters"][0]["name_en"] == "Harry"
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_merge_sources.py -v`
Expected: FAIL - `AttributeError: module 'src.guide' has no attribute 'merge_sources'`

- [ ] **Step 3: Implement in `src/guide.py`**

Nahraď stávající `merge_draft_and_guide` tímto (starý název zůstává jako obal):

```python
def _reference_index(reference):
    if not reference:
        return {}
    return {f["id"]: f for f in reference.get("findings") or []}


def _is_fresh(reference, draft, cfg) -> bool:
    """Jeden příznak, ne tři: čerstvé je jen to, kde sedí otisk draftu, korpusu
    i prahů. Nedostupný korpus se chová jako nečerstvý - radši nepředvyplnit
    než předvyplnit z neznámého podkladu."""
    if not reference or cfg is None:
        return False
    from src import reference_mine
    fp = reference.get("fingerprint") or {}
    if fp.get("draft") != reference_mine.draft_fingerprint(draft):
        return False
    if fp.get("thresholds") != reference_mine.thresholds_fingerprint(cfg):
        return False
    current_corpus = reference_mine.corpus_fingerprint(reference.get("source_root") or "")
    return current_corpus is not None and fp.get("corpus") == current_corpus


def _reference_block(finding, fresh, shown_cz):
    """Nečerstvá reference nepřispívá ničím než poznámkou. U čerstvé se číselný
    důkaz vynechá, liší-li se zobrazená hodnota od té, ke které se důkaz váže -
    ale jen u tříd, které hodnotu předvyplňují; `evidence_only` má cz prázdné
    záměrně a jeho důkaz je jediný obsah, který má."""
    if not fresh:
        return {"fresh": False, "classification": finding["classification"]}
    block = {"fresh": True, "classification": finding["classification"],
             "primary_attested": finding["primary_attested"],
             "matched_forms": finding["matched_forms"],
             "matched_cz": finding["matched_cz"]}
    prefilling = finding["classification"] in ("confirmed", "weak")
    if prefilling and shown_cz and shown_cz != finding["matched_cz"]:
        return block
    block.update({"hits": finding["hits"], "books": finding["books"],
                  "per_form": finding["per_form"],
                  "cooccurrence": finding["cooccurrence"]})
    return block


def _merge_section(draft, guide_data, ref_index, fresh, section, key_field,
                   is_character=False):
    from src import textnorm
    g_map = {normalize(i.get(key_field, "")): i for i in (guide_data.get(section) or [])}
    out, done = [], set()
    for d in (draft.get(section) or []):
        name = d.get(key_field, "")
        g = g_map.get(normalize(name), {})
        done.add(normalize(name))
        fid = f"{section}/{textnorm.normalize_key(name)}"
        finding = ref_index.get(fid)

        scout_suggestion = (d.get("suggested_cz") if not is_character
                            else None) or None
        lex_suggestion = finding.get("navrh") if finding else None

        human_cz = (g.get("cz") or "").strip()
        ref_cz = (finding.get("cz") or "") if (finding and fresh) else ""
        cz = human_cz or ref_cz or ""
        provenance = "human" if human_cz else ("reference" if ref_cz else "none")

        row = {key_field: name, "cz": cz, "note": d.get("note") or "",
               "aliases": g.get("aliases") or d.get("aliases") or [],
               "provenance": provenance,
               "scout_suggestion": scout_suggestion,
               "lexicographer_suggestion": lex_suggestion}
        if is_character:
            human_render = g.get("render")
            ref_render = "keep" if ref_cz else None
            row["render"] = human_render or ref_render or ""
            row["scout_suggestion"] = d.get("suggested") or None
        if finding:
            row["reference"] = _reference_block(finding, fresh, cz)
        out.append(row)

    for key, g in g_map.items():
        if key in done:
            continue
        row = {key_field: g.get(key_field, ""), "cz": g.get("cz") or "",
               "note": "", "aliases": g.get("aliases") or [],
               "provenance": "human" if g.get("cz") else "none",
               "scout_suggestion": None, "lexicographer_suggestion": None}
        if is_character:
            row["render"] = g.get("render") or ""
        out.append(row)
    return out


def merge_sources(draft: dict, guide_data: dict, reference=None, *, cfg=None) -> dict:
    """Podklad pro review UI ze tří zdrojů. Přednost: guide > reference > draft.

    Glosářová pole (`cz`, `render`) se předvyplňují JEN z doložené reference -
    scoutův ani lexikografův odhad se do nich nedostane. Oba návrhy se drží
    odděleně, aby je formulář mohl nabídnout tlačítkem.
    """
    draft = draft or {}
    guide_data = guide_data or {}
    ref_index = _reference_index(reference)
    fresh = _is_fresh(reference, draft, cfg)

    characters = _merge_section(draft, guide_data, ref_index, fresh,
                                "characters", "name_en", is_character=True)
    places = _merge_section(draft, guide_data, ref_index, fresh, "places", "name_en")
    terms = _merge_section(draft, guide_data, ref_index, fresh, "terms", "term_en")

    g_rel = {relationship_key(r.get("a", ""), r.get("b", "")): r
             for r in (guide_data.get("relationships") or [])}
    out_rel, done_rel = [], set()
    for d in (draft.get("relationships") or []):
        k = relationship_key(d.get("a", ""), d.get("b", ""))
        g = g_rel.get(k, {})
        done_rel.add(k)
        # Vztahy a styl těžba nepokrývá, takže scoutův návrh zůstává předvyplněný;
        # sekce vztahů to vyvažuje zaškrtnutím "zkontrolováno" před uložením.
        out_rel.append({"a": d.get("a", ""), "b": d.get("b", ""),
                        "address": g.get("address") or d.get("suggested") or ""})
    for k, g in g_rel.items():
        if k not in done_rel:
            out_rel.append({"a": g.get("a", ""), "b": g.get("b", ""),
                            "address": g.get("address") or ""})

    return {"characters": characters, "places": places, "terms": terms,
            "relationships": out_rel,
            "style": guide_data.get("style") or draft.get("style_notes", "") or "",
            "rules": guide_data.get("rules") or [],
            "must_decide": draft.get("must_decide") or []}


def merge_draft_and_guide(draft: dict, guide_data: dict) -> dict:
    """Tenký obal kvůli zpětné kompatibilitě."""
    return merge_sources(draft, guide_data, None)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_merge_sources.py tests/test_guide.py -v`
Expected: PASS. Pozor: `tests/test_guide.py::test_merge_translates_draft_field_names_to_final` a `test_merge_keeps_human_decisions` **budou padat** - dřív očekávaly předvyplnění ze `suggested_cz`/`suggested`, což je právě to, co se ruší.

- [ ] **Step 5: Update the two stale tests in `tests/test_guide.py`**

```python
def test_merge_translates_draft_field_names_to_final(tmp_path):
    draft = {"characters": [{"name_en": "Bob", "suggested": "translate", "note": "x"}],
             "places": [{"name_en": "Chicago", "suggested_cz": "Chicago", "note": ""}],
             "terms": [{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
             "relationships": [], "must_decide": [], "style_notes": "sarkastický"}
    g = {"characters": [], "places": [], "terms": [], "relationships": [],
         "style": "", "rules": []}
    m = guide.merge_draft_and_guide(draft, g)
    assert m["style"] == "sarkastický"
    # scoutův návrh se drží ODDĚLENĚ, nepředvyplňuje se do cz
    assert m["terms"][0]["term_en"] == "Nevernever"
    assert m["terms"][0]["cz"] == ""
    assert m["terms"][0]["scout_suggestion"] == "Nikdykdy"
    assert m["places"][0]["scout_suggestion"] == "Chicago"
    assert m["characters"][0]["scout_suggestion"] == "translate"


def test_merge_keeps_human_decisions(tmp_path):
    draft = {"characters": [{"name_en": "Harry", "suggested": "keep", "note": "hrdina"},
                            {"name_en": "NewGuy", "suggested": "translate", "note": ""}],
             "places": [], "terms": [], "relationships": [], "must_decide": []}
    g = {"characters": [{"name_en": "Harry", "render": "keep", "cz": "Harry"}],
         "places": [], "terms": [], "relationships": [], "style": "", "rules": []}
    merged = guide.merge_draft_and_guide(draft, g)
    harry = [c for c in merged["characters"] if c["name_en"] == "Harry"][0]
    assert harry["render"] == "keep"          # lidské rozhodnutí zůstalo
    newguy = [c for c in merged["characters"] if c["name_en"] == "NewGuy"][0]
    assert newguy["render"] == ""             # bez doložení se nepředvyplňuje
    assert newguy["scout_suggestion"] == "translate"
```

- [ ] **Step 6: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/guide.py tests/test_merge_sources.py tests/test_guide.py
git commit -m "feat: merge_sources - tři zdroje, provenience, oddělené návrhy"
```

---

## Task 10: guard v glosáři proti přepsání přes alias

**Files:**
- Modify: `src/glossary.py`
- Modify: `tests/test_glossary.py` (append)

**Interfaces:**
- Consumes: nic nového
- Produces: `glossary.seed_from_guide(db_path, guide) -> list[dict]` - vrací seznam konfliktů `[{incoming, existing_term_id, existing_canonical}]` (dřív vracela `None`)

- [ ] **Step 1: Write the failing test** — připoj do `tests/test_glossary.py`

```python
def test_seed_does_not_overwrite_row_matched_only_by_alias(tmp_path):
    """Latentní chyba stávajícího kódu: _seed_one páruje i přes aliasy a pak
    přepíše canonical_en. `Billy Borden` má alias `Billy`, takže seed položky
    `Billy` by mu přepsal kanonický tvar."""
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Billy Borden", "aliases": ["Billy", "Will"], "render": "keep"}],
        "places": [], "terms": []})
    conflicts = glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Billy", "aliases": [], "render": "keep"}],
        "places": [], "terms": []})
    rows = glossary.all_terms(db)
    assert len(rows) == 1
    assert rows[0]["canonical_en"] == "Billy Borden"     # NEPŘEPSÁNO
    assert conflicts and conflicts[0]["incoming"] == "Billy"


def test_seed_returns_empty_list_when_no_conflict(tmp_path):
    db = _db(tmp_path)
    out = glossary.seed_from_guide(db, {"characters": [], "places": [],
                                        "terms": [{"term_en": "Foo", "cz": "Fů"}]})
    assert out == []


def test_seed_still_updates_row_matched_by_canonical(tmp_path):
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [], "places": [],
                                  "terms": [{"term_en": "Council", "cz": "Rada"}]})
    glossary.seed_from_guide(db, {"characters": [], "places": [],
                                  "terms": [{"term_en": "Council", "cz": "Koncil"}]})
    assert [t for t in glossary.all_terms(db)][0]["cz"] == "Koncil"
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_glossary.py -v`
Expected: FAIL - `assert rows[0]["canonical_en"] == "Billy Borden"` (dnes se přepíše na `Billy`)

- [ ] **Step 3: Implement in `src/glossary.py`**

Uprav `_seed_one` a `seed_from_guide`:

```python
def _seed_one(conn, canonical_en: str, cz: str, type_: str,
              aliases: list, note: str):
    """Vrací dict konfliktu, nebo None. Řádek nalezený JEN přes alias se
    nepřepíše, liší-li se příchozí canonical_en - jinak by seed položky `Billy`
    přepsal kanonický tvar řádku `Billy Borden`, který ji má mezi aliasy."""
    existing, matched_by_canonical = None, False
    needle = canonical_en.strip().lower()
    for r in conn.execute("SELECT term_id,canonical_en,aliases,status FROM glossary").fetchall():
        if (r["canonical_en"] or "").strip().lower() == needle:
            existing, matched_by_canonical = r, True
            break
        if needle in [(a or "").strip().lower()
                      for a in json.loads(r["aliases"] or "[]")]:
            existing = r
            break

    if existing is None:
        tid = _free_term_id(conn, "term_" + slugify(canonical_en))
        conn.execute(
            "INSERT INTO glossary (term_id,canonical_en,aliases,cz,accepted_alt,"
            "note,type,status) VALUES (?,?,?,?,'[]',?,?,'seeded')",
            (tid, canonical_en, json.dumps(aliases, ensure_ascii=False), cz, note, type_))
        return None

    if not matched_by_canonical and \
            (existing["canonical_en"] or "").strip().lower() != needle:
        return {"incoming": canonical_en,
                "existing_term_id": existing["term_id"],
                "existing_canonical": existing["canonical_en"]}

    merged = json.loads(existing["aliases"] or "[]")
    for a in aliases:
        if a not in merged:
            merged.append(a)
    if existing["status"] == "approved":
        conn.execute("UPDATE glossary SET aliases=? WHERE term_id=?",
                     (json.dumps(merged, ensure_ascii=False), existing["term_id"]))
        return None
    conn.execute(
        "UPDATE glossary SET canonical_en=?, aliases=?, cz=?, note=?, type=?, "
        "status='seeded', updated_at=CURRENT_TIMESTAMP WHERE term_id=?",
        (canonical_en, json.dumps(merged, ensure_ascii=False), cz, note, type_,
         existing["term_id"]))
    return None


def seed_from_guide(db_path: str, guide: dict) -> list:
    """Naseeduje glosář z potvrzeného návodu. Vrací seznam konfliktů, které
    CLI vypíše - nic se přitom nepřepíše."""
    conflicts = []
    with state.connect(db_path) as conn:
        for ch in guide.get("characters", []) or []:
            name = ch.get("name_en") or ""
            if not name:
                continue
            cz = name if ch.get("render", "keep") == "keep" else (ch.get("cz") or name)
            c = _seed_one(conn, name, cz, "name", list(ch.get("aliases") or []),
                          ch.get("note") or "")
            if c:
                conflicts.append(c)
        for pl in guide.get("places", []) or []:
            name = pl.get("name_en") or ""
            if not name:
                continue
            c = _seed_one(conn, name, pl.get("cz") or name, "place",
                          list(pl.get("aliases") or []), pl.get("note") or "")
            if c:
                conflicts.append(c)
        for t in guide.get("terms", []) or []:
            name = t.get("term_en") or ""
            if not name:
                continue
            c = _seed_one(conn, name, t.get("cz") or name, "term",
                          list(t.get("aliases") or []), t.get("note") or "")
            if c:
                conflicts.append(c)
    return conflicts
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_glossary.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/glossary.py tests/test_glossary.py
git commit -m "fix: seed_from_guide nepřepíše řádek nalezený jen přes alias"
```

---

## Task 11: review UI server - reference, pořadí POSTu, allowlist

**Files:**
- Modify: `src/review_ui/server.py`
- Modify: `tests/test_review_ui.py` (append)

**Interfaces:**
- Consumes: `guide.merge_sources`, `reference_mine.load_reference`
- Produces:
  - `server.build_app(draft_path, guide_path, on_saved, *, reference_path=None)` - `reference_path` **keyword-only**
  - `server.run_review_server(draft_path, guide_path, *, reference_path=None, host, port)`
  - `server.strip_transient(payload) -> dict` - allowlist ukládaných polí

- [ ] **Step 1: Write the failing test** — připoj do `tests/test_review_ui.py`

```python
def _full_payload(**over):
    base = {"characters": [], "places": [], "terms": [], "relationships": [],
            "style": "", "rules": [], "must_decide": [],
            "relationships_reviewed": True}
    base.update(over)
    return base


def test_reference_path_is_keyword_only(tmp_path):
    """Třetí poziční parametr je on_saved - nová cesta se za něj nesmí vydávat."""
    import inspect
    sig = inspect.signature(server.build_app)
    assert sig.parameters["reference_path"].kind == inspect.Parameter.KEYWORD_ONLY


def test_get_guide_includes_reference_block(tmp_path):
    import json as _json
    dp, gp = _paths(tmp_path)
    _json.dump({"characters": [], "places": [],
                "terms": [{"term_en": "White Council", "suggested_cz": "R", "note": ""}],
                "relationships": [], "style_notes": "", "must_decide": []},
               open(dp, "w", encoding="utf-8"))
    from src import reference_mine
    import config as cfg
    draft = _json.load(open(dp, encoding="utf-8"))
    rp = str(tmp_path / "reference.json")
    reference_mine.write_reference(
        [{"id": "terms/white council", "section": "terms", "surface": "White Council",
          "cz": "White Council", "classification": "confirmed",
          "primary_attested": True, "navrh": None, "hits": 12, "books": [1, 2],
          "per_form": {}, "cooccurrence": [], "matched_forms": ["White Council"],
          "matched_cz": "White Council", "source": "kept"}],
        rp, 1,
        {"draft": reference_mine.draft_fingerprint(draft), "corpus": None,
         "thresholds": reference_mine.thresholds_fingerprint(cfg)}, "/root")
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    assert body["terms"][0]["reference"]["classification"] == "confirmed"


def test_post_strips_transient_metadata(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, lambda: None)
    payload = _full_payload(characters=[
        {"name_en": "Harry", "aliases": ["Dresden"], "render": "keep", "cz": "Harry",
         "note": "hrdina", "provenance": "reference", "scout_suggestion": "keep",
         "lexicographer_suggestion": None,
         "reference": {"fresh": True, "classification": "confirmed"}}])
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    saved = json.load(open(gp, encoding="utf-8"))
    ch = saved["characters"][0]
    assert ch["note"] == "hrdina"          # note se ukládá - _seed_one ho čte
    for gone in ("provenance", "scout_suggestion", "lexicographer_suggestion",
                 "reference"):
        assert gone not in ch
    assert "relationships_reviewed" not in saved


def test_post_rejects_unreviewed_relationships(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, lambda: None)
    payload = _full_payload(
        relationships=[{"a": "Harry", "b": "Murphy", "address": "tyka"}],
        relationships_reviewed=False)
    r = TestClient(app).post("/api/guide", json=payload)
    assert r.status_code == 422
    assert any("vztah" in e.lower() for e in r.json()["errors"])


def test_post_allows_missing_flag_when_no_relationships(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, lambda: None)
    payload = _full_payload()
    del payload["relationships_reviewed"]
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200


def test_unanswered_must_decide_still_blocks_after_reorder(tmp_path):
    """apply_must_decide prázdné odpovědi přeskočí a seznam vymaže, takže
    kontrola musí zůstat PŘED ní."""
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, lambda: None)
    payload = _full_payload(must_decide=[{"kind": "term", "scope_key": "Foo",
                                          "question": "?", "answer": ""}])
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_review_ui.py -v`
Expected: FAIL - `reference_path` neexistuje, `strip_transient` neexistuje

- [ ] **Step 3: Implement in `src/review_ui/server.py`**

```python
# nahoře k importům
from src import reference_mine

_PERSIST = {
    "characters": ("name_en", "aliases", "render", "cz", "note"),
    "places": ("name_en", "aliases", "cz", "note"),
    "terms": ("term_en", "aliases", "cz", "note"),
    "relationships": ("a", "b", "address"),
}


def strip_transient(payload: dict) -> dict:
    """Allowlist ukládaných polí. `guide.json` je kanonický lidský model -
    pomocná pole formuláře (`provenance`, návrhy, blok `reference`, příznak
    o zkontrolovaných vztazích) v něm nemají co dělat a po dalším běhu těžby
    by zastarala."""
    out = {}
    for section, fields in _PERSIST.items():
        out[section] = [{k: item[k] for k in fields if k in item}
                        for item in (payload.get(section) or [])]
    out["style"] = payload.get("style", "")
    out["rules"] = payload.get("rules") or []
    return out


def _check_relationships_reviewed(payload: dict) -> list:
    if not (payload.get("relationships") or []):
        return []
    if payload.get("relationships_reviewed") is True:
        return []
    return ["Sekce vztahů: potvrď zaškrtnutím, že jsi tykání/vykání zkontroloval."]
```

Uprav `build_app`, `post_guide` a `run_review_server`:

```python
def build_app(draft_path: str, guide_path: str, on_saved, *,
              reference_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Book translator - review návodu")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_STATIC, "index.html"))

    @app.get("/api/guide")
    def get_guide():
        import config
        reference = (reference_mine.load_reference(reference_path)
                     if reference_path else None)
        return guide_mod.merge_sources(guide_mod.load_draft(draft_path),
                                       guide_mod.load_guide(guide_path),
                                       reference, cfg=config)

    @app.post("/api/guide")
    def post_guide(payload: dict):
        # Pořadí je závazné: kontrola nezodpovězených MUSÍ být před
        # apply_must_decide, které prázdné odpovědi přeskočí a seznam vymaže.
        errs = _check_must_decide_answered(payload)
        if errs:
            return JSONResponse({"ok": False, "errors": errs}, status_code=422)
        payload = apply_must_decide(payload)
        errs = validate(payload) + _check_relationships_reviewed(payload)
        if errs:
            return JSONResponse({"ok": False, "errors": errs}, status_code=422)
        guide_mod.save_guide(guide_path, strip_transient(payload))
        on_saved()
        return {"ok": True}

    return app


def run_review_server(draft_path: str, guide_path: str, *,
                      reference_path: str | None = None,
                      host: str = "127.0.0.1", port: int = 8765) -> int:
    ...
    app = build_app(draft_path, guide_path, on_saved, reference_path=reference_path)
    ...
```

**Pozor:** `_check_relationships_reviewed` se volá po `apply_must_decide`, protože ta může do `relationships` přidat řádek z odpovědi na vztahovou otázku.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_review_ui.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/review_ui/server.py tests/test_review_ui.py
git commit -m "feat: review server - reference_path, allowlist při uložení, kontrola vztahů"
```

---

## Task 12: review UI formulář - chování polí

**Files:**
- Modify: `src/review_ui/static/index.html`
- Create: `tests/test_review_ui_fields.py`

**Interfaces:**
- Consumes: payload z `GET /api/guide` (`provenance`, `scout_suggestion`, `lexicographer_suggestion`, `reference`)
- Produces: formulář, kde se předvyplňuje jen doložené a každá akce je vratná

Testuje se **serializovaný payload**, ne vzhled - proto se v testu spouští
JS logika přes prohlížeč není potřeba: pomocné funkce se vytáhnou do samostatné
části souboru a testuje se přes `POST` s payloadem, který by formulář vyrobil.

- [ ] **Step 1: Write the failing test** — `tests/test_review_ui_fields.py`

```python
import json
from fastapi.testclient import TestClient
from src.review_ui import server


def _paths(tmp_path, draft):
    dp = str(tmp_path / "guide.draft.json")
    gp = str(tmp_path / "guide.json")
    json.dump(draft, open(dp, "w", encoding="utf-8"))
    return dp, gp


def test_unused_suggestion_never_reaches_saved_guide(tmp_path):
    """Nepoužitý návrh se do payloadu nesmí dostat - formulář ho drží mimo pole."""
    draft = {"characters": [], "places": [],
             "terms": [{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
             "relationships": [], "style_notes": "", "must_decide": []}
    dp, gp = _paths(tmp_path, draft)
    app = server.build_app(dp, gp, lambda: None)
    body = TestClient(app).get("/api/guide").json()
    assert body["terms"][0]["cz"] == ""
    assert body["terms"][0]["scout_suggestion"] == "Nikdykdy"
    # uživatel návrh nepoužil -> odešle prázdné cz
    payload = {"characters": [], "places": [], "terms": body["terms"],
               "relationships": [], "style": "", "rules": [], "must_decide": []}
    TestClient(app).post("/api/guide", json=payload)
    saved = json.load(open(gp, encoding="utf-8"))
    assert saved["terms"][0]["cz"] == ""
    assert "scout_suggestion" not in saved["terms"][0]


def test_used_suggestion_is_saved_as_ordinary_value(tmp_path):
    draft = {"characters": [], "places": [],
             "terms": [{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
             "relationships": [], "style_notes": "", "must_decide": []}
    dp, gp = _paths(tmp_path, draft)
    app = server.build_app(dp, gp, lambda: None)
    body = TestClient(app).get("/api/guide").json()
    body["terms"][0]["cz"] = "Nikdykdy"          # kliknul na "použít návrh"
    payload = {"characters": [], "places": [], "terms": body["terms"],
               "relationships": [], "style": "", "rules": [], "must_decide": []}
    TestClient(app).post("/api/guide", json=payload)
    assert json.load(open(gp, encoding="utf-8"))["terms"][0]["cz"] == "Nikdykdy"


def test_character_without_evidence_needs_explicit_render(tmp_path):
    """render se nepředvyplňuje; prázdná volba nesmí projít validací."""
    draft = {"characters": [{"name_en": "Aria", "aliases": [], "suggested": "keep",
                             "note": ""}],
             "places": [], "terms": [], "relationships": [], "style_notes": "",
             "must_decide": []}
    dp, gp = _paths(tmp_path, draft)
    app = server.build_app(dp, gp, lambda: None)
    body = TestClient(app).get("/api/guide").json()
    assert body["characters"][0]["render"] == ""       # NEPŘEDVYPLNĚNO
    payload = {"characters": body["characters"], "places": [], "terms": [],
               "relationships": [], "style": "", "rules": [], "must_decide": []}
    r = TestClient(app).post("/api/guide", json=payload)
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_review_ui_fields.py -v`
Expected: FAIL - `render` se dnes předvyplňuje na `keep`

- [ ] **Step 3: Implement changes in `src/review_ui/static/index.html`**

Nahraď vykreslování postav, míst a termínů tímto vzorem (zbytek souboru beze změny):

```javascript
// Pole podle původu hodnoty. Zásada: odhad se nepředvyplňuje, důkaz ano,
// a každá akce je vratná - původní hodnota se nikdy neztratí.
function valueField(item, onChange) {
  const wrap = el("div");
  const ref = item.reference || {};
  const backed = ref.fresh && (ref.classification === "confirmed" ||
                               ref.classification === "weak") && item.cz;
  const original = item.cz || "";

  const input = el("input", { type: "text", value: original });
  input.readOnly = backed;                 // doložené je zamčené
  input.oninput = e => onChange(e.target.value);
  wrap.appendChild(input);

  if (backed) {
    const evidence = ref.hits
      ? `${ref.hits}× v dílech ${(ref.books || []).join(", ")}`
      : "doloženo referencemi";
    wrap.appendChild(el("p", { class: "note" }, [evidence]));
    const unlock = el("button", {}, ["změnit předvyplněné"]);
    const revert = el("button", {}, ["vrátit zpět předvyplněné"]);
    revert.hidden = true;
    unlock.onclick = () => { input.readOnly = false; input.focus(); revert.hidden = false; };
    revert.onclick = () => { input.value = original; onChange(original); input.readOnly = true; };
    wrap.appendChild(unlock); wrap.appendChild(revert);
  }

  // Návrhy se nikdy nedávají do editovatelného pole - po přepsání by zmizely
  // a nešlo by porovnat, co navrhl model a co říká referenční překlad.
  [["scout_suggestion", "návrh scouta"],
   ["lexicographer_suggestion", "návrh z referencí (nedoloženo)"]].forEach(([key, label]) => {
    const suggestion = item[key];
    if (!suggestion || backed) return;
    const row = el("p", { class: "note" }, [`${label}: ${suggestion}  `]);
    const use = el("button", {}, ["použít návrh"]);
    use.onclick = () => {
      if (use.textContent === "použít návrh") {
        input.value = suggestion; onChange(suggestion); use.textContent = "zpět";
      } else {
        input.value = ""; onChange(""); use.textContent = "použít návrh";
      }
    };
    row.appendChild(use);
    wrap.appendChild(row);
  });
  return wrap;
}

// "přijmout všechny scoutovy návrhy" - jedno vědomé rozhodnutí místo sta
// třiceti nevědomých. Nepřepíše ručně vyplněná ani doložená pole a zpět vrátí
// jen to, co samo změnilo.
function acceptAllScoutSuggestions() {
  const changed = [];
  ["characters", "places", "terms"].forEach(section => {
    (data[section] || []).forEach((item, i) => {
      const ref = item.reference || {};
      const backed = ref.fresh && (ref.classification === "confirmed" ||
                                   ref.classification === "weak");
      if (backed || (item.cz || "").trim() || !item.scout_suggestion) return;
      changed.push([section, i]);
      data[section][i].cz = item.scout_suggestion;
    });
  });
  return changed;
}
```

A u postav nahraď `select(..., c.render || "keep")` prázdnou volbou:

```javascript
const sel = select([["", "-- vyber --"], ["keep", "ponechat"],
                    ["translate", "přeložit"]], c.render || "");
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_review_ui_fields.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Visual check in the browser**

Spusť dočasný server nad kopií dat a projdi formulář okem: doložená pole zamčená s důkazem, návrhy vedle prázdných polí s tlačítkem, roletka postav s `-- vyber --`.

- [ ] **Step 6: Commit**

```bash
git add src/review_ui/static/index.html tests/test_review_ui_fields.py
git commit -m "feat: formulář - předvyplňuje se jen doložené, každá akce vratná"
```

---

## Task 13: CLI příkaz `reference` + oprava promptu scouta

**Files:**
- Modify: `main.py`
- Modify: `src/agents/scout.py` (prompt)
- Modify: `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: vše předchozí
- Produces:
  - `python main.py reference [--dir CESTA] [--refresh-cache]`
  - `_cmd_review` předává `config.REFERENCE_PATH` a vypisuje konflikty z `seed_from_guide`

- [ ] **Step 1: Write the failing test** — připoj do `tests/test_cli.py`

```python
def test_reference_requires_scan_first(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    # guide.draft.json neexistuje
    assert _run(["reference", "--dir", str(tmp_path / "ref")], tmp_path, monkeypatch) == 1


def test_reference_missing_dir_is_fatal(tmp_path, monkeypatch):
    import json as _json
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    _json.dump({"characters": [], "places": [], "terms": [], "relationships": [],
                "style_notes": "", "must_decide": []},
               open("data/guide.draft.json", "w", encoding="utf-8"))
    assert _run(["reference", "--dir", str(tmp_path / "neexistuje")],
                tmp_path, monkeypatch) == 1
    assert not os.path.exists("data/reference.json")


def test_reference_writes_findings_and_closes_run(tmp_path, monkeypatch):
    import json as _json
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    _json.dump({"characters": [], "places": [],
                "terms": [{"term_en": "Nevernever", "suggested_cz": "N", "note": ""}],
                "relationships": [], "style_notes": "", "must_decide": []},
               open("data/guide.draft.json", "w", encoding="utf-8"))
    import src.reference as R
    import src.reference_mine as M
    monkeypatch.setattr(R, "load_corpus", lambda root: R.Corpus(
        cz={1: "Nevernever tady je uprostřed věty.", 2: "a Nevernever zase.",
            3: "Nevernever potřetí uprostřed."},
        en={1: "Nevernever", 2: "Nevernever", 3: "Nevernever"},
        manifest={}, source_root=root))
    monkeypatch.setattr(R, "load_cache", lambda p, r: None)
    monkeypatch.setattr(R, "save_cache", lambda c, p: None)
    ref_dir = tmp_path / "ref"; ref_dir.mkdir()
    assert _run(["reference", "--dir", str(ref_dir)], tmp_path, monkeypatch) == 0
    data = M.load_reference("data/reference.json")
    assert data["findings"][0]["classification"] in ("confirmed", "weak")
    with state.connect("data/state.sqlite3") as conn:
        r = conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    assert r["status"] == "ok"


def test_reference_failure_leaves_previous_file_untouched(tmp_path, monkeypatch):
    import json as _json
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    _json.dump({"characters": [], "places": [],
                "terms": [{"term_en": "Foo", "suggested_cz": "", "note": ""}],
                "relationships": [], "style_notes": "", "must_decide": []},
               open("data/guide.draft.json", "w", encoding="utf-8"))
    os.makedirs("data", exist_ok=True)
    with open("data/reference.json", "w", encoding="utf-8") as f:
        f.write('{"schema_version": 1, "run_id": 0, "source_root": "/old", '
                '"fingerprint": {}, "findings": []}')
    before = open("data/reference.json", encoding="utf-8").read()
    import src.reference as R
    monkeypatch.setattr(R, "load_corpus", lambda root: (_ for _ in ()).throw(
        ValueError("korpus je rozbitý")))
    monkeypatch.setattr(R, "load_cache", lambda p, r: None)
    ref_dir = tmp_path / "ref"; ref_dir.mkdir()
    assert _run(["reference", "--dir", str(ref_dir)], tmp_path, monkeypatch) == 1
    assert open("data/reference.json", encoding="utf-8").read() == before
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_cli.py -v -k reference`
Expected: FAIL - `invalid choice: 'reference'`

- [ ] **Step 3: Implement in `main.py`**

Přidej import a příkaz:

```python
from src import reference as reference_mod
from src import reference_mine


def _cmd_reference(args) -> int:
    db = config.DB_PATH
    root = args.dir or config.REFERENCE_DIR
    rid = state.create_run(db, "reference")
    status = "fatal"
    try:
        if not root:
            raise FatalRunError("Chybí cesta k referencím - použij `--dir CESTA` "
                                "nebo nastav REFERENCE_DIR v config.py.")
        if not os.path.exists(config.GUIDE_DRAFT_PATH):
            raise FatalRunError(
                f"Chybí {config.GUIDE_DRAFT_PATH} - nejdřív spusť `scan`.")
        draft = guide_mod.load_draft(config.GUIDE_DRAFT_PATH)

        corpus = None if args.refresh_cache else reference_mod.load_cache(
            config.REFERENCE_CACHE_PATH, root)
        if corpus is None:
            print("Načítám referenční korpus (~30 s)...")
            try:
                corpus = reference_mod.load_corpus(root)
            except ValueError as e:
                raise FatalRunError(str(e))
            except OSError as e:
                raise FatalRunError(f"Referenční korpus se nepodařilo načíst: {e}")
            reference_mod.save_cache(corpus, config.REFERENCE_CACHE_PATH)

        items = []
        for section, key in (("characters", "name_en"), ("places", "name_en"),
                             ("terms", "term_en")):
            for it in draft.get(section) or []:
                surface = (it.get(key) or "").strip()
                if not surface:
                    continue
                items.append({"id": f"{section}/{textnorm.normalize_key(surface)}",
                              "section": section, "surface": surface,
                              "aliases": list(it.get("aliases") or []),
                              "note": it.get("note") or ""})

        cf = _client_factory(rid, interactive=False)
        try:
            findings = reference_mine.resolve(corpus, items, cf, config)
        except FatalRunError:
            raise
        except Exception as e:
            # Selhání je atomické: předchozí reference.json zůstane nedotčený.
            raise FatalRunError(
                f"Těžba selhala ({type(e).__name__}: {e}). Předchozí "
                f"{config.REFERENCE_PATH} zůstal beze změny, spusť znovu.")

        fingerprint = {
            "draft": reference_mine.draft_fingerprint(draft),
            "corpus": reference_mine.corpus_fingerprint(corpus.source_root),
            "thresholds": reference_mine.thresholds_fingerprint(config)}
        reference_mine.write_reference(findings, config.REFERENCE_PATH, rid,
                                       fingerprint, corpus.source_root)

        counts = {}
        for f in findings:
            counts[f["classification"]] = counts.get(f["classification"], 0) + 1
        print(f"Vytěženo do {config.REFERENCE_PATH}:")
        for name in ("confirmed", "weak", "evidence_only", "proposed",
                     "not_attested", "unresolved"):
            print(f"   {name:<15} {counts.get(name, 0)}")
        _print_usage(db, rid)
        print("Dál: `python main.py review`")
        status = "ok"
        return 0
    except FatalRunError as e:
        print(e)
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        state.finish_run(db, rid, status)
```

Uprav `_cmd_review`, aby předával reference a vypsal konflikty:

```python
def _cmd_review(args) -> int:
    from src import glossary
    from src.review_ui import server
    rc = server.run_review_server(config.GUIDE_DRAFT_PATH, config.GUIDE_PATH,
                                  reference_path=config.REFERENCE_PATH)
    if rc != 0:
        print("Návod nebyl uložen - glosář zůstává beze změny.")
        return rc
    conflicts = glossary.seed_from_guide(config.DB_PATH,
                                         guide_mod.load_guide(config.GUIDE_PATH))
    for c in conflicts:
        print(f"KONFLIKT: {c['incoming']!r} je alias položky "
              f"{c['existing_canonical']!r} - nic jsem nepřepsal, rozhodni ručně.")
    print("Návod uložen, glosář naseedován. Dál: `python main.py run`")
    return 0
```

Zaregistruj příkaz (a přidej `textnorm` k importům):

```python
    p_ref = sub.add_parser("reference", help="vytěž terminologii z profesionálních překladů")
    p_ref.add_argument("--dir", default=None, help="kořen se složkami EN/ a CZ/")
    p_ref.add_argument("--refresh-cache", action="store_true", dest="refresh_cache",
                       help="postav korpus znovu bez ohledu na cache")
    p_ref.set_defaults(func=_cmd_reference)
```

a doplň `"reference"` do `_MUTATING`.

- [ ] **Step 4: Fix the scout prompt** in `src/agents/scout.py`

```
- Jedna položka = **jeden povrch**. Nikdy nepiš výčty jako
  "White Court / Red Court" ani poznámky v závorce jako "Warden(s)" -
  synonyma patří do "aliases", varianty jako samostatné položky.
- Do "aliases" dávej jen tvary, které entitu **identifikují**. Oslovení
  a role ("sir", "kid", "captain") tam nepatří.
```

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add main.py src/agents/scout.py tests/test_cli.py
git commit -m "feat: CLI příkaz reference + předání referencí do review"
```

---

## Task 14: end-to-end invariant

**Files:**
- Create: `tests/test_reference_e2e.py`

**Interfaces:**
- Consumes: vše
- Produces: nic (jen test)

- [ ] **Step 1: Write the test** — `tests/test_reference_e2e.py`

```python
"""Celá cesta reference.json -> GET -> POST -> guide.json -> glosář.

Prokazuje invariant: odhad se nikdy nesmí tvářit jako důkaz a nedoložená
hodnota se nedostane do glosáře bez výslovného přijetí člověkem.
"""
import json
from fastapi.testclient import TestClient

import config
from src import glossary, reference_mine, state
from src.review_ui import server


def _setup(tmp_path, findings):
    dp = str(tmp_path / "guide.draft.json")
    gp = str(tmp_path / "guide.json")
    rp = str(tmp_path / "reference.json")
    db = str(tmp_path / "s.sqlite3")
    state.init_db(db)
    draft = {"characters": [{"name_en": "Aria", "aliases": [], "suggested": "keep",
                             "note": "vedlejší"}],
             "places": [],
             "terms": [{"term_en": "White Council", "suggested_cz": "Rada scouta",
                        "note": "organizace"},
                       {"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
             "relationships": [], "style_notes": "sarkastický", "must_decide": []}
    json.dump(draft, open(dp, "w", encoding="utf-8"))
    reference_mine.write_reference(
        findings, rp, 1,
        {"draft": reference_mine.draft_fingerprint(draft), "corpus": None,
         "thresholds": reference_mine.thresholds_fingerprint(config)},
        "/root")
    return dp, gp, rp, db


def _f(**over):
    base = {"id": "terms/white council", "section": "terms",
            "surface": "White Council", "cz": None, "classification": "unresolved",
            "primary_attested": False, "navrh": None, "hits": 0, "books": [],
            "per_form": {}, "cooccurrence": [], "matched_forms": [],
            "matched_cz": None, "source": "none"}
    base.update(over)
    return base


def test_proposed_does_not_reach_glossary_without_acceptance(tmp_path):
    dp, gp, rp, db = _setup(tmp_path, [
        _f(classification="proposed", navrh="Bílá rada", matched_cz="Bílá rada")])
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    council = [t for t in body["terms"] if t["term_en"] == "White Council"][0]
    assert council["cz"] == "" and council["lexicographer_suggestion"] == "Bílá rada"

    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": body["terms"], "relationships": [],
               "style": "s", "rules": [], "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    glossary.seed_from_guide(db, json.load(open(gp, encoding="utf-8")))
    row = [t for t in glossary.all_terms(db) if t["canonical_en"] == "White Council"][0]
    # bez přijetí zůstal cz = anglický povrch (fallback seedu), NE návrh modelu
    assert row["cz"] != "Bílá rada"


def test_accepted_suggestion_does_reach_glossary(tmp_path):
    dp, gp, rp, db = _setup(tmp_path, [
        _f(classification="proposed", navrh="Bílá rada", matched_cz="Bílá rada")])
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    for t in body["terms"]:
        if t["term_en"] == "White Council":
            t["cz"] = "Bílá rada"          # člověk kliknul na "použít návrh"
    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": body["terms"], "relationships": [],
               "style": "s", "rules": [], "must_decide": []}
    TestClient(app).post("/api/guide", json=payload)
    glossary.seed_from_guide(db, json.load(open(gp, encoding="utf-8")))
    row = [t for t in glossary.all_terms(db) if t["canonical_en"] == "White Council"][0]
    assert row["cz"] == "Bílá rada"


def test_confirmed_flows_through_with_evidence(tmp_path):
    dp, gp, rp, db = _setup(tmp_path, [
        _f(classification="confirmed", cz="White Council",
           matched_cz="White Council", hits=14, books=[1, 2, 3],
           primary_attested=True, source="kept")])
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    council = [t for t in body["terms"] if t["term_en"] == "White Council"][0]
    assert council["cz"] == "White Council"
    assert council["reference"]["hits"] == 14
    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": body["terms"], "relationships": [],
               "style": "s", "rules": [], "must_decide": []}
    TestClient(app).post("/api/guide", json=payload)
    saved = json.load(open(gp, encoding="utf-8"))
    assert "reference" not in saved["terms"][0]      # metadata se neukládají
    glossary.seed_from_guide(db, saved)
    row = [t for t in glossary.all_terms(db) if t["canonical_en"] == "White Council"][0]
    assert row["cz"] == "White Council"


def test_character_without_render_is_rejected(tmp_path):
    dp, gp, rp, db = _setup(tmp_path, [])
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    payload = {"characters": body["characters"], "places": [],
               "terms": [dict(t, cz="x") for t in body["terms"]],
               "relationships": [], "style": "s", "rules": [], "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422


def test_note_survives_all_the_way_to_glossary(tmp_path):
    dp, gp, rp, db = _setup(tmp_path, [])
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": [dict(t, cz="x") for t in body["terms"]],
               "relationships": [], "style": "s", "rules": [], "must_decide": []}
    TestClient(app).post("/api/guide", json=payload)
    glossary.seed_from_guide(db, json.load(open(gp, encoding="utf-8")))
    row = [t for t in glossary.all_terms(db) if t["canonical_en"] == "White Council"][0]
    assert row["note"] == "organizace"
```

- [ ] **Step 2: Run to verify it fails or passes**

Run: `python -m pytest tests/test_reference_e2e.py -v`
Expected: PASS, pokud jsou tasky 1-13 hotové. Padá-li něco, je to skutečná díra - oprav ji v příslušném modulu, ne v testu.

- [ ] **Step 3: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS (vše).

- [ ] **Step 4: Commit**

```bash
git add tests/test_reference_e2e.py
git commit -m "test: end-to-end invariant těžby referencí"
```

---

## Task 15: README a pilotní postup

**Files:**
- Modify: `README.md`
- Modify: `docs/pilot-checklist.md`

- [ ] **Step 1: Add the `reference` command to README**

Do sekce „Fáze běhu" mezi `scan` a `review`:

```bash
python tools/check_draft.py                   # zkontroluj draft (report-only)
python main.py reference --dir "<cesta k referencím>"   # vytěž terminologii
```

A nová podsekce:

```markdown
## Terminologie z předchozích dílů

Máš-li předchozí díly série v EN i CZ, `reference` z nich vytěží zavedené
překlady. Složka musí mít podsložky `EN/` a `CZ/` a soubory číslované dílem.

Nejdřív `tools/check_draft.py` - vypíše, co je ve scoutově draftu rozbité
(výčty místo jednoho termínu, duplicitní entity, otázky odkazující nikam).
Nic nemění; opravíš to ručně v `data/guide.draft.json`.

Ve formuláři pak: **předvyplněné je jen to, co je doložené** v profesionálním
překladu, a vedle stojí důkaz („112× v 8 dílech"). Odhady modelu čekají vedle
prázdného pole na tlačítko „použít návrh".
```

- [ ] **Step 2: Extend the pilot checklist**

```markdown
## Těžba z referencí

- [ ] `python tools/check_draft.py` - kolik vad? Oprav je v `guide.draft.json`.
- [ ] `python main.py reference --dir <cesta>` - kolik `confirmed` / `weak` /
      `evidence_only` / `proposed` / `not_attested` / `unresolved`?
- [ ] Vysoký počet `not_attested` může znamenat, že přesná shoda je moc přísná
      a skloňování by se tolerovat mělo. **To je hlavní věc, kterou má první běh
      změřit.**
- [ ] Sedí prahy `REFERENCE_MIN_HITS` / `MIN_BOOKS`, nebo je většina nálezů
      těsně pod nimi?
- [ ] Kolik návrhů prošlo výskytem, ale spadlo na souvýskytu?
- [ ] Namátkou zkontroluj pět `confirmed` položek - je důkaz opravdu důkaz?
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/pilot-checklist.md
git commit -m "docs: README a pilotní checklist pro těžbu z referencí"
```

---

## Self-Review (provedeno při psaní plánu)

**1. Spec coverage:**
- ✅ Krok 0 normalizace draftu, všech 6 postpodmínek → Task 2
- ✅ `textnorm.normalize_key` jen k identitě → Task 1
- ✅ korpus, párování dílů, manifest, cache → Task 3
- ✅ stupeň 0: způsobilost jedním výskytem, aliasy, sjednocení rozsahů, začátek věty → Task 4
- ✅ stupeň 1: přesná shoda, `books_with_en` bez délkového omezení → Task 5
- ✅ lexikograf: `id` párování, chybějící `id` → `ValueError` → Task 6
- ✅ precedence klasifikace včetně `evidence_only` → Task 7
- ✅ `reference.json`, otisky, validace schématu → Task 8
- ✅ `merge_sources`, provenience, oba návrhy odděleně, `fresh` → Task 9
- ✅ guard v `seed_from_guide` → Task 10
- ✅ `reference_path` keyword-only, pořadí POSTu, allowlist, `relationships_reviewed` → Task 11
- ✅ chování polí, vratnost, „přijmout všechny" → Task 12
- ✅ CLI, atomické selhání, oprava promptu scouta → Task 13
- ✅ end-to-end invariant, zachování `note` → Task 14

**2. Placeholder scan:** Žádné „TBD"/„podobně jako task N". Jediné místo bez
plného kódu je Task 12 krok 5 (vizuální kontrola okem) - to je záměrně manuální.

**3. Type consistency:**
- `Evidence(hits, books, per_form, matched_forms, confirm_eligible)` - Tasky 4, 5, 7
- `Finding` s `classification` (ne `klasifikace`) - Tasky 7, 8, 9, 14
- `SurfaceItem(id, section, surface, aliases, note)` - Tasky 7, 13
- `seed_from_guide` vrací `list` - Tasky 10, 13
- `build_app(..., *, reference_path=None)` - Tasky 11, 12, 14

**Poznámka k Tasku 9:** mění chování dvou existujících testů v
`tests/test_guide.py`. Je to záměr - právě ty testy zachycovaly předvyplňování
scoutových odhadů, které se ruší. Task je proto upravuje výslovně, ne mlčky.

---

## Execution Handoff

Plán uložen do `docs/superpowers/plans/2026-09-07-reference-mining.md`.
