import json
import os
from fastapi.testclient import TestClient
from src.review_ui import server


def _paths(tmp_path, draft):
    dp = str(tmp_path / "guide.draft.json")
    gp = str(tmp_path / "guide.json")
    json.dump(draft, open(dp, "w", encoding="utf-8"))
    return dp, gp


def test_unused_suggestion_is_not_silently_saved(tmp_path):
    """Nepoužitý návrh se do uloženého guide.json nedostane ani jako tichá
    hodnota, ani jako metadata. Prázdné `cz` u termínu neprojde validací
    (nezměněno oproti dnešnímu chování) - "nedoloženo se do glosáře nedostane
    samo" tu platí v nejsilnější podobě: bez rozhodnutí se neuloží vůbec nic."""
    draft = {"characters": [], "places": [],
             "terms": [{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
             "relationships": [], "style_notes": "", "must_decide": []}
    dp, gp = _paths(tmp_path, draft)
    app = server.build_app(dp, gp, lambda: None)
    body = TestClient(app).get("/api/guide").json()
    assert body["terms"][0]["cz"] == ""
    assert body["terms"][0]["scout_suggestion"] == "Nikdykdy"

    payload = {"characters": [], "places": [], "terms": body["terms"],
               "relationships": [], "style": "", "rules": [], "must_decide": []}
    r = TestClient(app).post("/api/guide", json=payload)
    assert r.status_code == 422
    assert not os.path.exists(gp)

    # Rozhodne se sám, jinak než navrhoval scout - uloží se JEHO hodnota,
    # návrh zůstane mimo guide.json úplně.
    payload["terms"][0]["cz"] = "Vlastní volba"
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    saved = json.load(open(gp, encoding="utf-8"))
    assert saved["terms"][0]["cz"] == "Vlastní volba"
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
