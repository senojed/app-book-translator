"""CLI překladače knih. Tenká vrstva: rozparsuj argumenty, zavolej modul, vypiš.

Fáze běhu:
    init kniha.epub    kniha → kapitoly do DB
    scan [--chunked]   scout projede knihu → guide.draft.json
    review             web UI: potvrdíš návod → guide.json (+ reseed glosáře)
    run [--retry-flagged [IDX...]]   překladová smyčka
    questions / answer QID "text"    dávkové otázky
    status / export [--only-done]

Mutující příkazy drží zámek v data/ - druhý běh se nespustí a nerozbije stav.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from src import concordance, glossary
from src import guide as guide_mod
from src import ingest, pipeline, requeue, state
from src import reference as reference_mod
from src import reference_mine, textnorm
from src.agents import scout
from src.llm.client import AnthropicClient, FatalRunError, OutputTruncated, PipelineLLMClient

_MUTATING = {"init", "scan", "run", "answer", "review", "reference"}

_MARKERS = {"done": "OK", "pending": "..", "flagged": "!!", "needs_human": "??",
            "error": "XX", "processing": "~~"}


def _bootstrap_stdout() -> None:
    """Windows konzole je často cp1252 a český výstup by ji shodil."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _client_factory(run_id: int, *, interactive: bool):
    """Klienta staví až při volání - `run` s fake pipeline nikdy nesáhne na API."""
    def factory(agent: str):
        return PipelineLLMClient(AnthropicClient(), run_id=run_id, agent=agent,
                                 db_path=config.DB_PATH, config_mod=config,
                                 interactive=interactive)
    return factory


def _print_usage(db_path: str, run_id: int) -> None:
    with state.connect(db_path) as conn:
        r = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(input_tokens),0) it, "
            "COALESCE(SUM(output_tokens),0) ot, COALESCE(SUM(cost_usd),0) c "
            "FROM llm_calls WHERE run_id = ?", (run_id,)).fetchone()
    print(f"LLM volání: {r['n']}, vstup {r['it']} tok, výstup {r['ot']} tok, "
          f"cena ~${r['c']:.4f}")


# --- příkazy ----------------------------------------------------------------

def _cmd_init(args) -> int:
    db = config.DB_PATH
    if not state.is_db_empty(db) and not args.reset:
        print("DB už obsahuje knihu. Použij `init --reset` pro nahrazení.")
        return 1
    if args.reset:
        state.reset_book(db)
    chapters = ingest.load_book(args.path)
    state.seed_chapters(db, chapters)
    print(f"Načteno kapitol: {len(chapters)}")
    return 0


def _cmd_scan(args) -> int:
    db = config.DB_PATH
    state.recover_processing(db)
    rid = state.create_run(db, "scan")
    status = "fatal"
    try:
        chs = state.chapters_by_status(
            db, ("pending", "processing", "done", "flagged", "needs_human", "error"))
        if not chs:
            raise FatalRunError("Žádné kapitoly - nejdřív `init`.")
        # scan je neinteraktivní: jedno velké volání, cost guard tvrdě zastaví
        cf = _client_factory(rid, interactive=False)
        try:
            if args.chunked:
                chunks = scout.chunk_chapters(chs, config.SCOUT_CHUNK_WORD_LIMIT)
                result = scout.scan_chunks(chunks, cf("scout"))
            else:
                text = "\n\n".join(c["raw_text"] for c in chs)
                result = scout.scan_book(text, cf("scout"))
        except (OutputTruncated, ValueError) as e:
            raw = getattr(e, "raw", "")
            if raw:
                # Bez surového výstupu je další pokus slepý; do gitu se nedostane.
                dump = os.path.join(config.DATA_DIR, "scout_raw_last.txt")
                with open(dump, "w", encoding="utf-8") as f:
                    f.write(raw)
                print(f"Surový výstup scouta uložen: {dump}")
            raise FatalRunError(
                f"Scout výstup je neúplný/rozbitý ({e}). Zkus `scan --chunked` "
                "nebo zvyš MAX_TOKENS_SCOUT v config.py.")
        guide_mod.save_draft(config.GUIDE_DRAFT_PATH, result)
        print(f"Draft návodu uložen: {config.GUIDE_DRAFT_PATH}")
        print("Dál: `python main.py review`")
        status = "ok"
        return 0
    except FatalRunError as e:
        print(e)
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        state.finish_run(db, rid, status)


