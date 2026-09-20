import json
import config
from src import state, glossary, pipeline
from src.llm.client import Completion
from src.agents import translator as T, critic as C


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p)
    state.seed_chapters(p, [type("Ch", (), {"index": 1, "title": "K1",
                                            "raw_text": "Harry met Bob."})()])
    return p


def _factory(_agent):  # fake klient nikdy nevolá reálné API v těchto testech
    from src.llm.client import FakeLLMClient
    return FakeLLMClient([Completion("unused", False, 1, 1)])


def test_clean_chapter_reaches_done(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        translation="Harry potkal Boba.", new_terms=[], rendered_terms=[], questions=[]))
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    ch = state.get_chapter(db, 1)
    out = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "done"
    assert state.get_chapter(db, 1)["translated_text"] == "Harry potkal Boba."


def test_process_chapter_notes_have_finding_ids(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "špatný překlad", [], [], []))
    monkeypatch.setattr(T, "revise_chapter", lambda *a, **k: T.TranslationResult(
        "pořád špatný", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    ch = state.get_chapter(db, 1)
    pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    row = state.get_chapter(db, 1)
    saved = json.loads(row["notes"])
    assert saved   # nálezy skutečně vznikly
    assert all("id" in f and "resolved" in f for f in saved)


def test_critical_finding_triggers_revision_then_flags_after_max(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "špatný překlad", [], [], []))
    monkeypatch.setattr(T, "revise_chapter", lambda *a, **k: T.TranslationResult(
        "pořád špatný", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    ch = state.get_chapter(db, 1)
    out = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "flagged"
    assert state.get_chapter(db, 1)["revision_rounds"] == 2  # MAX_REVIZE


def test_blocking_question_sets_needs_human(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "překlad", [], [], [{"kind": "name", "scope_key": "cand_x",
                             "guess_answer": None, "text": "kdo je X?",
                             "severity": "blocking"}]))
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    ch = state.get_chapter(db, 1)
    out = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "needs_human"
    assert state.chapter_has_open_blocking(db, 1)


def test_new_term_creates_candidate_and_question(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "Nevernever je divný.", [{"term_en": "Nevernever", "cz": "Nikdykdy",
                                  "note": "", "type": "place"}], [], []))
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    ch = state.get_chapter(db, 1)
    pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    terms = glossary.all_terms(db)
    cand = [t for t in terms if t["canonical_en"] == "Nevernever"]
    assert cand and cand[0]["status"] == "candidate"
    assert any(q["kind"] == "term" for q in state.unanswered_questions(db))
    # nový kandidát MUSÍ mít term_mentions řádek (jinak ho requeue nenajde),
    # i když jeho EN povrch není v EN textu kapitoly
    assert state.chapters_mentioning_term(db, cand[0]["term_id"]) == [1]


def test_processing_recovered_before_next_run(tmp_path, monkeypatch):
    db = _db(tmp_path)
    state.set_status(db, 1, "processing")
    assert state.recover_processing(db) == 1


def test_critic_fatal_error_propagates_and_flags_preserving_translation(tmp_path, monkeypatch):
    """Kolo 22 IMPORTANT (plan-consensus) - PŮVODNĚ (před Task 2's
    checkpoint) tohle asserovalo `status != "flagged"` - kritikovo
    `FatalRunError` na PRVNÍM volání (před revizní smyčkou) nechávalo
    kapitolu `processing`, nikdy komitnutou. Kolo 22 tenhle gap ZAVŘELO
    schválně - `_checkpoint_flagged()` teď scénový překlad zachová jako
    `flagged` PŘED re-raise, stejně jako revizní smyčka dělá od kola 13."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "překlad", [], [], []))
    def boom(*a, **k): raise FatalRunError("bad key")
    monkeypatch.setattr(C, "review", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "překlad"


def test_hallucinated_rendered_term_does_not_trigger_revision(tmp_path, monkeypatch):
    db = _db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("UPDATE glossary SET canonical_en='Grey Cloak', cz='Šedý plášť', "
                     "status='approved' WHERE term_id='t1'")
    # translator hlásí rendered_term, který ve výsledném CZ NENÍ
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "Šedý plášť promluvil.",   # CZ obsahuje kanonický tvar
        [], [{"term_id": "t1", "cz_as_used": "Popelář"}], []))   # ale hlásí "Popelář"
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    out = pipeline.process_chapter(db, state.get_chapter(db, 1), client_factory=_factory,
        guide={"characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "done"          # žádná falešná inconsistency/revize
    assert out["revision_rounds"] == 0


def test_critic_recoverable_failure_flags_chapter(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "překlad", [], [], []))
    def boom(*a, **k): raise ValueError("rozbitý JSON od kritika")
    monkeypatch.setattr(C, "review", boom)
    out = pipeline.process_chapter(db, state.get_chapter(db, 1), client_factory=_factory,
        guide={"characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "flagged"
    assert "kritik selhal" in state.get_chapter(db, 1)["notes"]


def test_run_drift_check_creates_global_question(tmp_path):
    db = _db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='done' WHERE idx=1")
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (2,'K2','x','done')")
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) "
                     "VALUES ('tc','Council','Rada')")
    state.replace_term_mentions(db, 1, [{"term_id": "tc", "cz_form": "Rada",
                                         "scene_idx": None, "source": "detected"}])
    state.replace_term_mentions(db, 2, [{"term_id": "tc", "cz_form": "Koncil",
                                         "scene_idx": None, "source": "detected"}])
    drifts = pipeline.run_drift_check(db, 2)
    assert drifts and drifts[0]["term_id"] == "tc"
    gq = [q for q in state.unanswered_questions(db) if q["chapter_idx"] is None]
    assert gq and gq[0]["scope_key"] == "tc"


def test_revision_recoverable_failure_flags_chapter_preserves_translation(
        tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "prvotní scénový překlad", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    def boom(*a, **k): raise ValueError("chybí koncový marker - useknutý výstup")
    monkeypatch.setattr(T, "revise_chapter", boom)
    ch = state.get_chapter(db, 1)
    out = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "flagged"
    assert state.get_chapter(db, 1)["translated_text"] == "prvotní scénový překlad"
    assert "revize selhala" in state.get_chapter(db, 1)["notes"]


def test_revision_fatal_error_preserves_translation_before_reraising(
        tmp_path, monkeypatch):
    """Kolo 13 IMPORTANT (plan-consensus) - FatalRunError BĚHEM revize
    (rozbitý CLI/auth) MUSÍ uložit poslední platný překlad JAKO
    `flagged` PŘED re-raise - jinak `_cmd_run`'s `flagged` status
    (kolo 10/11) je jen kosmetický, skutečný PŘEKLAD zůstává ztracený
    (commit v `pipeline.py` běží normálně až na konci funkce, výjimka
    ho nikdy nedosáhne)."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "prvotní scénový překlad", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    def boom(*a, **k): raise FatalRunError("codex auth expired")
    monkeypatch.setattr(T, "revise_chapter", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "prvotní scénový překlad"


def test_revision_fatal_error_preserves_existing_term_mentions(tmp_path, monkeypatch):
    """Kolo 18 IMPORTANT (plan-consensus) - `mentions=[]` (kolo-13
    původní verze) NENÍ "jen bez nových mentions" - `state.commit_
    chapter_result()` PŘED vložením VŽDY smaže VŠECHNY existující
    `term_mentions` pro tuhle kapitolu, bez ohledu na co se posílá.
    Pro `--retry-flagged` kapitolu s existujícím mention z dřívějšího
    úspěšného commitu by prázdný seznam mentions ty existující
    nenávratně smazal, i když `translated_text` zůstal zachovaný."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz,status) "
                     "VALUES ('t1','Harry','Harry','approved')")
        # `_confident_surface_match()` (concordance.py) záměrně NEUZNÁ
        # jméno, co se v EN textu objeví JEN na začátku věty (pilot
        # nález 2026-09-13 - "Will"/"will" kolize) - `_db()` fixture's
        # výchozí "Harry met Bob." má "Harry" JEN tam, takže `t1` by
        # `examined_terms()` nikdy nezahrnula. Přidej druhý výskyt
        # uprostřed věty.
        conn.execute("UPDATE chapters SET raw_text='Harry met Bob. Bob greeted Harry.' "
                     "WHERE idx=1")
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "Harry je tady.", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    def boom(*a, **k): raise FatalRunError("codex auth expired")
    monkeypatch.setattr(T, "revise_chapter", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert 1 in state.chapters_mentioning_term(db, "t1")


def test_revision_fatal_error_preserves_existing_open_questions(tmp_path, monkeypatch):
    """Kolo 20 IMPORTANT (plan-consensus) - `state.begin_chapter()`
    (úplný začátek `process_chapter()`) UNCONDITIONALLY smaže všechny
    nezodpovězené otázky kapitoly - `commit_chapter_result()` je znovu
    nesmaže, jen upsertuje, co dostane. `questions=[]` (kolo-13 původní
    verze) by tedy TRVALE ztratilo existující otevřené otázky z
    dřívějšího úspěšného běhu pro `--retry-flagged` scénář (stejná
    třída chyby jako kolo-18's mentions, jiný zdroj)."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    state.upsert_open_question(db, {
        "chapter_idx": 1, "kind": "term", "scope_key": "cand_x",
        "text": "Nový termín 'X' přeložen jako 'Y'. Sedí to?",
        "guess_answer": "Y", "severity": "guess"})
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "Text.", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    def boom(*a, **k): raise FatalRunError("codex auth expired")
    monkeypatch.setattr(T, "revise_chapter", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    open_qs = state.unanswered_questions(db)
    assert any(q["scope_key"] == "cand_x" for q in open_qs)


def test_revision_fatal_error_from_critic_after_successful_revision_preserves_new_cz(
        tmp_path, monkeypatch):
    """Kolo 21 IMPORTANT (plan-consensus) - checkpoint (kolo 13) obaloval
    jen `translator.revise_chapter()`, ne NÁSLEDUJÍCÍ `_run_critic()`
    volání VE STEJNÉ iteraci. Když Codex ÚSPĚŠNĚ dokončí revizi (nové
    `cz`) a HNED PO NÍ kritik (VŽDY Claude, i při `--translator codex`)
    selže na `FatalRunError`, nové `cz` se BEZ týhle opravy nikdy
    nedostane k commitu - kapitola zůstane `processing`, příští `run`
    ji celou přeloží znovu od nuly, i když revize už jednou (zaplaceně)
    uspěla."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "prvotní scénový překlad", [], [], []))
    monkeypatch.setattr(T, "revise_chapter", lambda *a, **k: T.TranslationResult(
        "revidovaný překlad", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    calls = {"n": 0}
    def review(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:      # 1. volání = PŘED smyčkou, vyžádá revizi
            return always_bad
        raise FatalRunError("codex auth expired po revizi")   # 2. volání = PO úspěšné revizi
    monkeypatch.setattr(C, "review", review)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "revidovaný překlad"


def test_scene_loop_fatal_error_restores_existing_open_question(tmp_path, monkeypatch):
    """Kolo 23 IMPORTANT (plan-consensus) - scénová smyčka (PŘED "kontrola"
    blokem) neměla ŽÁDNÝ checkpoint (na rozdíl od kontrola bloku/revizní
    smyčky, kolo 13/18/20/21/22) - selhání PŘÍMO v ní (např. znovu
    rozbitý Codex CLI/auth na `--retry-flagged` kapitole) propagovalo
    BEZ obnovy `existing_questions`, i když `begin_chapter()` (transakce
    A) je UŽ nenávratně smazal na začátku funkce. Žádný nový `cz`
    neexistuje (na rozdíl od kol 13/18/20/21/22's scénářů) - fix obnoví
    JEN staré otázky, nic víc."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    state.upsert_open_question(db, {
        "chapter_idx": 1, "kind": "term", "scope_key": "cand_x",
        "text": "Nový termín 'X' přeložen jako 'Y'. Sedí to?",
        "guess_answer": "Y", "severity": "guess"})
    def boom(*a, **k): raise FatalRunError("codex auth expired znovu")
    monkeypatch.setattr(T, "translate_scene", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    open_qs = state.unanswered_questions(db)
    assert any(q["scope_key"] == "cand_x" for q in open_qs)


def test_scene_loop_keyboard_interrupt_restores_existing_open_question(
        tmp_path, monkeypatch):
    """Kolo 24 IMPORTANT (plan-consensus) - `KeyboardInterrupt` (Ctrl+C)
    NENÍ `Exception` podtřída (je `BaseException`) - holé `except
    Exception` kolem scénové smyčky (kolo 23) by ho přeskočilo úplně,
    staré otázky by zůstaly ztracené stejně jako bez opravy vůbec.
    Uživatelovo přerušení BĚHEM Codex volání je reálný, běžný scénář
    (dlouho běžící `run`, uživatel chce zastavit)."""
    db = _db(tmp_path)
    state.upsert_open_question(db, {
        "chapter_idx": 1, "kind": "term", "scope_key": "cand_x",
        "text": "Nový termín 'X' přeložen jako 'Y'. Sedí to?",
        "guess_answer": "Y", "severity": "guess"})
    def boom(*a, **k): raise KeyboardInterrupt()
    monkeypatch.setattr(T, "translate_scene", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(KeyboardInterrupt):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    open_qs = state.unanswered_questions(db)
    assert any(q["scope_key"] == "cand_x" for q in open_qs)


def test_revision_keyboard_interrupt_preserves_translation(tmp_path, monkeypatch):
    """Kolo 24 IMPORTANT (plan-consensus) - stejná mezera jako výš, jen
    v revizní smyčce (kolo 13/18/20/21/22's `_checkpoint_flagged()`
    volání): holé `except FatalRunError` by `KeyboardInterrupt` BĚHEM
    `revise_chapter()` přeskočilo, `cz` (scénový překlad) by propadl
    stejně, jako kdyby žádný z předchozích kol fix nikdy nebyl."""
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "scénový překlad", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    def boom(*a, **k): raise KeyboardInterrupt()
    monkeypatch.setattr(T, "revise_chapter", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(KeyboardInterrupt):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "scénový překlad"


def test_pre_loop_critic_keyboard_interrupt_preserves_scene_translation(
        tmp_path, monkeypatch):
    """Kolo 25 IMPORTANT (plan-consensus) - Codex si všiml, že kolo 24
    přidalo `KeyboardInterrupt` do `except` klauzule PRE-LOOP kritika
    (kolo 22), ale chyběl pro ni odpovídající regresní test (na rozdíl
    od scénové smyčky a revizní smyčky, co testy dostaly). Stejný
    scénář jako `test_pre_loop_critic_fatal_error_preserves_scene_
    translation`, jen `KeyboardInterrupt` místo `FatalRunError`."""
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "scénový překlad", [], [], []))
    def boom(*a, **k): raise KeyboardInterrupt()
    monkeypatch.setattr(C, "review", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(KeyboardInterrupt):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "scénový překlad"


def test_kontrola_phase_fatal_error_preserves_scene_translation(tmp_path, monkeypatch):
    """Kolo 25 IMPORTANT (plan-consensus) - `_verified_rendered()`/
    `glossary.all_terms()`/`concordance.check_chapter()` (MEZI scénovou
    smyčkou a `_run_critic()` voláním) neměly ŽÁDNÝ checkpoint - jen
    `_run_critic()` samotné bylo chráněné (kolo 22). Selhání PŘÍMO
    tady (deterministický kód, ale pořád může selhat - DB čtení
    glosáře, neočekávaný tvar dat) by zahodilo hotový scénový překlad
    stejně jako mezery, co kola 20-24 zavřely jinde."""
    db = _db(tmp_path)
    from src import concordance
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "scénový překlad", [], [], []))
    def boom(*a, **k): raise ValueError("rozbita konkordance")
    monkeypatch.setattr(concordance, "check_chapter", boom)
    ch = state.get_chapter(db, 1)
    # Kolo 27 IMPORTANT (plan-consensus) - obyčejný `Exception` (ne
    # `FatalRunError`/`KeyboardInterrupt`) checkpoint teď VRÁTÍ jako
    # výsledek funkce MÍSTO re-raise - `process_chapter()` tedy
    # NEVYHODÍ výjimku, jen vrátí `flagged` výsledek (jinak by main.py's
    # generický `except Exception: status="error"` `flagged` přepsal).
    result = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert result["status"] == "flagged"
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "scénový překlad"


def test_transakce_b_prep_fatal_error_preserves_final_translation(tmp_path, monkeypatch):
    """Kolo 25 IMPORTANT (plan-consensus) - "příprava transakce B" (nové
    termíny do glosáře, `concordance.build_mentions()`, finální
    `commit_chapter_result()`) běží AŽ PO revizní smyčce, ale nemá
    ŽÁDNÝ checkpoint - poslední nechráněné místo v celé funkci. `cz` je
    v tuhle chvíli FINÁLNÍ (nejlepší dostupný překlad), selhání tady by
    ho zahodilo úplně stejně, jako kdyby k žádnému z předchozích kol
    fixů nikdy nedošlo."""
    db = _db(tmp_path)
    from src import concordance
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "finální překlad", [], [], []))
    real_build_mentions = concordance.build_mentions
    calls = {"n": 0}
    def boom(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:        # 1. volání = transakce B prep (má selhat)
            raise ValueError("rozbita konkordance pri mentions")
        return real_build_mentions(*a, **k)   # 2. volání = uvnitř checkpointu
    monkeypatch.setattr(concordance, "build_mentions", boom)
    ch = state.get_chapter(db, 1)
    result = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert result["status"] == "flagged"
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "finální překlad"


def test_checkpoint_glossary_fetch_failure_preserves_existing_mentions(
        tmp_path, monkeypatch):
    """Kolo 26 IMPORTANT (plan-consensus) - `_checkpoint_flagged()`'s
    vlastní `glossary.all_terms()` re-fetch (kolo 25) může SAMO selhat -
    pád na `gl_rows=[]` by `concordance.build_mentions()` vrátilo
    prázdný seznam a `commit_chapter_result()` (VŽDY smaže existující
    `term_mentions` před vložením, kolo 18) by je nenávratně smazal.
    Fallback musí být `existing_mentions` (snapshot PŘED `begin_
    chapter()`), NE `[]` - stejná třída chyby jako kolo-18's původní
    nález, teď uvnitř checkpointu samotného."""
    db = _db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz,status) "
                     "VALUES ('cand_x','X','Y','candidate')")
    state.replace_term_mentions(db, 1, [{"term_id": "cand_x", "cz_form": "Y",
                                         "scene_idx": 0, "source": "rendered"}])
    from src import glossary
    real_all_terms = glossary.all_terms
    calls = {"n": 0}
    def boom(*a, **k):
        calls["n"] += 1
        # 1. volání = `_glossary_block()` (guide prep, PŘED scénovou
        # smyčkou) - musí uspět, ať se dostaneme k "kontrola" fázi.
        # 2.+ volání = "kontrola" fáze's VLASTNÍ `glossary_rows =
        # glossary.all_terms(...)` (spustí fatální větev) A `_checkpoint_
        # flagged()`'s VLASTNÍ re-fetch (má taky selhat - to je to, co
        # test ověřuje).
        if calls["n"] == 1:
            return real_all_terms(*a, **k)
        raise RuntimeError("DB nedostupná")
    monkeypatch.setattr(glossary, "all_terms", boom)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "scénový překlad", [], [], []))
    ch = state.get_chapter(db, 1)
    result = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert result["status"] == "flagged"
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "scénový překlad"
    mentions = state.chapter_mentions(db, 1)
    assert any(m["term_id"] == "cand_x" for m in mentions)


