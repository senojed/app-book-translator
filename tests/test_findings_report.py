import json
from src import findings_report, polish_store, state


def _db_with_notes(tmp_path, notes):
    db = str(tmp_path / "s.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute(
            "INSERT INTO chapters (idx,title,raw_text,translated_text,status,"
            "revision_rounds,notes) VALUES (1,'K1','EN','CZ','done',0,?)",
            (json.dumps(notes, ensure_ascii=False),))
    return db


def test_build_findings_report_includes_notes_findings(tmp_path):
    db = _db_with_notes(tmp_path, [
        {"id": "f1", "resolved": False, "source": "concordance",
         "type": "omission", "issue": "chybí termín"}])
    report = findings_report.build_findings_report(db)
    assert report == [{"idx": 1, "title": "K1",
                       "findings": [{"id": "f1", "resolved": False,
                                    "source": "concordance", "type": "omission",
                                    "issue": "chybí termín"}]}]


def test_build_findings_report_excludes_markers(tmp_path):
    db = _db_with_notes(tmp_path, [
        {"id": "m1", "resolved": False, "source": "stylist", "type": "polish",
         "issue": "stylizováno..."}])
    report = findings_report.build_findings_report(db)
    assert report == []   # jediný nález byl marker, kapitola se vynechá


def test_build_findings_report_does_not_duplicate_via_history(tmp_path):
    """`_commit_polish_result` (Task 5) zapisuje STEJNÝ seznam nálezů do
    `notes` i do historie zároveň - report NESMÍ sáhnout do historie
    taky, jinak by se každý nález zobrazil dvakrát (stejné `id`)."""
    db = _db_with_notes(tmp_path, [
        {"id": "f1", "resolved": False, "source": "critic",
         "type": "fidelity", "issue": "posun smyslu"}])
    history_path = str(tmp_path / "polish.history.json")
    polish_store.save_history(history_path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "a", "cz_after": "b", "styled_by_codex": "b",
            "title": "K1", "findings": [{"id": "f1", "resolved": False,
                                        "source": "critic", "type": "fidelity",
                                        "issue": "posun smyslu"}],
            "rendered_terms": [], "source": "polish-batch", "draft_id": "d1"}]})
    report = findings_report.build_findings_report(db)
    assert len(report[0]["findings"]) == 1


def test_render_findings_html_contains_chapter_and_issue():
    report = [{"idx": 1, "title": "K1",
              "findings": [{"id": "f1", "resolved": False, "severity": "minor",
                           "issue": "chybí termín"}]}]
    html = findings_report.render_findings_html(report)
    assert "K1" in html and "chybí termín" in html


def test_render_findings_txt_contains_chapter_and_issue():
    report = [{"idx": 1, "title": "K1",
              "findings": [{"id": "f1", "resolved": True, "severity": "minor",
                           "issue": "vyřešeno"}]}]
    txt = findings_report.render_findings_txt(report)
    assert "K1" in txt and "vyřešeno" in txt
