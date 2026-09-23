"""Zpracování odpovědi na otázku: kam se zapíše a které kapitoly se přepočítají.

Oddělené od `main.py`, aby šlo testovat bez CLI.

Dvě fáze:
1. `guide.json` (vztahy, volná pravidla) - soubor, atomický zápis, idempotentní
2. DB (glosář, odpověď, requeue kapitol) - jedna transakce

Když spadne fáze 2, otázka zůstane nezodpovězená a `answer` se dá pustit znovu;
fáze 1 se jen zopakuje se stejným výsledkem.
"""
import re

from src import glossary, guide as guide_mod, state


def _chapters_with_both_names(db_path: str, a: str, b: str) -> list:
    idxs = []
    for ch in state.chapters_by_status(db_path, ("done", "flagged")):
        text = ch.get("raw_text") or ""
        if all(re.search(r"\b" + re.escape(n) + r"\b", text, re.IGNORECASE)
               for n in (a, b) if n):
            idxs.append(ch["idx"])
    return idxs


def _chapters_from(db_path: str, from_idx) -> list:
    return [ch["idx"] for ch in state.chapters_by_status(db_path, ("done", "flagged"))
            if from_idx is None or ch["idx"] >= from_idx]


def preview_affected_chapters(db_path: str, question: dict) -> list:
    """Kolik/které kapitoly by se přepočítaly, KDYBY se na tuhle otázku
    odpovědělo jinak než model hádal - STEJNÁ logika jako `apply_answer`'s
    `requeue_idxs` větev, ale BEZ zápisu (žádná odpověď, žádný glosář
    zápis, žádné DB update). Pro UI náhled (questions-review, 2026-09-23) -
    uživatel chce vidět dopad PŘED tím, než se rozhodne odpovědět."""
    kind = question["kind"]
    scope_key = question["scope_key"]
    if kind in ("term", "name"):
        tid = glossary.resolve_term_or_surface(db_path, scope_key)
        if not tid:
            return []   # nový termín - žádné existující zmínky
        return state.chapters_mentioning_term(db_path, tid)
    elif kind == "relationship":
        a, _, b = scope_key.partition("|")
        return _chapters_with_both_names(db_path, a, b)
    else:
        return _chapters_from(db_path, question.get("chapter_idx"))


def questions_for_chapter(db_path: str, idx: int) -> list:
    """Otevřené otázky RELEVANTNÍ pro tuhle kapitolu - buď je přímo
    kapitolová (`chapter_idx == idx`, typicky "nový termín, sedí
    odhad?"), NEBO je globální/víc-kapitolová a `idx` je mezi jejími
    `preview_affected_chapters` (drift napříč knihou). Pro editor.html
    (2026-09-23) - "chci vidět otázky s kontextem EN/CZ týhle kapitoly",
    ne slepý seznam na samostatné stránce. Každá otázka dostane navíc
    `affected_chapters` (stejné pole jako `questions_server.py`'s GET
    /api/questions), ať editor ukáže "tahle otázka se týká i kapitol
    X, Y" i uvnitř jedné konkrétní kapitoly."""
    result = []
    for q in state.unanswered_questions(db_path):
        if q.get("chapter_idx") == idx:
            q["affected_chapters"] = preview_affected_chapters(db_path, q)
            result.append(q)
            continue
        affected = preview_affected_chapters(db_path, q)
        if idx in affected:
            q["affected_chapters"] = affected
            result.append(q)
    return result


def apply_answer(db_path: str, guide_path: str, qid: int, answer_text: str) -> dict:
    if not answer_text or not answer_text.strip():
        raise ValueError("Prázdná odpověď - napiš, co se má zapsat.")
    q = state.get_question(db_path, qid)
    if q is None:
        raise ValueError(f"Otázka {qid} neexistuje.")
    if q.get("answer") is not None:
        raise ValueError(f"Otázka {qid} už je zodpovězená.")

    kind = q["kind"]
    scope_key = q["scope_key"]
    answer_text = answer_text.strip()
    glossary_ops, target_tid = [], None

    if kind in ("term", "name"):
        # "Šedý plášť | Šedého pláště" = kanonický tvar + schválené alternativy
        parts = [p.strip() for p in answer_text.split("|") if p.strip()]
        if not parts:
            raise ValueError("Odpověď musí obsahovat český tvar termínu.")
        tid = glossary.resolve_term_or_surface(db_path, scope_key)
        target_tid = tid or ("term_" + glossary.slugify(scope_key))
        if tid:
            glossary_ops.append(("promote", target_tid, parts[0]))
        else:
            glossary_ops.append(("add_approved", scope_key, parts[0],
                                 "name" if kind == "name" else "term"))
        glossary_ops += [("add_accepted_alt", target_tid, alt) for alt in parts[1:]]
    elif kind == "relationship":
        a, _, b = scope_key.partition("|")
        g = guide_mod.load_guide(guide_path)
        rels = g.setdefault("relationships", [])
        for r in rels:
            if guide_mod.relationship_key(r.get("a", ""), r.get("b", "")) == scope_key:
                r["address"] = answer_text
                break
        else:
            rels.append({"a": a, "b": b, "address": answer_text})
        guide_mod.save_guide(guide_path, g)
    else:  # style / other
        guide_mod.add_rule(guide_path, answer_text)

    # Requeue jen u guess otázky, jejíž odpověď se liší od toho, co model zvolil.
    requeue_idxs = []
    if q["severity"] == "guess" and answer_text != (q.get("guess_answer") or ""):
        if kind in ("term", "name"):
            requeue_idxs = state.chapters_mentioning_term(db_path, target_tid)
        elif kind == "relationship":
            a, _, b = scope_key.partition("|")
            requeue_idxs = _chapters_with_both_names(db_path, a, b)
        else:
            requeue_idxs = _chapters_from(db_path, q.get("chapter_idx"))

    blocking_idx = q["chapter_idx"] if q["severity"] == "blocking" else None
    return state.commit_answer(db_path, qid=qid, answer_text=answer_text,
                               glossary_ops=glossary_ops, requeue_idxs=requeue_idxs,
                               blocking_chapter_idx=blocking_idx)
