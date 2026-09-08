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


def test_confirmed_threshold_uses_only_primary_form_not_alias_union(monkeypatch):
    """Primární tvar `Harry Dresden` je jen v 1 dílu (1 výskyt) - pod prahem.
    Alias `Dresden` je hodně doložený ve 2 dílech. Sjednocené `ev0.hits`/
    `ev0.books` (primární + alias) by práh SPLNILY (6 výskytů, 2 díly) a bez
    opravy by položka vyšla `confirmed`, ačkoli primární tvar samotný
    doložen není."""
    monkeypatch.setattr(config, "REFERENCE_MIN_HITS", 3)
    monkeypatch.setattr(config, "REFERENCE_MIN_BOOKS", 2)
    cz = {1: "Potkal jsem Harry Dresden uprostřed. Dresden. Dresden.",
          2: "Dresden dorazil. Dresden zase. Dresden pořád."}
    items = [{"id": "characters/harry dresden", "section": "characters",
              "surface": "Harry Dresden", "aliases": ["Dresden"], "note": ""}]
    f = reference_mine.resolve(_corpus(cz=cz), items, _client_factory({}), config)[0]
    assert f["classification"] == "weak"       # primární tvar má jen 1 výskyt v 1 dílu
    assert f["hits"] == 6 and f["books"] == [1, 2]   # zobrazený důkaz zůstává sjednocený


def test_nfd_surface_finds_its_own_nfc_normalized_evidence(monkeypatch):
    """`count_en_surface` ukládá klíče `per_form` po NFC (viz Task 4). Přijde-li
    `item["surface"]` v NFD (jinak zapsaný, kanonicky stejný text), `classify`
    i `_finding` ho musí normalizovat stejně - jinak lookup do `per_form`
    mine a položka vyjde `weak`/`unresolved` i s reálným důkazem."""
    import unicodedata
    monkeypatch.setattr(config, "REFERENCE_MIN_HITS", 3)
    monkeypatch.setattr(config, "REFERENCE_MIN_BOOKS", 2)
    nfd_surface = unicodedata.normalize("NFD", "Áine")
    cz = {i: "Potkal jsem Áine uprostřed věty." for i in (1, 2, 3)}  # NFC text
    items = [{"id": "characters/aine", "section": "characters",
              "surface": nfd_surface, "aliases": [], "note": ""}]
    f = reference_mine.resolve(_corpus(cz=cz), items, _client_factory({}), config)[0]
    assert f["classification"] == "confirmed"
    assert f["primary_attested"] is True


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
