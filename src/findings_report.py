"""Agregovaný report nálezů napříč VŠEMI kapitolami, čtený z `chapters.
notes` (JEDINÝ zdroj - viz `build_findings_report` docstring, proč se
NEslučuje s `polish.history.json`). Dva výstupy ze STEJNÉHO
`build_findings_report`: HTML k vytištění a prostý txt vedle exportu
knihy. Viz spec 2026-09-14, sekce "Report nálezů"."""
import html as _html

from src import findings, state


def build_findings_report(db_path: str) -> list:
    """`chapters.notes` je JEDINÝ zdroj - `_commit_polish_result`
    (main.py Task 5) zapisuje do `notes` PŘESNĚ to, co zároveň připojí
    do `polish.history.json`.

    DÁVKA (`_cmd_polish`/Task 5) `notes` PŘEPISUJE - `_commit_polish_
    result` samo NEMERGUJE, jen uloží, co dostane (`rec["findings"]` z
    čerstvé `_polish_one_chapter` analýzy + marker); volající v Tasku 5
    žádný merge nedělá. Běžný běh (dávka jede JAKO PRVNÍ krok, hned po
    `run`u, PŘED jakoukoli ruční úpravou) tak `run`-fáze nálezy nahradí
    ČERSTVĚJŠÍMI (koncordance/kritik spočítané znovu proti NOVĚ
    stylizovanému textu, relevantnější než nálezy o textu, co už
    neexistuje) - to je ZÁMĚRNÉ, ne ztráta dat (kolo 6 NIT, oprava - dřív
    tenhle docstring mylně tvrdil, že AKUMULACE platí i pro dávku).

    EDITOR (`POST /api/chapter/{idx}/save`, Task 9) naopak `notes`
    AKUMULUJE, ne přepisuje - VOLAJÍCÍ (endpoint, ne `_commit_polish_
    result` samo) sloučí nové nálezy s `_merge_findings_by_id` PŘED
    voláním `_commit_polish_result`, ať žádná ruční úprava neztratí
    nález, co tam mezitím přidala jiná karta/regenerace. Report proto
    typicky ukazuje ROSTOUCÍ seznam PO PRVNÍ ruční úpravě kapitoly, ne
    hned po dávce - zaškrtávátko `resolved` je způsob, jak nález
    "uklidit" z pohledu, ne mazání ze storage.

    Slučování s posledním historie záznamem by KAŽDÝ nález zdvojilo
    (stejná data, stejná `id`, ze STEJNÉHO zápisu) - viz Task 5
    `_commit_polish_result` docstring."""
    from main import _parse_findings   # lazy - main importuje spoustu modulů, ne naopak
    chapters = state.chapters_by_status(
        db_path, ("pending", "processing", "done", "flagged", "needs_human", "error"))
    out = []
    for ch in sorted(chapters, key=lambda c: c["idx"]):
        notes_findings = [f for f in _parse_findings(ch["notes"])
                          if not findings.is_marker(f)]
        if notes_findings:
            out.append({"idx": ch["idx"], "title": ch["title"], "findings": notes_findings})
    return out


def render_findings_html(report: list) -> str:
    parts = ["<!DOCTYPE html><html lang=\"cs\"><head><meta charset=\"utf-8\">"
            "<title>Report nálezů</title><style>"
            "body{font-family:system-ui,sans-serif;margin:2rem;color:#1a1a1a}"
            "h2{border-bottom:1px solid #ccc;padding-bottom:.3rem}"
            "li{margin-bottom:.4rem}.resolved{color:#888;text-decoration:line-through}"
            "</style></head><body><h1>Report nálezů</h1>"]
    if not report:
        parts.append("<p>Žádné nálezy.</p>")
    for ch in report:
        parts.append(f"<h2>#{_html.escape(str(ch['idx']))} - "
                     f"{_html.escape(ch['title'])}</h2><ul>")
        for f in ch["findings"]:
            cls = " class=\"resolved\"" if f.get("resolved") else ""
            # `str(...)` PŘED `_html.escape` (kolo 4 IMPORTANT) - producenti
            # nálezů (kritik/concordance) nejsou validovaní jako klientský
            # save vstup, `issue`/`severity` NEMUSÍ být `str` (`html.escape`
            # na non-str spadne na `TypeError`).
            sev = _html.escape(str(f.get("severity") or "?"))
            issue = _html.escape(str(f.get("issue") or "(bez popisu)"))
            parts.append(f"<li{cls}>[{sev}] {issue}</li>")
        parts.append("</ul>")
    parts.append("</body></html>")
    return "".join(parts)


def render_findings_txt(report: list) -> str:
    lines = ["REPORT NÁLEZŮ", ""]
    if not report:
        lines.append("Žádné nálezy.")
    for ch in report:
        lines.append(f"# {ch['idx']} - {ch['title']}")
        for f in ch["findings"]:
            mark = "[VYŘEŠENO] " if f.get("resolved") else ""
            lines.append(f"  {mark}[{f.get('severity') or '?'}] "
                         f"{f.get('issue') or '(bez popisu)'}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
