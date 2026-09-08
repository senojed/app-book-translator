"""Celá cesta reference.json -> GET -> POST -> guide.json -> glosář.

Prokazuje invariant: odhad se nikdy nesmí tvářit jako důkaz a nedoložená
hodnota se nedostane do glosáře bez výslovného přijetí člověkem.
"""
import json
import os
from fastapi.testclient import TestClient

import config
from src import glossary, reference_mine, state
from src.review_ui import server


def _setup(tmp_path, findings, monkeypatch):
    """`monkeypatch` je povinný, i pro prázdné `findings`: `corpus_fingerprint`
    by proti neexistujícímu "/root" vždy vrátilo `None`, takže by `fresh` bylo
    vždy False a testy s neprázdnými nálezy by nedokázaly ověřit cestu skrz
    doloženou/aktuální referenci vůbec."""
    monkeypatch.setattr(reference_mine, "corpus_fingerprint", lambda root: "corpus-fp")
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
        {"draft": reference_mine.draft_fingerprint(draft), "corpus": "corpus-fp",
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


def test_proposed_does_not_reach_glossary_without_acceptance(tmp_path, monkeypatch):
    """Nedoloženo se nedostane do glosáře bez výslovného rozhodnutí - a to
    v nejsilnější podobě: prázdné `cz` blokuje uložení úplně (validate() se
    Tasky 9-13 nemění), takže bez rozhodnutí se neuloží vůbec nic. Rozhodne-li
    se člověk sám, jinak než navrhl model, projde JEHO hodnota."""
    dp, gp, rp, db = _setup(tmp_path, [
        _f(classification="proposed", navrh="Bílá rada", matched_cz="Bílá rada")],
        monkeypatch)
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    council = [t for t in body["terms"] if t["term_en"] == "White Council"][0]
    assert council["cz"] == "" and council["lexicographer_suggestion"] == "Bílá rada"

    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": body["terms"], "relationships": [],
               "style": "s", "rules": [], "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422
    assert not os.path.exists(gp)

    # Nevernever nemá žádný nález (fixture ho neobsahuje) a validate() u
    # KAŽDÉHO termínu vyžaduje neprázdné cz - musí se rozhodnout i o něm,
    # jinak POST zůstane 422 a nic z White Council se neověří.
    for t in payload["terms"]:
        if t["term_en"] == "White Council":
            t["cz"] = "Moje vlastní volba"
        elif t["term_en"] == "Nevernever":
            t["cz"] = "Nikdykdy"
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    glossary.seed_from_guide(db, json.load(open(gp, encoding="utf-8")))
    row = [t for t in glossary.all_terms(db) if t["canonical_en"] == "White Council"][0]
    assert row["cz"] == "Moje vlastní volba"          # NE návrh modelu


def test_accepted_suggestion_does_reach_glossary(tmp_path, monkeypatch):
    dp, gp, rp, db = _setup(tmp_path, [
        _f(classification="proposed", navrh="Bílá rada", matched_cz="Bílá rada")],
        monkeypatch)
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    for t in body["terms"]:
        if t["term_en"] == "White Council":
            t["cz"] = "Bílá rada"          # člověk kliknul na "použít návrh"
        elif t["term_en"] == "Nevernever":
            t["cz"] = "Nikdykdy"           # validate() vyžaduje cz u KAŽDÉHO termínu
    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": body["terms"], "relationships": [],
               "style": "s", "rules": [], "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    glossary.seed_from_guide(db, json.load(open(gp, encoding="utf-8")))
    row = [t for t in glossary.all_terms(db) if t["canonical_en"] == "White Council"][0]
    assert row["cz"] == "Bílá rada"


def test_confirmed_flows_through_with_evidence(tmp_path, monkeypatch):
    dp, gp, rp, db = _setup(tmp_path, [
        _f(classification="confirmed", cz="White Council",
           matched_cz="White Council", hits=14, books=[1, 2, 3],
           primary_attested=True, source="kept")], monkeypatch)
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    council = [t for t in body["terms"] if t["term_en"] == "White Council"][0]
    assert council["cz"] == "White Council"
    assert council["reference"]["hits"] == 14
    for t in body["terms"]:
        if t["term_en"] == "Nevernever":
            t["cz"] = "Nikdykdy"          # validate() vyžaduje cz u KAŽDÉHO termínu
    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": body["terms"], "relationships": [],
               "style": "s", "rules": [], "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    saved = json.load(open(gp, encoding="utf-8"))
    assert "reference" not in saved["terms"][0]      # metadata se neukládají
    glossary.seed_from_guide(db, saved)
    row = [t for t in glossary.all_terms(db) if t["canonical_en"] == "White Council"][0]
    assert row["cz"] == "White Council"


def test_character_without_render_is_rejected(tmp_path, monkeypatch):
    dp, gp, rp, db = _setup(tmp_path, [], monkeypatch)
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    payload = {"characters": body["characters"], "places": [],
               "terms": [dict(t, cz="x") for t in body["terms"]],
               "relationships": [], "style": "s", "rules": [], "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422


def test_evidence_only_does_not_prefill_and_needs_human_decision(tmp_path, monkeypatch):
    """`evidence_only` (např. `stole` - nalezeno, ale nikdy nedokládá ponechání)
    smí ukázat důkaz, ale `cz` musí zůstat prázdné a bez rozhodnutí se neuloží."""
    dp, gp, rp, db = _setup(tmp_path, [
        _f(classification="evidence_only", hits=79, books=[1, 2, 3],
           matched_forms=["White Council"], source="kept")], monkeypatch)
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    council = [t for t in body["terms"] if t["term_en"] == "White Council"][0]
    assert council["cz"] == "" and council["reference"]["hits"] == 79
    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": body["terms"], "relationships": [],
               "style": "s", "rules": [], "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422
    assert not os.path.exists(gp)


def test_not_attested_does_not_prefill_and_needs_human_decision(tmp_path, monkeypatch):
    """`not_attested` (model navrhl, ale doložení selhalo) taky nesmí
    předvyplnit ani se dostat do glosáře bez rozhodnutí."""
    dp, gp, rp, db = _setup(tmp_path, [
        _f(classification="not_attested", navrh="Vymyšlená rada")], monkeypatch)
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    council = [t for t in body["terms"] if t["term_en"] == "White Council"][0]
    assert council["cz"] == "" and council["lexicographer_suggestion"] == "Vymyšlená rada"
    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": body["terms"], "relationships": [],
               "style": "s", "rules": [], "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422
    assert not os.path.exists(gp)


def test_note_survives_all_the_way_to_glossary(tmp_path, monkeypatch):
    dp, gp, rp, db = _setup(tmp_path, [], monkeypatch)
    app = server.build_app(dp, gp, lambda: None, reference_path=rp)
    body = TestClient(app).get("/api/guide").json()
    payload = {"characters": [dict(body["characters"][0], render="keep")],
               "places": [], "terms": [dict(t, cz="x") for t in body["terms"]],
               "relationships": [], "style": "s", "rules": [], "must_decide": []}
    TestClient(app).post("/api/guide", json=payload)
    glossary.seed_from_guide(db, json.load(open(gp, encoding="utf-8")))
    row = [t for t in glossary.all_terms(db) if t["canonical_en"] == "White Council"][0]
    assert row["note"] == "organizace"
