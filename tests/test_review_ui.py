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
            "style": "", "rules": [], "must_decide": []}
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