def test_checkpoint_preserves_question_from_concordance_finding(tmp_path, monkeypatch):
    """Kolo 26 IMPORTANT (plan-consensus) - normální transakce B
    (`src/pipeline.py:157-162`) překlápí `findings` položky s `action==
    "question"` (z `concordance.check_chapter()`, NE z translatoru) do
    DB otázek stejně jako `questions_now`. `_checkpoint_flagged()` bez
    týhle větve by zachráněný `cz` uložil s nálezem v `notes`, ale BEZ
    odpovídající strukturované otázky v `questions` tabulce -
    nekonzistence oproti normálnímu dokončení."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    from src import concordance
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "scénový překlad", [], [], []))
    finding_q = [{"source": "concordance", "type": "omission", "severity": "guess",
                  "action": "question", "term_id": "cand_y", "expected": None,
                  "actual": "Y?", "cz_excerpt": "x",
                  "issue": "Termín 'Y' se v překladu nenašel. OK?", "suggestion": None}]
    monkeypatch.setattr(concordance, "check_chapter", lambda *a, **k: finding_q)
    def boom(*a, **k): raise FatalRunError("codex auth expired")
    monkeypatch.setattr(C, "review", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    open_qs = state.unanswered_questions(db)
    assert any(q["scope_key"] == "cand_y" for q in open_qs)


def test_pre_loop_critic_fatal_error_preserves_scene_translation(tmp_path, monkeypatch):
    """Kolo 22 IMPORTANT (plan-consensus) - PRVNÍ `_run_critic()` volání
    (PŘED revizní smyčkou) nebylo chráněné VŮBEC - kola 13/18/20/21's
    checkpointy jsou UVNITŘ `while` smyčky. Fatální chyba kritika (VŽDY
    Claude, i při `--translator codex`) HNED po úspěšném (a zaplaceném
    přes Codex) scénovém překladu by `cz` zahodila stejně jako mezery,
    co předchozí kola opravila uvnitř smyčky - jen o krok DŘÍV."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "scénový překlad", [], [], []))
    def boom(*a, **k): raise FatalRunError("codex auth expired")
    monkeypatch.setattr(C, "review", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    row = state.get_chapter(db, 1)
    assert row["status"] == "flagged"
    assert row["translated_text"] == "scénový překlad"


def test_pre_loop_critic_fatal_error_preserves_new_question_from_current_attempt(
        tmp_path, monkeypatch):
    """Kolo 22 IMPORTANT (plan-consensus) - `existing_questions` (kolo 20)
    samo neslo NOVÉ nejistoty z AKTUÁLNÍHO (právě zachráněného) výsledku -
    jen STARÉ z PŘED `begin_chapter()`. Fatální chyba po úspěšném
    scénovém překladu s NOVOU otázkou (z `translate_scene()`'s `res.
    questions`) by tu novou otázku ztratila, i když překlad, na který se
    ptá, se zachová - nekonzistence mezi uloženým textem a otázkami o
    něm."""
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "překlad s otázkou", [], [],
        [{"kind": "term", "scope_key": "cand_new", "guess_answer": "Y",
          "text": "Nový termín?", "severity": "guess"}]))
    def boom(*a, **k): raise FatalRunError("codex auth expired")
    monkeypatch.setattr(C, "review", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    open_qs = state.unanswered_questions(db)
    assert any(q["scope_key"] == "cand_new" for q in open_qs)


def test_revision_timeout_flags_chapter_preserves_translation_integration(
        tmp_path, monkeypatch):
    """Kolo 9 IMPORTANT (plan-consensus) - integrační test PRES CELY
    stack (CodexLLMClient -> PipelineLLMClient -> pipeline.py revizni
    smycka, Task 2), ne jen mockovany ValueError jako Task 2's vlastni
    test - timeout BEHEM revize (StylistTimeoutError) nesmi zastavit
    cely beh ani zahodit hotovy scenovy preklad."""
    from src.llm.client import CodexLLMClient, PipelineLLMClient
    from src.agents.stylist import StylistTimeoutError
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    calls = {"n": 0}
    def fake_exec(prompt, *, codex_cmd, codex_model, timeout, label):
        calls["n"] += 1
        if calls["n"] == 1:      # 1. volani = scenovy preklad, uspeje
            return ("===PREKLAD===\nprvotní scénový překlad\n"
                    "===METADATA===\n{}\n===KONEC===")
        raise StylistTimeoutError("codex exec překročil timeout 300s. [translator]")
    monkeypatch.setattr("src.agents.stylist._exec_codex", fake_exec)
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    def cf(agent):
        inner = CodexLLMClient(["codex"], config.CODEX_MODEL) if agent == "translator" else None
        return PipelineLLMClient(inner, run_id=rid, agent=agent,
                                 db_path=db, config_mod=config)
    ch = state.get_chapter(db, 1)
    out = pipeline.process_chapter(db, ch, client_factory=cf, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "flagged"
    assert state.get_chapter(db, 1)["translated_text"] == "prvotní scénový překlad"