def _cmd_reference(args) -> int:
    db = config.DB_PATH
    root = args.dir or config.REFERENCE_DIR
    rid = state.create_run(db, "reference")
    status = "fatal"
    try:
        if not root:
            raise FatalRunError("Chybí cesta k referencím - použij `--dir CESTA` "
                                "nebo nastav REFERENCE_DIR v config.py.")
        if not os.path.exists(config.GUIDE_DRAFT_PATH):
            raise FatalRunError(
                f"Chybí {config.GUIDE_DRAFT_PATH} - nejdřív spusť `scan`.")
        try:
            draft = guide_mod.load_draft(config.GUIDE_DRAFT_PATH)
        except (OSError, ValueError) as e:
            raise FatalRunError(
                f"{config.GUIDE_DRAFT_PATH} se nepodařilo načíst ({type(e).__name__}: {e}).")

        corpus = None if args.refresh_cache else reference_mod.load_cache(
            config.REFERENCE_CACHE_PATH, root)
        if corpus is None:
            print("Načítám referenční korpus (~30 s)...")
            try:
                corpus = reference_mod.load_corpus(root)
            except ValueError as e:
                raise FatalRunError(str(e))
            except OSError as e:
                raise FatalRunError(f"Referenční korpus se nepodařilo načíst: {e}")
            try:
                reference_mod.save_cache(corpus, config.REFERENCE_CACHE_PATH)
            except OSError as e:
                # Cache je jen zrychlení příštího běhu - selhání zápisu
                # nesmí shodit těžbu, která už proběhla.
                print(f"reference: cache se nepodařilo uložit ({e}), pokračuji bez ní")

        items = []
        for section, key in (("characters", "name_en"), ("places", "name_en"),
                             ("terms", "term_en")):
            for it in draft.get(section) or []:
                surface = (it.get(key) or "").strip()
                if not surface:
                    continue
                items.append({"id": f"{section}/{textnorm.normalize_key(surface)}",
                              "section": section, "surface": surface,
                              "aliases": list(it.get("aliases") or []),
                              "note": it.get("note") or ""})

        cf = _client_factory(rid, interactive=False)
        try:
            # resolve() i write_reference() jsou v JEDNOM try/except: selže-li
            # cokoli mezi voláním modelu a dokončením zápisu (i samotný zápis,
            # např. disk plný), jde o stejnou situaci - těžba neproběhla a
            # předchozí reference.json (write_reference ho nahrazuje jen na
            # úplný konec přes os.replace) zůstává nedotčený.
            findings = reference_mine.resolve(corpus, items, cf, config)
            # manifest_fingerprint(corpus.manifest), NE corpus_fingerprint(root) -
            # to druhé by po těžbě (může trvat minuty kvůli modelu) přečetlo
            # AKTUÁLNÍ stav disku, ne ten, ze kterého nálezy skutečně vzešly.
            fingerprint = {
                "draft": reference_mine.draft_fingerprint(draft),
                "corpus": reference_mine.manifest_fingerprint(corpus.manifest),
                "thresholds": reference_mine.thresholds_fingerprint(config)}
            reference_mine.write_reference(findings, config.REFERENCE_PATH, rid,
                                           fingerprint, corpus.source_root)
        except FatalRunError:
            raise
        except Exception as e:
            raise FatalRunError(
                f"Těžba selhala ({type(e).__name__}: {e}). Předchozí "
                f"{config.REFERENCE_PATH} zůstal beze změny, spusť znovu.")

        counts = {}
        for f in findings:
            counts[f["classification"]] = counts.get(f["classification"], 0) + 1
        print(f"Vytěženo do {config.REFERENCE_PATH}:")
        for name in ("confirmed", "weak", "evidence_only", "proposed",
                     "not_attested", "unresolved"):
            print(f"   {name:<15} {counts.get(name, 0)}")
        _print_usage(db, rid)
        print("Dál: `python main.py review`")
        status = "ok"
        return 0
    except FatalRunError as e:
        print(e)
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        state.finish_run(db, rid, status)


def _cmd_review(args) -> int:
    from src import glossary
    from src.review_ui import server
    rc = server.run_review_server(config.GUIDE_DRAFT_PATH, config.GUIDE_PATH,
                                  reference_path=config.REFERENCE_PATH)
    if rc != 0:
        print("Návod nebyl uložen - glosář zůstává beze změny.")
        return rc
    # Reseed dělá CLI, ne UI - UI o DB nic neví (izolace modulů).
    conflicts = glossary.seed_from_guide(config.DB_PATH,
                                         guide_mod.load_guide(config.GUIDE_PATH))
    for c in conflicts:
        print(f"KONFLIKT: {c['incoming']!r} je alias položky "
              f"{c['existing_canonical']!r} - nic jsem nepřepsal, rozhodni ručně.")
    print("Návod uložen, glosář naseedován. Dál: `python main.py run`")
    return 0


