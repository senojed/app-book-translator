import json
import os
import pytest
from src import reference, reference_mine
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


def test_manifest_fingerprint_matches_corpus_fingerprint_for_same_manifest(tmp_path):
    """manifest_fingerprint(m) musí dát stejný otisk jako corpus_fingerprint()
    počítané ze stejného manifestu - jinak by `_is_fresh` (guide.py, počítá
    přes corpus_fingerprint) nikdy nepoznal referenci uloženou přes
    manifest_fingerprint (main.py) jako čerstvou."""
    (tmp_path / "EN").mkdir()
    (tmp_path / "EN" / "x.epub").write_bytes(b"x")
    manifest = reference.build_manifest(str(tmp_path))
    assert reference_mine.manifest_fingerprint(manifest) == \
        reference_mine.corpus_fingerprint(str(tmp_path))


def test_manifest_fingerprint_changes_with_manifest_content():
    assert reference_mine.manifest_fingerprint({"EN/a.epub": [1, 2]}) != \
        reference_mine.manifest_fingerprint({"EN/a.epub": [1, 3]})


def test_corpus_fingerprint_returns_none_on_oserror(tmp_path, monkeypatch):
    """os.listdir/os.stat uvnitř build_manifest můžou selhat i po úspěšném
    isdir() (soubor mezitím zmizel, oprávnění, síťový disk) - guide._is_fresh
    (volané z GET /api/guide) na tom nesmí spadnout na nezachycenou výjimku."""
    (tmp_path / "EN").mkdir()
    def boom(root):
        raise OSError("soubor zmizel")
    monkeypatch.setattr(reference, "build_manifest", boom)
    assert reference_mine.corpus_fingerprint(str(tmp_path)) is None


def test_load_rejects_wrong_type_for_hits(tmp_path):
    """`hits` jako string - platný JSON, špatný tvar. Nesmí projít jako
    validní a nesmí spadnout na TypeError/KeyError, jen vrátit None."""
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(hits="mnoho")]}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_non_int_book_number(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(books=["1"])]}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_missing_top_level_metadata(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "findings": []}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_malformed_per_form_row(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(per_form={"X": {"hits": "ne"}})]}),
                 encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_bool_as_hits(tmp_path):
    """isinstance(True, int) je v Pythonu True - bez explicitního vyloučení
    by 'hits': true prošlo jako platný počet výskytů."""
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(hits=True)]}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_per_form_row_missing_case_exact(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(per_form={"X": {"hits": 1, "books": [1]}})]}),
                 encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_fingerprint_with_extra_or_missing_key(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": {"draft": "a", "thresholds": "c"},  # chybí "corpus"
                             "findings": []}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_unknown_source(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(source="odjinud")]}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_cz_set_outside_confirmed_or_weak(tmp_path):
    """`resolve()` nikdy nevyrobí `cz` mimo confirmed/weak (viz classify()) -
    poškozený/ručně upravený soubor s classification="proposed" a vyplněným
    `cz` by jinak `_merge_section` vzal jako doložené."""
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(classification="proposed",
                                                   cz="Vymysleno")]}), encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_load_rejects_navrh_set_outside_proposed_or_not_attested(tmp_path):
    p = tmp_path / "reference.json"
    p.write_text(json.dumps({"schema_version": 1, "run_id": 1, "source_root": "/r",
                             "fingerprint": _fp(),
                             "findings": [_finding(classification="confirmed",
                                                   cz="X", navrh="neplatny")]}),
                 encoding="utf-8")
    assert reference_mine.load_reference(str(p)) is None


def test_write_leaves_no_tmp_file_on_error(tmp_path, monkeypatch):
    """Selže-li zápis (např. disk plný), po sobě neuklizený .tmp soubor by
    matl při dalším pokusu."""
    p = str(tmp_path / "reference.json")
    import json as json_mod
    def boom(*a, **kw):
        raise OSError("disk plný")
    monkeypatch.setattr(json_mod, "dump", boom)
    with pytest.raises(OSError):
        reference_mine.write_reference([_finding()], p, 1, _fp(), "/root")
    assert not any(n.endswith(".tmp") for n in os.listdir(tmp_path))
