import pytest
from src.agents import translator
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

_RAW = (
    "===PREKLAD===\nAhoj světe.\n\nDruhý odstavec.\n"
    "===METADATA===\n"
    '{"new_terms":[{"term_en":"Foo","cz":"Fů","note":"","type":"term"}],'
    '"rendered_terms":[{"term_id":"t1","cz_as_used":"Harry"}],'
    '"questions":[{"kind":"term","scope_key":"cand_foo","guess_answer":"Fů",'
    '"text":"jak Foo?","severity":"guess"}]}'
    "\n===KONEC==="
)


def test_translate_scene_parses_delimited():
    r = translator.translate_scene("Hello world.", "guide", "gloss",
                                   FakeLLMClient([Completion(_RAW, False, 10, 10)]))
    assert r.translation == "Ahoj světe.\n\nDruhý odstavec."
    assert r.new_terms[0]["cz"] == "Fů"
    assert r.rendered_terms[0]["term_id"] == "t1"
    assert r.questions[0]["severity"] == "guess"


def test_translate_scene_raises_on_truncated():
    with pytest.raises(OutputTruncated):
        translator.translate_scene("Hi.", "g", "gl",
                                   FakeLLMClient([Completion(_RAW, True, 10, 10)]))


def test_broken_metadata_json_raises():
    raw = "===PREKLAD===\nText tady.\n===METADATA===\n{tohle neni json\n===KONEC==="
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_empty_translation_raises():
    raw = "===PREKLAD===\n\n===METADATA===\n{}\n===KONEC==="
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_missing_end_marker_raises_as_possibly_truncated():
    """Kolo 3 BLOCKING (plan-consensus) - CodexLLMClient.complete()'s
    `truncated` je VŽDY False (Codex nemá spolehlivý stop_reason signál
    jako Claude), takže tohle je JEDINÁ pojistka proti tichému přijetí
    useknutého výstupu jako hotového překladu."""
    raw = "===PREKLAD===\nText tady bez konce."
    with pytest.raises(ValueError, match="KONEC"):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_duplicate_end_marker_raises():
    """Kolo 4 BLOCKING (plan-consensus) - pouhé `MARK_END in raw` by
    tohle propustilo (marker JE přítomný), ale duplicita signalizuje
    poškozený/opakovaný výstup, ne validní strukturu."""
    raw = ("===PREKLAD===\nText.\n===METADATA===\n{}\n===KONEC===\n"
           "===KONEC===")
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_content_after_end_marker_raises():
    """Kolo 4 BLOCKING (plan-consensus) - text PO markeru (druhý pokus
    modelu, garbage) by pouhé `in` kontrole prošel - marker musí být
    opravdu POSLEDNÍ obsah."""
    raw = "===PREKLAD===\nText.\n===METADATA===\n{}\n===KONEC===\nnavíc ještě tohle"
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_missing_metadata_marker_does_not_leak_end_marker_into_translation():
    """Kolo 4 BLOCKING (plan-consensus) - nejzávažnější díra kola 3:
    chybí-li ===METADATA=== úplně, ale ===KONEC=== přítomný je,
    split_sections by bez týhle opravy vzalo `===KONEC===` jako
    SOUČÁST přeloženého textu (zapečený marker v próze), místo aby
    to zahodilo jako poškozený výstup."""
    raw = "===PREKLAD===\nText bez metadat.\n===KONEC==="
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_duplicate_translation_marker_raises():
    """Kolo 6 IMPORTANT (plan-consensus) - slíbená ÚPLNÁ strukturální
    validace musí krýt i duplicitu markerů JINÝCH než KONEC."""
    raw = ("===PREKLAD===\nText.\n===PREKLAD===\nJeště text.\n"
           "===METADATA===\n{}\n===KONEC===")
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_duplicate_metadata_marker_raises():
    """Kolo 6 IMPORTANT (plan-consensus) - viz výš."""
    raw = ("===PREKLAD===\nText.\n===METADATA===\n{}\n"
           "===METADATA===\n{}\n===KONEC===")
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_markers_out_of_order_raises():
    """Kolo 6 IMPORTANT (plan-consensus) - markery přítomné přesně
    jednou, ale ve ŠPATNÉM pořadí (METADATA před PREKLAD) - `count()==1`
    kontrola sama tohle nezachytí, `index()` porovnání ano."""
    raw = "===METADATA===\n{}\n===PREKLAD===\nText.\n===KONEC==="
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_missing_end_marker_raises_invalid_translation_output_type():
    """Kolo 6 IMPORTANT (plan-consensus) - main.py's `_cmd_run` (Task 5)
    rozlišuje `InvalidTranslationOutput` od ostatních výjimek podle
    TYPU (`except translator.InvalidTranslationOutput`), ne jen podle
    `ValueError`, takže musí být přesně tenhle typ, ne jeho rodič."""
    raw = "===PREKLAD===\nText bez konce."
    with pytest.raises(translator.InvalidTranslationOutput):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_system_prompts_instruct_end_marker():
    """Kolo 5 NIT (plan-consensus) - parser-testy samy nezachytí
    regresi, kdy `_parse()` kontrolu na `MARK_END` ponechá, ale
    instrukce modelu (co marker vlastně vyžádá) se omylem z promptu
    vytratí - model by pak marker nikdy nevrátil a VŠECHNY odpovědi
    by selhávaly."""
    assert translator.MARK_END in translator.SYSTEM_PROMPT_FRESH
    assert translator.MARK_END in translator.SYSTEM_PROMPT_REVISE


