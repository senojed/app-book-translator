"""
Orchestrátor pipeline. Neobsahuje žádnou "inteligenci" navíc - jen řídí pořadí
volání agentů a stará se o perzistenci stavu mezi kroky. Rozhodovací logika
(co je nekonzistence, co je chyba) je v jednotlivých agentech.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src import state_db, glossary as gl
from src.ingest import split_into_scenes
from src.agents import translator, terminology, critic, cross_reference


def process_chapter(db_path: str, chapter: dict, is_calibration: bool) -> dict:
    """Zpracuje jednu kapitolu celou pipeline. Vrací shrnutí pro CLI výstup."""
    glossary = gl.load_glossary(config.GLOSSARY_PATH)
    style_guide = gl.load_style_guide(config.STYLE_GUIDE_PATH)

    scenes = split_into_scenes(chapter["raw_text"], config.CHAPTER_SPLIT_WORD_THRESHOLD)

    translated_parts = []
    all_new_terms = []
    all_open_questions = []

    for scene in scenes:
        result = translator.translate_chunk(scene, glossary, style_guide)
        translated_parts.append(result["translation"])
        all_new_terms.extend(result.get("new_terms", []))
        all_open_questions.extend(result.get("open_questions", []))
        # glosář aktualizujeme průběžně, aby další scéna stejné kapitoly
        # už viděla nové termíny z předchozí scény
        for t in result.get("new_terms", []):
            gl.add_or_update_term(
                config.GLOSSARY_PATH, t["term_en"], t["cz"], t.get("note", ""), t.get("type", "term")
            )
            glossary = gl.load_glossary(config.GLOSSARY_PATH)

    full_translation = "\n\n".join(translated_parts)

    # terminologická kontrola nezávisle na translatorovi
    term_check = terminology.check_terminology(full_translation, glossary)

    # kritik - nezávisle, bez viditelnosti translator reasoningu
    review = critic.review(chapter["raw_text"], full_translation)

    critical_findings = [f for f in review.get("findings", []) if f.get("severity") == "critical"]

    for q in all_open_questions:
        state_db.add_open_question(db_path, chapter["idx"], q)

    if critical_findings or term_check.get("inconsistencies"):
        status = "critic_flagged"
    elif all_open_questions and is_calibration:
        status = "needs_human"
    else:
        status = "done"

    notes = {
        "critic_findings": review.get("findings", []),
        "terminology_inconsistencies": term_check.get("inconsistencies", []),
    }

    state_db.update_chapter(
        db_path,
        chapter["idx"],
        translated_text=full_translation,
        status=status,
        critic_notes=json.dumps(notes, ensure_ascii=False),
    )

    return {
        "chapter_idx": chapter["idx"],
        "status": status,
        "new_terms_count": len(all_new_terms),
        "open_questions": all_open_questions,
        "critical_findings_count": len(critical_findings),
        "terminology_issues_count": len(term_check.get("inconsistencies", [])),
    }


def run_cross_reference(db_path: str, up_to_chapter: int):
    glossary = gl.load_glossary(config.GLOSSARY_PATH)
    with state_db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT idx, translated_text FROM chapters WHERE status = 'done' AND idx <= ? ORDER BY idx",
            (up_to_chapter,),
        ).fetchall()
    excerpts = {r["idx"]: r["translated_text"] for r in rows if r["translated_text"]}
    if not excerpts:
        return None
    report = cross_reference.check_drift(glossary, excerpts)
    state_db.save_cross_ref_report(db_path, up_to_chapter, report)
    return report