def _cmd_run(args) -> int:
    db = config.DB_PATH
    state.recover_processing(db)
    if args.retry_flagged is not None:
        n = state.retry_flagged(db, args.retry_flagged or None)
        print(f"Vráceno do fronty (flagged → pending): {n}")
    rid = state.create_run(db, "run")
    status = "fatal"
    try:
        g = guide_mod.load_guide(config.GUIDE_PATH)
        cf = _client_factory(rid, interactive=True)
        queue = state.queue_for_run(db)
        if args.only:
            # Pilot: přelož jen vyjmenované kapitoly, zbytek nech ve frontě.
            wanted = set(args.only)
            queue = [c for c in queue if c["idx"] in wanted]
            chybi = sorted(wanted - {c["idx"] for c in queue})
            if chybi:
                print("Přeskočeno (nejsou ve frontě - už hotové, flagged nebo "
                      "needs_human): " + ", ".join(str(i) for i in chybi))
        for ch in queue:
            try:
                summary = pipeline.process_chapter(db, ch, client_factory=cf, guide=g)
            except FatalRunError:
                raise                      # celý běh končí, kapitola zůstane rozpracovaná
            except Exception as e:         # OutputTruncated i ValueError sem patří
                state.update_chapter(db, ch["idx"], status="error",
                                     notes=json.dumps(
                                         {"error": f"{type(e).__name__}: {e}"},
                                         ensure_ascii=False))
                print(f"Kapitola {ch['idx']}: chyba ({type(e).__name__}), pokračuji.")
                continue
            print(f"Kapitola {summary['idx']}: {summary['status']} "
                  f"(revizí: {summary.get('revision_rounds', 0)})")
            if summary["status"] in ("done", "flagged"):
                counts = state.counts_by_status(db)
                n = counts.get("done", 0) + counts.get("flagged", 0)
                if n > 0 and n % config.CROSS_REF_EVERY_N == 0:
                    drifts = pipeline.run_drift_check(db, ch["idx"])
                    if drifts:
                        print(f"Drift check: {len(drifts)} termínů s rozjetými tvary "
                              "→ nové otázky.")
        _report(db)
        _print_usage(db, rid)
        status = "ok"
        return 0
    except FatalRunError as e:
        print(f"Fatální chyba běhu: {e}")
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        state.finish_run(db, rid, status)


def _report(db: str) -> None:
    counts = state.counts_by_status(db)
    parts = [f"{k}: {v}" for k, v in sorted(counts.items())]
    print("Stav kapitol - " + ", ".join(parts) if parts else "Žádné kapitoly.")
    open_q = state.unanswered_questions(db)
    if open_q:
        print(f"Nezodpovězených otázek: {len(open_q)} (`python main.py questions`)")


def _cmd_status(args) -> int:
    db = config.DB_PATH
    _report(db)
    for ch in state.chapters_by_status(
            db, ("pending", "processing", "done", "flagged", "needs_human", "error")):
        mark = _MARKERS.get(ch["status"], "??")
        print(f"  [{mark}] {ch['idx']:>3}  {ch['title']}")
    return 0


def _cmd_questions(args) -> int:
    rows = state.unanswered_questions(config.DB_PATH)
    if not rows:
        print("Žádné otevřené otázky.")
        return 0
    for q in rows:
        scope = f"kapitola {q['chapter_idx']}" if q["chapter_idx"] is not None else "globální"
        guess = f" (odhad: {q['guess_answer']})" if q["guess_answer"] else ""
        print(f"#{q['id']} [{q['severity']}] {q['kind']} / {scope}{guess}\n"
              f"    {q['text']}")
    print("\nOdpověz: python main.py answer <ID> \"text\"  "
          "(víc tvarů odděl svislítkem: \"Rada | Radě\")")
    return 0


def _cmd_answer(args) -> int:
    try:
        out = requeue.apply_answer(config.DB_PATH, config.GUIDE_PATH,
                                   args.qid, args.text)
    except ValueError as e:
        print(e)
        return 1
    if out["requeued"]:
        print("Přepočítat kapitoly: " +
              ", ".join(str(i) for i in out["requeued"]) + " (spusť `run`)")
    elif out["chapter_status_changed"]:
        print("Kapitola uvolněna k překladu (spusť `run`).")
    else:
        print("Zapsáno. Žádná kapitola se přepočítávat nemusí.")
    return 0