def test_marker_like_text_inside_translation_does_not_confuse_parser():
    """Kolo 9 IMPORTANT (plan-consensus) - `===KONEC===` (nebo jiný
    marker) může být SOUČÁSTÍ legitimního přeloženého textu (citace,
    popis nápisu v knize) - pokud NENÍ na vlastním řádku, nesmí se
    počítat jako SKUTEČNÝ marker. Substring kontrola (`in`/`count`) by
    tohle chybně odmítla jako "poškozený výstup"."""
    raw = ('===PREKLAD===\nNa obálce stálo podivné heslo: "===KONEC==="'
           ' a nikdo nevěděl proč.\n'
           '===METADATA===\n{}\n===KONEC===')
    r = translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))
    assert 'heslo: "===KONEC==="' in r.translation


def test_marker_like_text_inside_metadata_json_does_not_confuse_parser():
    """Kolo 9 IMPORTANT (plan-consensus) - stejné riziko uvnitř JSON
    hodnoty (např. `note` pole citující zdrojový text)."""
    raw = ('===PREKLAD===\nText.\n'
           '===METADATA===\n{"new_terms": [{"term_en": "X", "cz": "Y", '
           '"note": "puvodni text mel ===KONEC=== jako oddelovac", '
           '"type": "term"}]}\n===KONEC===')
    r = translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))
    assert r.new_terms[0]["note"] == "puvodni text mel ===KONEC=== jako oddelovac"


def test_crlf_line_endings_do_not_confuse_parser():
    """Kolo 11 IMPORTANT (plan-consensus) - `^marker$` (re.MULTILINE) by
    na CRLF řádku ("marker\\r\\n") neprošlo bez normalizace - `\\r`
    zůstane mezi markerem a `$` pozicí. Windows-primární projekt."""
    raw = ("===PREKLAD===\r\nText s CRLF.\r\n"
           "===METADATA===\r\n{}\r\n===KONEC===\r\n")
    r = translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))
    assert r.translation == "Text s CRLF."


def test_metadata_not_a_dict_raises():
    """Kolo 12 IMPORTANT (plan-consensus) - `extract_json()` validuje
    jen syntaxi JSON - `[]` je validní JSON, ale `meta.get(...)` na
    seznamu spadne na `AttributeError`, ne `InvalidTranslationOutput`."""
    raw = "===PREKLAD===\nText.\n===METADATA===\n[]\n===KONEC==="
    with pytest.raises(translator.InvalidTranslationOutput):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_metadata_field_wrong_type_raises():
    """Kolo 12 IMPORTANT (plan-consensus) - `{"new_terms": "x"}` je
    validní JSON, ale `list("x")` by tiše rozsekal řetězec na znaky
    (`['x']`), ne vyhodilo chybu."""
    raw = ('===PREKLAD===\nText.\n===METADATA===\n'
           '{"new_terms": "x"}\n===KONEC===')
    with pytest.raises(translator.InvalidTranslationOutput):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_metadata_field_items_not_dicts_raises():
    """Kolo 12 IMPORTANT (plan-consensus) - seznam JE seznam, ale
    položky NEJSOU objekty - downstream kód (`nt.get("term_en")`) by
    spadl na `AttributeError` na řetězcové položce."""
    raw = ('===PREKLAD===\nText.\n===METADATA===\n'
           '{"new_terms": ["not-a-dict"]}\n===KONEC===')
    with pytest.raises(translator.InvalidTranslationOutput):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_metadata_field_new_term_item_wrong_type_raises():
    """Kolo 14 IMPORTANT (plan-consensus) - "seznam objektů" samo
    nestačí - `term_en` uvnitř JE v dictu, ale je to int, ne string.
    `pipeline.py`'s `(nt.get("term_en") or "").strip()` by na INTU
    spadl na `AttributeError` (1 je truthy, `or ""` fallback se
    nepoužije)."""
    raw = ('===PREKLAD===\nText.\n===METADATA===\n'
           '{"new_terms": [{"term_en": 1, "cz": "X", "note": "", "type": "term"}]}'
           '\n===KONEC===')
    with pytest.raises(translator.InvalidTranslationOutput):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_revise_chapter_sends_findings_and_en(monkeypatch):
    seen = {}
    def gen(**kw):
        seen.update(kw)
        return Completion(_RAW, False, 10, 10)
    translator.revise_chapter("EN ORIGINAL", "stary CZ",
                              [{"issue": "vynechavka", "suggestion": "doplň"}],
                              "guide", "gloss", FakeLLMClient(gen))
    assert "EN ORIGINAL" in seen["user"]
    assert "vynechavka" in seen["user"]
