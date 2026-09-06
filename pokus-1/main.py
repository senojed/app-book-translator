#!/usr/bin/env python3
"""
CLI pro multi-agentní překlad knihy.

Použití:
  python main.py init KNIHA.epub          - načte knihu, rozdělí na kapitoly, uloží do DB
  python main.py calibrate                 - zpracuje prvních N kapitol (fáze 0), nastaví pauzu na otázky
  python main.py questions                 - vypíše nezodpovězené otázky
  python main.py answer ID "odpověď"        - zodpoví otázku, zapíše pravidlo do style guide
  python main.py run                        - plný běh přes zbylé kapitoly (fáze 1)
  python main.py status                     - přehled stavu všech kapitol
  python main.py export                     - vyexportuje hotové kapitoly do output/kniha_cz.txt
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from src import state_db, ingest, orchestrator, llm_client, glossary as gl


def cmd_init(args):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    state_db.init_db(config.DB_PATH)
    chapters = ingest.load_book(args.book_path)
    state_db.seed_chapters(config.DB_PATH, chapters)
    print(f"Načteno {len(chapters)} kapitol z {args.book_path}.")
    if len(chapters) == 1:
        print("POZOR: segmentace na kapitoly zřejmě selhala (vrátila se jen 1 kapitola).")
        print("Zkontroluj formát zdrojového souboru - viz src/ingest.py, CHAPTER_HEADING_RE.")


def cmd_calibrate(args):
    with state_db.connect(config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT * FROM chapters WHERE status = 'pending' ORDER BY idx LIMIT ?",
            (config.CALIBRATION_CHAPTERS,),
        ).fetchall()
    if not rows:
        print("Žádné kapitoly ke kalibraci (buď hotovo, nebo nejsou načtené - spusť nejdřív 'init').")
        return
    for row in rows:
        chapter = dict(row)
        print(f"Zpracovávám kapitolu {chapter['idx']}: {chapter['title']}...")
        summary = _process_one(chapter, is_calibration=True)
        if summary is None:
            continue
        print(f"  status={summary['status']} nové termíny={summary['new_terms_count']} "
              f"otevřené otázky={len(summary['open_questions'])} "
              f"kritické nálezy={summary['critical_findings_count']}")

    _print_usage()
    unanswered = state_db.get_unanswered_questions(config.DB_PATH)
    if unanswered:
        print(f"\n{len(unanswered)} otevřených otázek čeká na tvou odpověď:")
        for q in unanswered:
            print(f"  [{q['id']}] (kapitola {q['chapter_idx']}) {q['question']}")
        print("\nOdpověz příkazem: python main.py answer ID \"tvoje odpověď\"")
    else:
        print("\nŽádné otevřené otázky. Kalibrace hotová, můžeš spustit 'run'.")


def cmd_questions(args):
    unanswered = state_db.get_unanswered_questions(config.DB_PATH)
    if not unanswered:
        print("Žádné nezodpovězené otázky.")
        return
    for q in unanswered:
        print(f"[{q['id']}] (kapitola {q['chapter_idx']}) {q['question']}")


def cmd_answer(args):
    chapter_idx = state_db.answer_question(config.DB_PATH, args.question_id, args.answer)
    # odpověď se rovnou zapíše jako pravidlo do style guide, aby ji translator
    # četl u dalších kapitol
    gl.add_style_rule(config.STYLE_GUIDE_PATH, args.answer)
    print(f"Otázka {args.question_id} zodpovězena a zapsána do style guide.")

    # Kapitola, která kvůli téhle otázce uvízla v 'needs_human', se sama nikam
    # nepohne. Až jsou zodpovězené VŠECHNY její otázky, vrátíme ji do fronty -
    # 'calibrate' nebo 'run' ji přeloží znovu, teď už s doplněným pravidlem.
    if chapter_idx is not None and not state_db.chapter_has_unanswered_questions(config.DB_PATH, chapter_idx):
        if state_db.requeue_chapter(config.DB_PATH, chapter_idx):
            print(f"Kapitola {chapter_idx} má zodpovězené všechny otázky - "
                  "vrácena k přepracování (spusť 'calibrate' nebo 'run').")


def cmd_run(args):
    pending = state_db.get_pending_chapters(config.DB_PATH)
    if not pending:
        print("Žádné čekající kapitoly.")
        return
    for i, chapter in enumerate(pending, start=1):
        print(f"[{i}/{len(pending)}] Kapitola {chapter['idx']}: {chapter['title']}...")
        summary = _process_one(chapter, is_calibration=False)
        if summary is None:
            continue
        print(f"  status={summary['status']} nové termíny={summary['new_terms_count']} "
              f"kritické nálezy={summary['critical_findings_count']} "
              f"terminologické nesrovnalosti={summary['terminology_issues_count']}")
        if summary["status"] == "critic_flagged":
            print(f"  -> kapitola {chapter['idx']} označena k revizi, viz 'status' pro detail.")

        if chapter["idx"] % config.CROSS_REF_EVERY_N_CHAPTERS == 0:
            print(f"  Spouštím cross-reference kontrolu (do kapitoly {chapter['idx']})...")
            report = orchestrator.run_cross_reference(config.DB_PATH, chapter["idx"])
            if report and report.get("drift_found"):
                print(f"  POZOR: nalezen drift v {len(report['drift_found'])} termínech.")

    _print_usage()


def _process_one(chapter: dict, is_calibration: bool):
    """Zpracuje jednu kapitolu. Když to spadne (API chyba, useknutý výstup,
    rozbitá odpověď), kapitolu označí 'error' a vrátí None - běh pokračuje
    dalšími kapitolami místo pádu celého procesu. 'run' pak chyby zkusí znovu."""
    try:
        return orchestrator.process_chapter(config.DB_PATH, chapter, is_calibration=is_calibration)
    except Exception as e:
        state_db.update_chapter(
            config.DB_PATH,
            chapter["idx"],
            status="error",
            critic_notes=json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False),
        )
        print(f"  CHYBA u kapitoly {chapter['idx']}: {type(e).__name__}: {e}")
        print("  -> přeskakuji, kapitola označena 'error'. Oprav příčinu a spusť příkaz znovu.")
        return None


def _print_usage():
    u = llm_client.get_usage()
    if u["calls"]:
        print(f"\nSpotřeba API (tento běh): {u['calls']} volání, "
              f"vstup {u['input_tokens']:,} tok., výstup {u['output_tokens']:,} tok.")


def cmd_status(args):
    with state_db.connect(config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT idx, title, status FROM chapters ORDER BY idx"
        ).fetchall()
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        marker = {"done": "OK", "pending": "..", "critic_flagged": "!!",
                  "needs_human": "??", "error": "XX"}.get(r["status"], "?")
        print(f"  [{marker}] {r['idx']:>3}  {r['title'][:60]:60}  {r['status']}")
    print("\nSouhrn:", counts)


def cmd_export(args):
    with state_db.connect(config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT idx, title, translated_text FROM chapters WHERE status = 'done' ORDER BY idx"
        ).fetchall()
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(config.OUTPUT_DIR, "kniha_cz.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(f"\n\n{r['title']}\n\n")
            f.write(r["translated_text"])
    print(f"Exportováno {len(rows)} hotových kapitol do {out_path}.")


def main():
    parser = argparse.ArgumentParser(description="Multi-agentní překladač knih")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Načte knihu a rozdělí na kapitoly")
    p_init.add_argument("book_path")
    p_init.set_defaults(func=cmd_init)

    p_cal = sub.add_parser("calibrate", help="Fáze 0 - zpracuje prvních pár kapitol")
    p_cal.set_defaults(func=cmd_calibrate)

    p_q = sub.add_parser("questions", help="Vypíše nezodpovězené otázky")
    p_q.set_defaults(func=cmd_questions)

    p_a = sub.add_parser("answer", help="Zodpoví otázku")
    p_a.add_argument("question_id", type=int)
    p_a.add_argument("answer")
    p_a.set_defaults(func=cmd_answer)

    p_run = sub.add_parser("run", help="Fáze 1 - plný běh")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Přehled stavu kapitol")
    p_status.set_defaults(func=cmd_status)

    p_export = sub.add_parser("export", help="Export hotových kapitol do TXT")
    p_export.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