def _finding_summary(notes: str) -> str:
    try:
        data = json.loads(notes or "[]")
    except (ValueError, TypeError):
        return "neznámý nález"
    if isinstance(data, dict):
        return str(data.get("error") or "neznámý nález")
    for f in data:
        if f.get("issue"):
            return f["issue"]
    return "neznámý nález"


def _cmd_export(args) -> int:
    db = config.DB_PATH
    chapters = state.chapters_by_status(
        db, ("pending", "processing", "done", "flagged", "needs_human", "error"))
    out_lines, skipped = [], []
    for ch in chapters:
        idx, st = ch["idx"], ch["status"]
        if st == "done":
            out_lines.append(f"\n\n{ch['title']}\n\n{ch['translated_text'] or ''}")
        elif st == "flagged" and not args.only_done:
            out_lines.append(
                f"\n\n[!! REVIDOVAT: {_finding_summary(ch['notes'])}]\n"
                f"{ch['title']}\n\n{ch['translated_text'] or ''}")
        elif st == "flagged":
            skipped.append(idx)
        else:
            skipped.append(idx)
            if not args.only_done:
                # Kniha nesmí tiše přijít o kapitolu.
                out_lines.append(f"\n\n[!! CHYBÍ KAPITOLA {idx} - stav {st}]")
    os.makedirs(os.path.dirname(config.OUTPUT_TXT) or ".", exist_ok=True)
    with open(config.OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines).strip() + "\n")
    print(f"Export: {config.OUTPUT_TXT}")
    if skipped:
        print("Vynechané kapitoly: " + ", ".join(str(i) for i in skipped))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="book-translator",
                                description="Multiagentní překladač knih EN→CZ")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="načti knihu do DB")
    p_init.add_argument("path")
    p_init.add_argument("--reset", action="store_true",
                        help="smaž dosavadní stav knihy a nahraď novou")
    p_init.set_defaults(func=_cmd_init)

    p_scan = sub.add_parser("scan", help="scout → guide.draft.json")
    p_scan.add_argument("--chunked", action="store_true",
                        help="po částech, když se kniha nevejde do kontextu")
    p_scan.set_defaults(func=_cmd_scan)

    p_ref = sub.add_parser("reference", help="vytěž terminologii z profesionálních překladů")
    p_ref.add_argument("--dir", default=None, help="kořen se složkami EN/ a CZ/")
    p_ref.add_argument("--refresh-cache", action="store_true", dest="refresh_cache",
                       help="postav korpus znovu bez ohledu na cache")
    p_ref.set_defaults(func=_cmd_reference)

    sub.add_parser("review", help="web UI: potvrď návod → guide.json"
                   ).set_defaults(func=_cmd_review)

    p_run = sub.add_parser("run", help="překladová smyčka")
    p_run.add_argument("--retry-flagged", nargs="*", type=int, default=None,
                       dest="retry_flagged",
                       help="vrať flagged kapitoly do fronty (bez IDX = všechny)")
    p_run.add_argument("--only", nargs="+", type=int, default=None,
                       help="přelož jen tyhle kapitoly (pilot); zbytek zůstane ve frontě")
    p_run.set_defaults(func=_cmd_run)

    sub.add_parser("status", help="přehled kapitol").set_defaults(func=_cmd_status)
    sub.add_parser("questions", help="otevřené otázky").set_defaults(func=_cmd_questions)

    p_ans = sub.add_parser("answer", help="odpověz na otázku")
    p_ans.add_argument("qid", type=int)
    p_ans.add_argument("text")
    p_ans.set_defaults(func=_cmd_answer)

    p_exp = sub.add_parser("export", help="hotové kapitoly do TXT")
    p_exp.add_argument("--only-done", action="store_true", dest="only_done",
                       help="jen čisté kapitoly, bez flagged")
    p_exp.set_defaults(func=_cmd_export)

    return p


def main(argv=None) -> int:
    _bootstrap_stdout()
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    state.init_db(config.DB_PATH)

    args = _build_parser().parse_args(argv)
    if args.cmd in _MUTATING:
        try:
            with state.run_lock(config.LOCK_PATH):
                return args.func(args)
        except state.LockError as e:
            print(e)
            return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
