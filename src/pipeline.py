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
from src import findings as findings_mod
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

    # Kolo 20 IMPORTANT (plan-consensus) - snapshot PŘED `begin_chapter()`
    # (viz vysvětlení výš) - `begin_chapter()` nezodpovězené otázky týhle
    # kapitoly nenávratně smaže, revizní smyčka's fatal-commit větev
    # (níž) je při selhání obnoví, ať se pro --retry-flagged scénář
    # neztratí navěky.
    existing_questions = [q for q in state.unanswered_questions(db_path)
                          if q.get("chapter_idx") == idx]

    # Kolo 26 IMPORTANT (plan-consensus) - snapshot existujících `term_
    # mentions` PŘED `begin_chapter()`, ze STEJNÉHO důvodu jako `existing_
    # questions` výš - `_checkpoint_flagged()` (níž) potřebuje BEZPEČNÝ
    # fallback pro případ, že si vlastní `glossary.all_terms()` fetch
    # nepovede (viz kolo 25/26's vysvětlení u `_checkpoint_flagged()`).
    existing_mentions = state.chapter_mentions(db_path, idx)

    state.begin_chapter(db_path, idx)          # transakce A

    # Kolo 23 IMPORTANT (plan-consensus) - viz vysvětlení výš - scénová
    # smyčka je jediná fáze bez checkpointu; obnov staré otázky PŘED
    # re-raise, ať `--retry-flagged` kapitola, co tu ZNOVU selže, o ně
    # nenávratně nepřijde.
    # Kolo 25 IMPORTANT (plan-consensus) - `try` rozšířen tak, aby
    # zahrnul i `_guide_block(guide)`/`_glossary_block(db_path)`/
    # `ingest.split_into_scenes()` - ty běží PŘED scénovou smyčkou
    # samotnou, ale POŘÁD PO `begin_chapter()` (co `existing_questions`
    # už smazal) - selhání PŘÍMO tady (rozbitý `guide`/DB glosář čtení)
    # by jinak checkpoint úplně obešlo.
    try:
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
    except (Exception, KeyboardInterrupt):
        # Kolo 24 IMPORTANT (plan-consensus) - `KeyboardInterrupt`
        # (Ctrl+C) NENÍ `Exception` podtřída - holé `except Exception`
        # by přerušení BĚHEM `translate_scene()` přeskočilo, staré
        # otázky by zůstaly ztracené stejně jako bez týhle opravy vůbec.
        for q in existing_questions:
            state.upsert_open_question(db_path, q)
        raise

    cz = "\n\n".join(p for p in parts if p)
    findings = []

    def _checkpoint_flagged(cz_now, findings_now, questions_now, rounds_now, error):
        """Kolo 22 IMPORTANT (plan-consensus) - sdílená pomocná funkce
        (dřív duplikovaná pro pre-loop kritika a revizní smyčku zvlášť,
        kolo 13/18/20/21) - uloží POSLEDNÍ platný `cz_now` jako `flagged`
        PŘED re-raise fatální chyby: mentions se DETERMINISTICKY znovu
        sestaví z `cz_now`/glosáře (žádní noví kandidáti - ty se dají
        dohnat později), otázky jsou SLOUČENÍ `existing_questions`
        (snapshot z ÚVODU funkce, PŘED `begin_chapter()`) A
        `questions_now` (nejistoty z AKTUÁLNÍHO, právě zachráněného
        výsledku - kolo 22 IMPORTANT, ne jen stará data).

        Kolo 25 IMPORTANT (plan-consensus) - `glossary_rows` se FETCHUJE
        ZNOVU tady uvnitř, NE z vnějšího scope - checkpoint teď může
        běžet i PŘED tím, než se venkovní `glossary_rows` stihne vůbec
        nastavit (pokud selže PŘÍMO `glossary.all_terms()` níž, viz
        rozšířený `try` kolem "kontrola" fáze) - closure capture by
        jinak skončila na `NameError` MÍSTO uloženi flagged stavu.
        `rendered` se naopak BEZPEČNĚ čerpá z vnějšího scope - vždy má
        ASPOŇ scénové (neverifikované) hodnoty, i když `_verified_
        rendered()` samo selže (LHS přiřazení v tom případě neproběhne,
        `rendered` si drží svou PŘEDCHOZÍ platnou hodnotu).

        Kolo 26 IMPORTANT (plan-consensus) - když `glossary.all_terms()`
        selže, NEPADAT na `gl_rows=[]` → `build_mentions(..., [], ...)`
        → prázdný rebuild → `commit_chapter_result()` VŽDY smaže
        existující `term_mentions` PŘED vložením (kolo 18) → prázdný
        seznam by je nenávratně smazal. Fallback je místo toho
        `existing_mentions` (snapshot PŘED `begin_chapter()`, stejný
        vzor jako `existing_questions`) - horší než čerstvý rebuild
        (nemusí odrážet TENHLE run), ale nekonečně lepší než `[]`.

        Kolo 26 IMPORTANT (plan-consensus) - `questions_now` (z
        translatoru) NEBYL jediný zdroj otázek v normální transakci B -
        `findings_now` položky s `action=="question"` (z `concordance.
        check_chapter()`, ne z translatoru) se tam TAKY překlápí do
        DB otázek. Bez týhle větve by zachráněný `cz` mohl mít uložený
        minor/candidate nález BEZ odpovídající otázky v `questions`
        tabulce - nekonzistence oproti normálnímu dokončení.

        Kolo 27 IMPORTANT (plan-consensus) - VRACÍ `process_chapter()`-
        tvarovaný výsledek (ne `None`) - pro NEfatální výjimku (viz
        volající `except Exception` klauzule níž) tenhle výsledek
        volající přímo VRÁTÍ místo re-raise, protože holé `raise` by
        po úspěšném uložení `flagged` propagovalo do `_cmd_run` (main.py),
        co by ho svým GENERICKÝM `except Exception: status="error"`
        přepsalo zpátky na `error` - status, co `state.queue_for_run()`
        AUTOMATICKY zkusí znovu při každém dalším `run`u, MÍSTO `flagged`,
        co čeká na explicitní `--retry-flagged` (přesně to, co kolo
        10/11 zavedlo a co by tenhle přehlédnutý re-raise tiše rušilo)."""
        pseudo = {"source": "pipeline", "type": "fluency", "severity": "critical",
                 "action": "note", "term_id": None, "expected": None,
                 "actual": None, "cz_excerpt": None,
                 "issue": f"zpracování přerušeno fatální chybou ({error}) - "
                          "poslední platný překlad zachován",
                 "suggestion": None}
        saved_findings = findings_mod.assign_ids(findings_now + [pseudo])
        try:
            gl_rows = glossary.all_terms(db_path)
            rebuilt_mentions = concordance.build_mentions(en, cz_now, gl_rows, rendered)
            rebuilt_mentions = [{"term_id": m.term_id, "cz_form": m.cz_form,
                                 "scene_idx": m.scene_idx, "source": m.source}
                                for m in rebuilt_mentions]
        except Exception:
            rebuilt_mentions = existing_mentions
        fresh_db_questions = [{"chapter_idx": idx, "kind": q.get("kind") or "other",
                               "scope_key": _scope_key_for(q), "text": q.get("text") or "",
                               "guess_answer": q.get("guess_answer"),
                               "severity": q.get("severity") or "guess"}
                              for q in questions_now]
        fresh_db_questions += [
            {"chapter_idx": idx, "kind": "term",
             "scope_key": _scope_key_for({"scope_key": f.get("term_id"),
                                          "text": f.get("issue")}),
             "text": f.get("issue") or "", "guess_answer": f.get("actual"),
             "severity": "guess"}
            for f in findings_now if f.get("action") == "question"]
        commit_result = state.commit_chapter_result(
            db_path, idx, translated_text=cz_now, revision_rounds=rounds_now,
            notes_json=json.dumps(saved_findings, ensure_ascii=False),
            status="flagged", new_candidates=[], mentions=rebuilt_mentions,
            questions=existing_questions + fresh_db_questions)
        # Kolo 27 IMPORTANT (plan-consensus) - vrací hotový `process_
        # chapter()`-tvarovaný výsledek (viz vysvětlení u volajících
        # `except` klauzulí níž) - volající pro NEfatální výjimku tenhle
        # výsledek přímo VRÁTÍ MÍSTO re-raise, ať `_cmd_run` (main.py)
        # nemá šanci `flagged` status přepsat zpátky na auto-retry-ovaný
        # `error`.
        return {"idx": idx, "status": "flagged", "revision_rounds": rounds_now,
                "new_terms": 0, "questions_created": commit_result["questions_created"],
                "findings": saved_findings}

    # Kolo 25 IMPORTANT (plan-consensus) - `try` rozšířen na CELOU
    # "kontrola" fázi (`_verified_rendered()`/`glossary.all_terms()`/
    # `concordance.check_chapter()`), NE JEN `_run_critic()` volání -
    # tyhle tři jsou sice deterministické (žádné LLM volání), ale POŘÁD
    # mohou selhat (rozbitý `rendered` tvar, DB čtení glosáře) a BEZ
    # rozšíření by `cz` (už hotový, zaplacený scénový překlad) propadlo
    # BEZ checkpointu úplně stejně jako mezery, co kola 20-24 zavřely
    # jinde. `findings = []` PŘED try (výš) zaručuje, že `_checkpoint_
    # flagged()`'s `findings_now` parametr je VŽDY bezpečně bound, i
    # když selže `concordance.check_chapter()` samo (první přiřazení
    # `findings`).
    try:
        rendered = _verified_rendered(rendered, cz)

        # --- kontrola: deterministicky + nezávislý kritik ---
        glossary_rows = glossary.all_terms(db_path)
        findings = concordance.check_chapter(en, cz, glossary_rows, rendered)
        critic_findings, critic_failed = _run_critic(en, cz, client_factory("critic"))
    except (FatalRunError, KeyboardInterrupt) as e:
        # Kolo 22 IMPORTANT (plan-consensus) - viz vysvětlení výš -
        # PRVNÍ `_run_critic()` volání (PŘED revizní smyčkou) nebylo
        # chráněné vůbec.
        # Kolo 24 IMPORTANT (plan-consensus) - `KeyboardInterrupt` (Ctrl+C)
        # NENÍ `Exception` podtřída (je `BaseException`), takže by holé
        # `except FatalRunError` přeskočilo úplně - uživatelovo přerušení
        # BĚHEM čekání na kritika by zahodilo `cz` stejně jako kritikův
        # `FatalRunError`, jen skrz jiný trigger.
        # Kolo 27 IMPORTANT (plan-consensus) - `FatalRunError`/
        # `KeyboardInterrupt` jsou OPRAVDU fatální (kritikův cost guard/
        # auth, uživatelovo přerušení) - checkpoint uloží, PAK re-raise,
        # CELÝ `run` se zastaví (main.py žádnou z nich nezachytí zvlášť,
        # jen obecně - správné chování, beze změny oproti dřívějším
        # kolům).
        _checkpoint_flagged(cz, findings, questions, 0, type(e).__name__)
        raise
    except Exception as e:
        # Kolo 27 IMPORTANT (plan-consensus) - `_verified_rendered()`/
        # `glossary.all_terms()`/`concordance.check_chapter()` NEJSOU
        # LLM volání s vlastní FatalRunError klasifikací jako `_run_
        # critic()` - jejich chyba je OBYČEJNÝ `Exception` (např.
        # `sqlite3.OperationalError`), CO NECHCEME nechat zastavit
        # CELÝ run (na rozdíl od fatální větve výš). Checkpoint uloží
        # `flagged` A rovnou ho VRÁTÍ jako výsledek funkce - HOLÉ
        # `raise` by tu propagovalo do `_cmd_run`'s generického `except
        # Exception: status="error"` (main.py), co by `flagged` status
        # tiše přepsal na `error` (auto-retry PŘI KAŽDÉM dalším `run`u,
        # MÍSTO čekání na explicitní `--retry-flagged`) - přesně to, co
        # kolo 10/11 zavedlo pro Codex-translator selhání a co by tenhle
        # přehlédnutý re-raise pro pipeline-interní selhání tiše rušilo.
        return _checkpoint_flagged(cz, findings, questions, 0, type(e).__name__)
    findings += critic_findings

    # --- revizní smyčka ---
    rounds = 0
    revision_failed = False
    while (has_revise_triggers(findings) and rounds < config.MAX_REVIZE
           and not critic_failed):
        to_fix = [f for f in findings if f.get("action") == "revise"]
        try:
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
            # Kolo 21 IMPORTANT (plan-consensus) - `_run_critic()` je
            # TEĎ UVNITŘ try/except - kritikovo `FatalRunError` (VŽDY
            # Claude, i při --translator codex) se teď taky zachytí a
            # `cz` (i kdyby ho ZROVNA TAHLE `revise_chapter()` úspěšně
            # aktualizovala) se checkpointne stejně jako selhání
            # samotné revize.
            critic_findings, critic_failed = _run_critic(en, cz, client_factory("critic"))
            findings += critic_findings
        except (FatalRunError, KeyboardInterrupt) as e:
            # Kolo 13 IMPORTANT (plan-consensus) - BEZ týhle opravy `cz`
            # (scénový překlad, případně částečně revidovaný) propadne
            # s výjimkou, NIKDY se neuloží - `_cmd_run`'s `flagged`
            # status (kolo 10/11) je pak jen KOSMETICKÝ, skutečný
            # PŘEKLAD zůstává ztracený (commit běží až na konci funkce,
            # `raise`/re-raise ho nikdy nedosáhne).
            #
            # Kolo 22 IMPORTANT (plan-consensus) - stejná checkpoint
            # logika (mentions rebuild z kola 18, otázky z kola 20+22)
            # teď žije v `_checkpoint_flagged()` (definovaná výš, sdílená
            # s pre-loop kritikem) - zabraňuje TŘETÍ kopii stejného kódu.
            #
            # Kolo 24 IMPORTANT (plan-consensus) - `KeyboardInterrupt`
            # (Ctrl+C) NENÍ `Exception` podtřída - holé `except
            # FatalRunError` by ho přeskočilo, uživatelovo přerušení
            # BĚHEM `revise_chapter()`/kritika by zahodilo `cz` stejně
            # jako `FatalRunError`. Re-raise dál propaguje ven z `run`u
            # (main.py žádnou z těchhle výjimek nezachytí - správné,
            # Ctrl+C má CELÝ proces zastavit, checkpoint jen zajistí, že
            # se PŘED tím uloží poslední platný stav).
            _checkpoint_flagged(cz, findings, questions, rounds, type(e).__name__)
            raise
        except Exception as e:
            # Kolo 3 IMPORTANT (plan-consensus) - `revise_chapter()`
            # posílá CELOU kapitolu, a od kola 21 je celá tahle
            # iterace (revize + `_run_critic()` recheck) obalená
            # JEDNÍM try/except - bez týhle záchrany by výjimka
            # (useknutý/rozbitý výstup, ValueError z translator._
            # parse(), i kritikova nefatální chyba) propadla z
            # process_chapter() a zahodila i JIŽ HOTOVÝ scénový
            # překlad (commit běží až na konci funkce). Mirror
            # `_run_critic()`'s VLASTNÍHO vzoru (FatalRunError
            # propaguje, run se zastaví; jinak necháváme poslední
            # PLATNÝ `cz`, kapitola skončí flagged, ne error).
            revision_failed = type(e).__name__
            break
        rounds += 1

    if revision_failed:
        findings.append({"source": "pipeline", "type": "fluency", "severity": "critical",
                         "action": "note", "term_id": None, "expected": None,
                         "actual": None, "cz_excerpt": None,
                         "issue": f"revize selhala ({revision_failed}) - poslední "
                                  "platný překlad zachován, nálezy níž do něj "
                                  "nebyly zapracované", "suggestion": None})

    try:
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
        elif critic_failed or revision_failed or has_revise_triggers(findings):
            status = "flagged"
        else:
            status = "done"

        findings = findings_mod.assign_ids(findings)

        result = state.commit_chapter_result(
            db_path, idx, translated_text=cz, revision_rounds=rounds,
            notes_json=json.dumps(findings, ensure_ascii=False), status=status,
            new_candidates=new_candidates, mentions=mentions, questions=db_questions)
    except (FatalRunError, KeyboardInterrupt) as e:
        # Kolo 25 IMPORTANT (plan-consensus) - viz vysvětlení výš -
        # poslední nechráněné místo v `process_chapter()`. `cz` je tu
        # už FINÁLNÍ (po revizní smyčce) - bez checkpointu by selhání
        # PŘÍMO v přípravě transakce B (DB čtení glosáře, konkordanční
        # výpočet) zahodilo i tenhle, už hotový výsledek.
        # Kolo 27 IMPORTANT (plan-consensus) - v týhle fázi žádné LLM
        # volání neběží (`FatalRunError` je tu tedy nepravděpodobný), ale
        # `KeyboardInterrupt` (Ctrl+C) může přijít kdykoli - checkpoint
        # uloží, PAK re-raise, run se zastaví (konzistentní s ostatními
        # dvěma checkpoint místy).
        _checkpoint_flagged(cz, findings, questions, rounds, type(e).__name__)
        raise
    except Exception as e:
        # Kolo 27 IMPORTANT (plan-consensus) - OBYČEJNÝ `Exception` (DB
        # chyba, neočekávaný tvar dat) NESMÍ zastavit CELÝ run - checkpoint
        # uloží `flagged` A rovnou ho VRÁTÍ jako výsledek funkce. Holé
        # `raise` by tu propagovalo do `_cmd_run`'s generického `except
        # Exception: status="error"` (main.py), co by `flagged` (needs-
        # human, čeká na `--retry-flagged`) tiše přepsal na `error`
        # (auto-retry PŘI KAŽDÉM dalším `run`u) - RUŠÍ smysl checkpointu.
        return _checkpoint_flagged(cz, findings, questions, rounds, type(e).__name__)

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
