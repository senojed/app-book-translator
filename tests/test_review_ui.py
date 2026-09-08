import json
from fastapi.testclient import TestClient
from src.review_ui import server


def _paths(tmp_path):
    dp = str(tmp_path / "guide.draft.json")
    gp = str(tmp_path / "guide.json")
    json.dump({"characters": [{"name_en": "Harry", "suggested": "keep", "note": "h"}],
               "places": [], "terms": [], "relationships": [],
               "style_notes": "s", "must_decide": []},
              open(dp, "w", encoding="utf-8"))
    return dp, gp


def test_get_guide_merges_draft(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    r = TestClient(app).get("/api/guide")
    assert r.status_code == 200
    assert any(c["name_en"] == "Harry" for c in r.json()["characters"])


def test_post_valid_guide_saves_and_calls_on_saved(tmp_path):
    dp, gp = _paths(tmp_path)
    called = {"n": 0}
    app = server.build_app(dp, gp, on_saved=lambda: called.__setitem__("n", 1))
    payload = {"characters": [{"name_en": "Harry", "render": "keep", "cz": "Harry"}],
               "places": [], "relationships": [], "style": "s", "rules": [],
               "must_decide": []}
    r = TestClient(app).post("/api/guide", json=payload)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert called["n"] == 1
    assert json.load(open(gp, encoding="utf-8"))["characters"][0]["render"] == "keep"


def test_post_rejects_translate_without_cz(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    payload = {"characters": [{"name_en": "X", "render": "translate", "cz": ""}],
               "places": [], "relationships": [], "style": "", "rules": [],
               "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422


def test_post_rejects_unanswered_must_decide(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    payload = {"characters": [], "places": [], "terms": [], "relationships": [],
               "style": "", "rules": [], "must_decide": [{"kind": "term",
               "scope_key": "Foo", "question": "?", "answer": ""}]}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422


def test_post_routes_must_decide_answer_into_terms(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    payload = {"characters": [], "places": [], "terms": [], "relationships": [],
               "style": "", "rules": [], "must_decide": [{"kind": "term",
               "scope_key": "The White Council", "question": "?", "answer": "Bílá rada"}]}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    saved = json.load(open(gp, encoding="utf-8"))
    assert any(t["term_en"] == "The White Council" and t["cz"] == "Bílá rada"
               for t in saved["terms"])
    assert saved.get("must_decide", []) == []  # rozhodnutí zapsaná, must_decide pryč


def _post(tmp_path, extra):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    base = {"characters": [], "places": [], "terms": [], "relationships": [],
            "style": "", "rules": [], "must_decide": [],
            "relationships_reviewed": True}
    base.update(extra)
    return TestClient(app).post("/api/guide", json=base), gp


def test_must_decide_name_routes_to_characters(tmp_path):
    r, gp = _post(tmp_path, {"must_decide": [{"kind": "name", "scope_key": "Aria",
        "question": "?", "answer": "Ária"}]})
    assert r.status_code == 200
    saved = json.load(open(gp, encoding="utf-8"))
    c = [x for x in saved["characters"] if x["name_en"] == "Aria"][0]
    assert c["render"] == "translate" and c["cz"] == "Ária"


def test_must_decide_relationship_routes_and_rejects_invalid_answer(tmp_path):
    ok, gp = _post(tmp_path, {"must_decide": [{"kind": "relationship",
        "scope_key": "harry|murphy", "question": "?", "answer": "vyka"}]})
    assert ok.status_code == 200
    assert json.load(open(gp, encoding="utf-8"))["relationships"][0]["address"] == "vyka"
    bad, _ = _post(tmp_path, {"must_decide": [{"kind": "relationship",
        "scope_key": "a|b", "question": "?", "answer": "možná"}]})
    assert bad.status_code == 422   # neplatný address chycen plnou validací PO apply


def test_must_decide_style_routes_to_rules(tmp_path):
    r, gp = _post(tmp_path, {"must_decide": [{"kind": "style", "scope_key": "",
        "question": "?", "answer": "vypravěč je sarkastický"}]})
    assert r.status_code == 200
    assert "vypravěč je sarkastický" in json.load(open(gp, encoding="utf-8"))["rules"]


def test_must_decide_updates_existing_term_not_duplicate(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    payload = {"characters": [], "places": [],
               "terms": [{"term_en": "Council", "cz": "Rada"}],
               "relationships": [], "style": "", "rules": [],
               "must_decide": [{"kind": "term", "scope_key": "Council",
                                "question": "?", "answer": "Koncil"}]}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    terms = json.load(open(gp, encoding="utf-8"))["terms"]
    assert len(terms) == 1 and terms[0]["cz"] == "Koncil"


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


def test_get_guide_includes_reference_block(tmp_path, monkeypatch):
    import json as _json
    dp, gp = _paths(tmp_path)
    _json.dump({"characters": [], "places": [],
                "terms": [{"term_en": "White Council", "suggested_cz": "R", "note": ""}],
                "relationships": [], "style_notes": "", "must_decide": []},
               open(dp, "w", encoding="utf-8"))
    from src import reference_mine
    import config as cfg
    # Stejný důvod jako v Taskách 9 a 14: corpus_fingerprint("/root") na
    # neexistující cestě vždy vrátí None, takže by fresh bylo vždy False.
    monkeypatch.setattr(reference_mine, "corpus_fingerprint", lambda root: "corpus-fp")
    draft = _json.load(open(dp, encoding="utf-8"))
    rp = str(tmp_path / "reference.json")
    reference_mine.write_reference(
        [{"id": "terms/white council", "section": "terms", "surface": "White Council",
          "cz": "White Council", "classification": "confirmed",
          "primary_attested": True, "navrh": None, "hits": 12, "books": [1, 2],
          "per_form": {}, "cooccurrence": [], "matched_forms": ["White Council"],
          "matched_cz": "White Council", "source": "kept"}],
        rp, 1,
        {"draft": reference_mine.draft_fingerprint(draft), "corpus": "corpus-fp",
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
