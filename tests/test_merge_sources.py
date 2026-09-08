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


def _fresh_fp(draft, monkeypatch):
    """`corpus_fingerprint` volá `reference.build_manifest(source_root)` proti
    skutečnému filesystému - v testu žádný "/root" neexistuje, takže by
    `current_corpus` vždy vyšlo `None` a `fresh` by bylo VŽDY False, ať je
    draft/prahy sedí sebelíp. Proto se `corpus_fingerprint` monkeypatchuje na
    pevnou hodnotu shodnou s tou v otisku - test tak cíleně ověřuje draft-
    a threshold-část `_is_fresh`, ne dostupnost souborového systému."""
    monkeypatch.setattr(reference_mine, "corpus_fingerprint", lambda root: "corpus-fp")
    return {"draft": reference_mine.draft_fingerprint(draft),
            "corpus": "corpus-fp",
            "thresholds": reference_mine.thresholds_fingerprint(config)}


def test_confirmed_prefills_cz_and_sets_provenance(monkeypatch):
    d = _draft()
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", hits=12, books=[1, 2])],
                     _fresh_fp(d, monkeypatch))
    m = guide.merge_sources(d, _empty_guide(), ref, cfg=config)
    term = [t for t in m["terms"] if t["term_en"] == "White Council"][0]
    assert term["cz"] == "White Council"
    assert term["provenance"] == "reference"
    assert term["reference"]["hits"] == 12


def test_proposed_leaves_cz_empty_and_keeps_suggestion_separate(monkeypatch):
    d = _draft()
    ref = _reference([_f(classification="proposed", navrh="Bílá rada",
                         matched_cz="Bílá rada")], _fresh_fp(d, monkeypatch))
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


def test_human_value_wins_over_reference(monkeypatch):
    d = _draft()
    g = _empty_guide()
    g["terms"] = [{"term_en": "White Council", "cz": "Moje rada"}]
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", hits=9, books=[1, 2])],
                     _fresh_fp(d, monkeypatch))
    m = guide.merge_sources(d, g, ref, cfg=config)
    term = m["terms"][0]
    assert term["cz"] == "Moje rada" and term["provenance"] == "human"


def test_character_keep_with_blank_cz_is_still_human_decided(monkeypatch):
    """render="keep" s prázdným cz je platný, uložený lidský stav (validate()
    vyžaduje neprázdné cz jen při render="translate"). Čerstvý confirmed
    nález pro tuhle postavu nesmí provenienci přepsat zpět na "reference" -
    "guide > reference" platí bezpodmínečně, i pro prázdnou hodnotu."""
    d = _draft()
    g = _empty_guide()
    g["characters"] = [{"name_en": "Harry", "render": "keep", "cz": ""}]
    ref = _reference([_f(id="characters/harry", section="characters", surface="Harry",
                         classification="confirmed", cz="Harry", matched_cz="Harry",
                         hits=10, books=[1, 2])], _fresh_fp(d, monkeypatch))
    m = guide.merge_sources(d, g, ref, cfg=config)
    harry = m["characters"][0]
    assert harry["provenance"] == "human"
    assert harry["cz"] == ""
    assert harry["render"] == "keep"
    # Prázdné cz se neshoduje s matched_cz "Harry" - číselný důkaz se nesmí
    # ukázat, i když je nález confirmed a čerstvý (dřívější `shown_cz and`
    # bral prázdný řetězec jako "nic se neliší", což je opak pravdy).
    assert "hits" not in harry["reference"]


def test_guide_only_character_keep_with_blank_cz_is_still_human():
    """Stejné pravidlo jako u položky spárované s draftem, ale pro
    GUIDE-ONLY řádek (v guide.json je, v draftu už ne - typicky po rescanu).
    `g.get("cz")` samo o sobě by u prázdného cz dalo provenance="none"."""
    d = _draft()   # neobsahuje "Aria"
    g = _empty_guide()
    g["characters"] = [{"name_en": "Aria", "render": "keep", "cz": ""}]
    m = guide.merge_sources(d, g, None, cfg=config)
    aria = [c for c in m["characters"] if c["name_en"] == "Aria"][0]
    assert aria["provenance"] == "human"
    assert aria["cz"] == "" and aria["render"] == "keep"


def test_human_value_coincidentally_equal_to_matched_cz_stays_human_provenance(monkeypatch):
    """Formulář zamyká pole podle `provenance == "reference"`, ne podle shody
    hodnoty s `matched_cz` - ruční hodnota, která náhodou vyjde stejně jako
    doložený tvar, se nesmí tvářit jako doložená."""
    d = _draft()
    g = _empty_guide()
    g["terms"] = [{"term_en": "White Council", "cz": "White Council"}]  # ruční, shodou okolností stejné
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", hits=9, books=[1, 2])],
                     _fresh_fp(d, monkeypatch))
    m = guide.merge_sources(d, g, ref, cfg=config)
    term = m["terms"][0]
    assert term["cz"] == "White Council" and term["provenance"] == "human"


