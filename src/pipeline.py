"""Orchestrace překladu jedné kapitoly. Jediné místo, které drátuje agenty,
stav, glosář a deterministické kontroly dohromady.

Sekvence je pevná (translator → concordance + kritik → revizní smyčka → uložení),
protože kroky jsou vždy stejné. LLM se volá jen na to, co kód neumí.

Dva zápisy do DB, mezi nimi běží LLM volání MIMO transakci (jsou dlouhá):
- transakce A: kapitola → `processing`, smazání jejích starých otevřených otázek
- transakce B: glosář + term_mentions + otázky + kapitola najednou

Agenty voláme modulově-kvalifikovaně (`translator.translate_scene`), aby šly
v testech monkeypatchnout.
"""
import hashlib
import json

import config
from src import concordance, glossary, ingest, state
from src import guide as guide_mod
from src.agents import critic, translator
from src.llm.client import FatalRunError


def has_revise_triggers(findings: list) -> bool:
    return any(f.get("action") == "revise" for f in findings or [])


def _guide_block(guide: dict) -> str:
    return guide_mod.guide_as_prompt_block(guide or {})


def _glossary_block(db_path: str) -> str:
    return glossary.as_prompt_block(db_path)


def _verified_rendered(rendered: list, cz_text: str) -> list:
    """Translator může ohlásit tvar, který ve výsledném textu není (halucinace
    nebo pozůstatek po revizi). Neověřené zahoď PŘED jakoukoliv kontrolou."""
    return [r for r in rendered
            if r.get("cz_as_used") and concordance.contains_form(cz_text, r["cz_as_used"])]


def _scope_key_for(q: dict) -> str:
    """style/other otázky nemají přirozený klíč - do DB nesmí jít prázdný
    (partial unique index by přestal fungovat)."""
    key = (q.get("scope_key") or "").strip()
    if key:
        return key
    return hashlib.sha1((q.get("text") or "").encode("utf-8")).hexdigest()[:16]


def _run_critic(en: str, cz: str, client):
    """Vrací (findings, failed). FatalRunError propaguje - ten končí celý běh."""
    try:
        return critic.review(en, cz, client), False
    except FatalRunError:
        raise
    except Exception as e:
        pseudo = {"source": "critic", "type": "fluency", "severity": "critical",
                  "action": "note", "term_id": None, "expected": None,
                  "actual": None, "cz_excerpt": None,
                  "issue": f"kritik selhal: {e}", "suggestion": None}
        return [pseudo], True


