"""Automatizovaný test čisté JS logiky hromadného přijetí/vrácení návrhů
(Task 12) - bez DOM/prohlížeče, přes Node. Viz POZOR výše u _JS_SOURCE."""
import shutil
import subprocess

import pytest

_JS_SOURCE = """
function fieldProvenance(item, field) {
  const key = "_" + field + "Provenance";
  return item[key] !== undefined ? item[key] : item.provenance;
}

let lastAcceptAllChanges = null;

function pendingAcceptAllChanges() {
  return (lastAcceptAllChanges || []).filter(
    c => data[c.section][c.i][c.field] === c.applied);
}

function acceptAllScoutSuggestions() {
  const changes = [];
  (data.characters || []).forEach((c, i) => {
    if (fieldProvenance(c, "render") === "reference" || c.render || !c.scout_suggestion) return;
    changes.push({ section: "characters", i, field: "render",
                  before: c.render || "", applied: c.scout_suggestion });
    data.characters[i].render = c.scout_suggestion;
    data.characters[i]._renderProvenance = "human";
  });
  ["places", "terms"].forEach(sec => {
    (data[sec] || []).forEach((item, i) => {
      if (fieldProvenance(item, "cz") === "reference" || (item.cz || "").trim()
          || !item.scout_suggestion) return;
      changes.push({ section: sec, i, field: "cz",
                    before: item.cz || "", applied: item.scout_suggestion });
      data[sec][i].cz = item.scout_suggestion;
      data[sec][i]._czProvenance = "human";
    });
  });
  lastAcceptAllChanges = changes;
  return changes.length;
}

function undoAcceptAllScoutSuggestions() {
  pendingAcceptAllChanges().forEach(c => {
    const item = data[c.section][c.i];
    item[c.field] = c.before;
    if (c.field === "cz") item._czActiveKey = null;
    else if (c.field === "render") item._renderActive = false;
  });
  lastAcceptAllChanges = null;
}
"""


def _run(script: str) -> None:
    if shutil.which("node") is None:
        pytest.skip("node není v PATH - test čisté JS logiky se přeskakuje")
    result = subprocess.run(["node", "-e", _JS_SOURCE + "\n" + script],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_bulk_accept_then_untouched_field_reverts_on_undo():
    _run("""
    var data = { characters: [], places: [{ cz: "", scout_suggestion: "Navrh", provenance: "none" }], terms: [] };
    acceptAllScoutSuggestions();
    if (data.places[0].cz !== "Navrh") throw new Error("bulk accept selhal");
    undoAcceptAllScoutSuggestions();
    if (data.places[0].cz !== "") throw new Error("nedotcene pole se nevratilo");
    """)


def test_bulk_undo_does_not_touch_manually_diverged_field():
    _run("""
    var data = { characters: [], places: [{ cz: "", scout_suggestion: "Navrh", provenance: "none" }], terms: [] };
    acceptAllScoutSuggestions();
    data.places[0].cz = "Rucni text";
    undoAcceptAllScoutSuggestions();
    if (data.places[0].cz !== "Rucni text") throw new Error("bulk undo prepsal rucni hodnotu");
    """)


def test_use_then_revert_individual_suggestion_then_bulk_undo_restores_original():
    """round-8 scenar: pouzij jiny navrh -> vrat ho zpet (hodnota se tim
    vrati presne na hromadne prijatou) -> vrat celou davku."""
    _run("""
    var data = { characters: [], places: [{ cz: "", scout_suggestion: "Navrh", provenance: "none" }], terms: [] };
    acceptAllScoutSuggestions();
    data.places[0].cz = "Jiny navrh";
    data.places[0].cz = "Navrh";
    undoAcceptAllScoutSuggestions();
    if (data.places[0].cz !== "") throw new Error("bulk undo nevratil puvodni hodnotu po use-then-revert cyklu");
    """)


def test_bulk_undo_clears_active_suggestion_flag_for_render():
    """round-9 scenar: bulk-accept -> uzivatel klikne na porad viditelne
    individualni "pouzit navrh" NA TOMTEZ poli (nastavi _renderActive, i
    kdyz hodnota vysla stejne) -> bulk-undo -> stav tlacitka se musi
    vycistit, jinak by dalsi klik na "zpet" tise obnovil hodnotu, kterou
    bulk-undo prave zrusilo. Bez explicitniho nastaveni _renderActive PRED
    undem by assert prosel i bez opravy (_renderActive by nikdy nebylo
    true) - proto se tu simuluje presne to, co dela use.onclick."""
    _run("""
    var data = { characters: [{ render: "", scout_suggestion: "keep", provenance: "none" }], places: [], terms: [] };
    acceptAllScoutSuggestions();
    if (data.characters[0].render !== "keep") throw new Error("bulk accept selhal");
    // simulace kliku na jednotlive "pouzit navrh" (viz renderField use.onclick)
    data.characters[0]._renderBefore = data.characters[0].render;
    data.characters[0]._renderActive = true;
    undoAcceptAllScoutSuggestions();
    if (data.characters[0].render !== "") throw new Error("bulk undo nevratil render");
    if (data.characters[0]._renderActive) throw new Error("_renderActive zustal true po bulk undo");
    """)


def test_bulk_undo_clears_active_suggestion_flag_for_cz():
    """Stejny scenar jako u render, ale pro cz (_czActiveKey) - jiny kod,
    jiny test, jinak by oprava jednoho z nich prosla bez pokryti druheho."""
    _run("""
    var data = { characters: [], places: [{ cz: "", scout_suggestion: "Navrh", provenance: "none" }], terms: [] };
    acceptAllScoutSuggestions();
    if (data.places[0].cz !== "Navrh") throw new Error("bulk accept selhal");
    // simulace kliku na jednotlive "pouzit navrh" (viz valueField use.onclick)
    data.places[0]._czBefore = data.places[0].cz;
    data.places[0]._czActiveKey = "scout_suggestion";
    undoAcceptAllScoutSuggestions();
    if (data.places[0].cz !== "") throw new Error("bulk undo nevratilo cz");
    if (data.places[0]._czActiveKey) throw new Error("_czActiveKey zustal nastaveny po bulk undo");
    """)