def test_stale_fingerprint_suppresses_everything_from_reference():
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", navrh="Bílá rada",
                         hits=12, books=[1, 2])],
                     {"draft": "jiny", "corpus": None, "thresholds": "jiny"})
    m = guide.merge_sources(_draft(), _empty_guide(), ref, cfg=config)
    term = m["terms"][0]
    assert term["cz"] == ""
    assert term["reference"] == {"fresh": False}   # NIC než příznak - ani klasifikace, ani návrh
    assert term["lexicographer_suggestion"] is None   # taky potlačeno, ne jen cz


def test_stale_reference_does_not_suppress_human_value():
    g = _empty_guide()
    g["terms"] = [{"term_en": "White Council", "cz": "Moje rada"}]
    ref = _reference([_f(classification="confirmed", cz="White Council")],
                     {"draft": "jiny", "corpus": None, "thresholds": "jiny"})
    m = guide.merge_sources(_draft(), g, ref, cfg=config)
    assert m["terms"][0]["cz"] == "Moje rada"


def test_evidence_binding_hides_numbers_when_value_differs(monkeypatch):
    d = _draft()
    g = _empty_guide()
    g["terms"] = [{"term_en": "White Council", "cz": "Něco jiného"}]
    ref = _reference([_f(classification="confirmed", cz="White Council",
                         matched_cz="White Council", hits=12, books=[1])],
                     _fresh_fp(d, monkeypatch))
    m = guide.merge_sources(d, g, ref, cfg=config)
    assert "hits" not in m["terms"][0]["reference"]


def test_evidence_only_always_shows_its_evidence(monkeypatch):
    """Třída, jejímž jediným obsahem je důkaz, ho musí ukázat i s prázdným cz."""
    d = _draft()
    ref = _reference([_f(classification="evidence_only", hits=79, books=[1, 2, 3],
                         matched_forms=["stole"])], _fresh_fp(d, monkeypatch))
    m = guide.merge_sources(d, _empty_guide(), ref, cfg=config)
    assert m["terms"][0]["reference"]["hits"] == 79


def test_prefill_ignores_cz_on_non_confirmed_finding_even_if_present(monkeypatch):
    """Obrana do hloubky: i kdyby se do merge_sources dostal nález s
    classification="proposed" a vyplněným cz (load_reference by ho odmítl,
    ale merge_sources dostává syrový dict, ne cestu přes něj), předvyplnění
    se řídí classification, ne pouhou přítomností cz."""
    d = _draft()
    ref = _reference([_f(classification="proposed", cz="Nemelo by se použít",
                         navrh="Nemelo by se použít", matched_cz="Nemelo by se použít")],
                     _fresh_fp(d, monkeypatch))
    m = guide.merge_sources(d, _empty_guide(), ref, cfg=config)
    term = m["terms"][0]
    assert term["cz"] == "" and term["provenance"] == "none"


def test_guide_and_draft_keys_merge_across_nfc_nfd_difference():
    """guide.json a guide.draft.json můžou vzniknout jinou cestou (draft ze
    scouta, guide.json ruční editací v prohlížeči) a nést jinak zapsaný, ale
    kanonicky stejný Unicode text. guide.normalize (jen strip+lower) by je
    nespároval - identita musí jít přes textnorm.normalize_key (NFC)."""
    import unicodedata
    d = _draft()
    d["terms"][0]["term_en"] = unicodedata.normalize("NFD", "White Council")
    g = _empty_guide()
    g["terms"] = [{"term_en": unicodedata.normalize("NFC", "White Council"),
                   "cz": "Moje rada"}]
    m = guide.merge_sources(d, g, None, cfg=config)
    assert len(m["terms"]) == 1                     # spárováno, ne dva řádky
    assert m["terms"][0]["cz"] == "Moje rada"


def test_human_can_remove_all_aliases(monkeypatch):
    """Prázdný seznam aliasů z guide.json je platné rozhodnutí ("smaž je"),
    ne "chybí, vezmi draftové". `g.get("aliases") or d.get("aliases")` by
    prázdný seznam vyhodnotil jako falsy a spadl zpět na draft - člověk by
    smazání aliasu nemohl uložit."""
    d = _draft()
    g = _empty_guide()
    g["characters"] = [{"name_en": "Harry", "render": "keep", "aliases": []}]
    m = guide.merge_sources(d, g, None, cfg=config)
    harry = m["characters"][0]
    assert harry["aliases"] == []


def test_human_edited_note_survives_next_merge():
    """Poznámka uložená v guide.json (člověk ji upravil ve formuláři) se při
    dalším GET nesmí přepsat zpět draftovou verzí."""
    d = _draft()   # d["characters"][0]["note"] == "hrdina"
    g = _empty_guide()
    g["characters"] = [{"name_en": "Harry", "render": "keep", "note": "upravená poznámka"}]
    m = guide.merge_sources(d, g, None, cfg=config)
    assert m["characters"][0]["note"] == "upravená poznámka"


def test_merge_draft_and_guide_still_works():
    m = guide.merge_draft_and_guide(_draft(), _empty_guide())
    assert m["terms"][0]["term_en"] == "White Council"
    assert m["style"] == "sarkastický"


def test_missing_reference_block_does_not_break():
    m = guide.merge_sources(_draft(), _empty_guide(), None, cfg=config)
    assert m["characters"][0]["name_en"] == "Harry"