def process_chapter(db_path: str, chapter: dict, *, client_factory, guide: dict) -> dict:
    idx = chapter["idx"]
    en = chapter["raw_text"]

    state.begin_chapter(db_path, idx)          # transakce A

    guide_block = _guide_block(guide)
    glossary_block = _glossary_block(db_path)

    # --- překlad po scénách ---
    scenes = ingest.split_into_scenes(en, config.CHAPTER_SPLIT_WORD_THRESHOLD)
    parts, rendered, questions = [], [], []
    new_terms: dict = {}
    for scene_idx, scene in enumerate(scenes):
        res = translator.translate_scene(scene, guide_block, glossary_block,
                                         client_factory("translator"))
        parts.append(res.translation)
        for nt in res.new_terms:
            key = (nt.get("term_en") or "").strip().casefold()
            if key and key not in new_terms:
                new_terms[key] = nt
        questions.extend(res.questions)
        for rt in res.rendered_terms:
            rendered.append({"term_id": rt.get("term_id"),
                             "cz_as_used": rt.get("cz_as_used"),
                             "scene_idx": scene_idx})
    cz = "\n\n".join(p for p in parts if p)
    rendered = _verified_rendered(rendered, cz)

    # --- kontrola: deterministicky + nezávislý kritik ---
    glossary_rows = glossary.all_terms(db_path)
    findings = concordance.check_chapter(en, cz, glossary_rows, rendered)
    critic_findings, critic_failed = _run_critic(en, cz, client_factory("critic"))
    findings += critic_findings

    # --- revizní smyčka ---
    rounds = 0
    while (has_revise_triggers(findings) and rounds < config.MAX_REVIZE
           and not critic_failed):
        to_fix = [f for f in findings if f.get("action") == "revise"]
        res = translator.revise_chapter(en, cz, to_fix, guide_block, glossary_block,
                                        client_factory("translator"))
        cz = res.translation
        for nt in res.new_terms:                  # nové termíny se KUMULUJÍ
            key = (nt.get("term_en") or "").strip().casefold()
            if key and key not in new_terms:
                new_terms[key] = nt
        # zbytek metadat je celokapitolový a NAHRAZUJE agregát ze scén
        questions = list(res.questions)
        rendered = _verified_rendered(
            [{"term_id": rt.get("term_id"), "cz_as_used": rt.get("cz_as_used"),
              "scene_idx": None} for rt in res.rendered_terms], cz)
        findings = concordance.check_chapter(en, cz, glossary_rows, rendered)
        critic_findings, critic_failed = _run_critic(en, cz, client_factory("critic"))
        findings += critic_findings
        rounds += 1

    # --- příprava transakce B ---
    new_candidates, extra_mentions = [], []
    db_questions = []
    for nt in new_terms.values():
        term_en = (nt.get("term_en") or "").strip()
        if not term_en:
            continue
        cz_form = nt.get("cz") or ""
        # termín se mohl přes revize z finálního překladu vytratit
        mention_form = cz_form if (cz_form and concordance.contains_form(cz, cz_form)) else None
        mention_source = "rendered" if mention_form else "omission"
        existing = glossary.resolve_surface(db_path, term_en)
        if existing:
            extra_mentions.append({"term_id": existing, "cz_form": mention_form,
                                   "scene_idx": None, "source": mention_source})
            continue
        cand = {"term_id": "cand_" + glossary.slugify(term_en),
                "canonical_en": term_en, "aliases": [], "cz": cz_form,
                "accepted_alt": [], "note": nt.get("note", ""),
                "type": nt.get("type", "term"), "status": "candidate"}
        new_candidates.append(cand)
        extra_mentions.append({"term_id": cand["term_id"], "cz_form": mention_form,
                               "scene_idx": None, "source": mention_source})
        db_questions.append({
            "chapter_idx": idx, "kind": "term", "scope_key": cand["term_id"],
            "text": f"Nový termín '{term_en}' přeložen jako '{cz_form}'. Sedí to?",
            "guess_answer": cz_form, "severity": "guess"})

    glossary_rows_all = glossary_rows + new_candidates
    mentions = concordance.build_mentions(en, cz, glossary_rows_all, rendered)
    mentions = [{"term_id": m.term_id, "cz_form": m.cz_form,
                 "scene_idx": m.scene_idx, "source": m.source} for m in mentions]
    mentions += extra_mentions

    for q in questions:
        db_questions.append({
            "chapter_idx": idx, "kind": q.get("kind") or "other",
            "scope_key": _scope_key_for(q), "text": q.get("text") or "",
            "guess_answer": q.get("guess_answer"),
            "severity": q.get("severity") or "guess"})
    for f in findings:
        if f.get("action") != "question":
            continue
        db_questions.append({
            "chapter_idx": idx, "kind": "term", "scope_key": f.get("term_id") or "",
            "text": f.get("issue") or "", "guess_answer": f.get("actual"),
            "severity": "guess"})
    for q in db_questions:
        q["scope_key"] = _scope_key_for(q)

    has_blocking = any(q["severity"] == "blocking" for q in db_questions)
    if has_blocking:
        status = "needs_human"
    elif critic_failed or has_revise_triggers(findings):
        status = "flagged"
    else:
        status = "done"

    from src import findings as findings_mod
    findings = findings_mod.assign_ids(findings)

    result = state.commit_chapter_result(
        db_path, idx, translated_text=cz, revision_rounds=rounds,
        notes_json=json.dumps(findings, ensure_ascii=False), status=status,
        new_candidates=new_candidates, mentions=mentions, questions=db_questions)

    return {"idx": idx, "status": status, "revision_rounds": rounds,
            "new_terms": len(new_candidates),
            "questions_created": result["questions_created"],
            "findings": findings}


def run_drift_check(db_path: str, up_to_chapter: int) -> list:
    """Napříč hotovými kapitolami hledá rozjeté tvary termínu. Z každého nálezu
    globální otázka - odpověď pak běžnými requeue pravidly přepočítá kapitoly."""
    rows = [m for m in state.all_term_mentions(db_path)
            if m.get("chapter_idx") is not None and m["chapter_idx"] <= up_to_chapter]
    drifts = concordance.check_drift(rows)
    state.save_drift_report(db_path, up_to_chapter, {"drift": drifts})
    for d in drifts:
        forms = [r["cz_form"] for r in rows
                 if r["term_id"] == d["term_id"] and r.get("cz_form")]
        most_common = max(set(forms), key=forms.count) if forms else None
        state.upsert_open_question(db_path, {
            "chapter_idx": None, "kind": "term", "scope_key": d["term_id"],
            "text": f"Termín se překládá různě: {', '.join(d['formy'])} "
                    f"(kapitoly {', '.join(str(k) for k in d['kapitoly'])}). "
                    "Který tvar je správný?",
            "guess_answer": most_common, "severity": "guess"})
    return drifts
