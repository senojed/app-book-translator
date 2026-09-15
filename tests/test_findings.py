from src import findings


def test_assign_ids_adds_id_and_resolved_false():
    fs = [{"source": "concordance", "type": "omission", "issue": "x"}]
    out = findings.assign_ids(fs)
    assert out is fs   # mutuje v místě, stejný objekt
    assert isinstance(fs[0]["id"], str) and fs[0]["id"]
    assert fs[0]["resolved"] is False


def test_assign_ids_is_idempotent():
    fs = [{"source": "concordance", "type": "omission", "id": "keep-me",
           "resolved": True}]
    findings.assign_ids(fs)
    assert fs[0]["id"] == "keep-me"
    assert fs[0]["resolved"] is True


def test_assign_ids_coerces_non_str_issue_to_str():
    """Kolo 5 IMPORTANT - `critic._to_finding` čte `issue` přímo z LLM
    JSON bez typové kontroly; bez tyhle normalizace by uživatel po GET+
    save cyklu NEMOHL uložit vůbec nic na kapitole s takovým nálezem
    (`_valid_finding_shape` by 400 odmítlo `issue: 123`)."""
    fs = [{"source": "critic", "type": "fidelity", "issue": 123, "severity": None}]
    findings.assign_ids(fs)
    assert fs[0]["issue"] == "123" and isinstance(fs[0]["issue"], str)
    assert fs[0]["severity"] is None   # None zůstává None, nekonvertuje se na "None"


def test_assign_ids_replaces_explicit_null_id():
    """Kolo 3 IMPORTANT - klient (Task 9 save) může poslat `id: null`
    (validace to propouští) - `setdefault` by to nechalo být, protože
    klíč UŽ existuje. Musí se to poznat stejně jako chybějící klíč."""
    fs = [{"source": "concordance", "type": "omission", "id": None,
           "resolved": None}]
    findings.assign_ids(fs)
    assert isinstance(fs[0]["id"], str) and fs[0]["id"]
    assert fs[0]["resolved"] is False


def test_assign_ids_gives_unique_ids_to_each_finding():
    fs = [{"issue": "a"}, {"issue": "b"}]
    findings.assign_ids(fs)
    assert fs[0]["id"] != fs[1]["id"]


def test_assign_ids_replaces_non_string_id():
    """Kolo 23 IMPORTANT - `id: 123` (číslo, TRUTHY, ale ne `str`) by
    starým `if not f.get("id")` prošlo beze změny - GET by ho vrátilo
    klientovi, ale resolve/save by ho NAVŽDY odmítly (vyžadují `str`).
    Zdroj takových dat: pre-Task-2 `chapters.notes`, migrace (Task 13
    Step 8) je jen filtruje na ne-dict, ne na shape `id` uvnitř dict."""
    fs = [{"id": 123, "issue": "a"}]
    findings.assign_ids(fs)
    assert isinstance(fs[0]["id"], str)
    assert fs[0]["id"] != 123


def test_assign_ids_replaces_duplicate_ids_within_same_batch():
    """Kolo 23 IMPORTANT - dvě položky se STEJNÝM `id` v JEDNÉ dávce
    (možné z pre-Task-2 dat) - `set_resolved`/`_merge_findings_by_id`
    předpokládají unikátnost. Druhý výskyt dostane NOVÉ `id`, první
    zůstává beze změny (první-vyhrává, ne oba přepsané)."""
    fs = [{"id": "dup", "issue": "a"}, {"id": "dup", "issue": "b"}]
    findings.assign_ids(fs)
    assert fs[0]["id"] == "dup"
    assert fs[1]["id"] != "dup"
    assert fs[0]["id"] != fs[1]["id"]


def test_set_resolved_updates_matching_finding():
    fs = [{"id": "f1", "resolved": False}, {"id": "f2", "resolved": False}]
    ok = findings.set_resolved(fs, "f2", True)
    assert ok is True
    assert fs[0]["resolved"] is False
    assert fs[1]["resolved"] is True


def test_set_resolved_returns_false_for_unknown_id():
    fs = [{"id": "f1", "resolved": False}]
    assert findings.set_resolved(fs, "nope", True) is False
    assert fs[0]["resolved"] is False


def test_is_marker_true_for_stylist_audit_types():
    assert findings.is_marker({"source": "stylist", "type": "polish"}) is True
    assert findings.is_marker({"source": "stylist", "type": "kept_original"}) is True
    assert findings.is_marker({"source": "stylist", "type": "revert"}) is True
    assert findings.is_marker({"source": "stylist", "type": "unchanged"}) is True   # kolo 9 IMPORTANT


def test_is_marker_false_for_real_findings():
    assert findings.is_marker({"source": "concordance", "type": "omission"}) is False
    assert findings.is_marker({"source": "critic", "type": "fidelity"}) is False
    assert findings.is_marker({"source": "stylist_check", "type": "register_drift"}) is False


def test_is_marker_false_not_crash_for_unhashable_source():
    """Kolo 4 IMPORTANT - producent nálezu (kritik/concordance) NENÍ
    validován jako klientský save vstup; `source: []` by bez isinstance
    kontroly spadlo na TypeError v `(source, type) in _MARKER_TYPES`."""
    assert findings.is_marker({"source": [], "type": "x"}) is False


def test_count_unresolved_excludes_markers_and_resolved():
    fs = [
        {"source": "stylist", "type": "polish", "resolved": False},   # marker - never counts
        {"source": "critic", "type": "fidelity", "resolved": False},  # counts
        {"source": "critic", "type": "fidelity", "resolved": True},   # resolved - excluded
    ]
    assert findings.count_unresolved(fs) == 1
