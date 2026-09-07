"""Lokální web UI pro potvrzení překladatelského návodu.

Izolované od jádra: sahá jen na `guide.*.json` přes `guide.py`. Pipeline, agenty
ani DB nezná. Reseed glosáře po uložení dělá CLI, ne tenhle modul.

Protokol s CLI je exit kód: uložení → server se sám ukončí a vrátí 0; zavření
okna nebo Ctrl-C bez uložení → nenulový kód a CLI nic nereseeduje.
"""
import os
import threading
import webbrowser

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src import guide as guide_mod

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

_ADDRESSES = ("tyka", "vyka")
_RENDERS = ("keep", "translate")


def _upsert(items: list, key_field: str, key_value: str, updates: dict) -> None:
    """Zápis do sekce podle klíče - nikdy nevyrobí duplicitní řádek."""
    for item in items:
        if (item.get(key_field) or "").strip().lower() == (key_value or "").strip().lower():
            item.update(updates)
            return
    row = {key_field: key_value}
    row.update(updates)
    items.append(row)


def apply_must_decide(payload: dict) -> dict:
    """Odpovědi na must_decide zapíše do finálních sekcí a must_decide zahodí.
    Díky tomu je pak validuje stejná kontrola jako všechno ostatní."""
    payload = dict(payload)
    for section in ("characters", "places", "terms", "relationships", "rules"):
        payload.setdefault(section, [])
    for md in payload.get("must_decide", []) or []:
        answer = (md.get("answer") or "").strip()
        if not answer:
            continue
        kind = md.get("kind")
        scope = md.get("scope_key") or ""
        if kind == "term":
            _upsert(payload["terms"], "term_en", scope, {"cz": answer})
        elif kind == "place":
            _upsert(payload["places"], "name_en", scope, {"cz": answer})
        elif kind == "name":
            _upsert(payload["characters"], "name_en", scope,
                    {"render": "translate" if answer != scope else "keep",
                     "cz": answer})
        elif kind == "relationship":
            a, _, b = scope.partition("|")
            for r in payload["relationships"]:
                if guide_mod.relationship_key(r.get("a", ""), r.get("b", "")) == scope:
                    r["address"] = answer
                    break
            else:
                payload["relationships"].append({"a": a, "b": b, "address": answer})
        else:   # style / other
            if answer not in payload["rules"]:
                payload["rules"].append(answer)
    payload["must_decide"] = []
    return payload


def validate(payload: dict) -> list:
    """Vrací seznam chyb. Prázdný seznam = návod je uložitelný."""
    errs = []
    for c in payload.get("characters", []) or []:
        name = (c.get("name_en") or "").strip()
        if not name:
            errs.append("Postava bez jména (name_en).")
            continue
        if c.get("render") not in _RENDERS:
            errs.append(f"Postava {name}: render musí být keep/translate.")
        elif c.get("render") == "translate" and not (c.get("cz") or "").strip():
            errs.append(f"Postava {name}: 'přeložit' bez českého tvaru.")
    for section, key in (("places", "name_en"), ("terms", "term_en")):
        for item in payload.get(section, []) or []:
            name = (item.get(key) or "").strip()
            if not name:
                errs.append(f"Položka v sekci {section} bez {key}.")
                continue
            if not (item.get("cz") or "").strip():
                errs.append(f"{name}: chybí český překlad.")
    for r in payload.get("relationships", []) or []:
        if not (r.get("a") or "").strip() or not (r.get("b") or "").strip():
            errs.append("Vztah bez obou jmen.")
            continue
        if r.get("address") not in _ADDRESSES:
            errs.append(f"Vztah {r['a']} ↔ {r['b']}: oslovení musí být tyka/vyka.")
    for md in payload.get("must_decide", []) or []:
        if (md.get("question") or "").strip() and not (md.get("answer") or "").strip():
            errs.append(f"Nezodpovězená otázka: {md['question']}")
    return errs


def _check_must_decide_answered(payload: dict) -> list:
    return [f"Nezodpovězená otázka: {md.get('question')}"
            for md in (payload.get("must_decide") or [])
            if not (md.get("answer") or "").strip()]


def build_app(draft_path: str, guide_path: str, on_saved) -> FastAPI:
    app = FastAPI(title="Book translator - review návodu")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_STATIC, "index.html"))

    @app.get("/api/guide")
    def get_guide():
        return guide_mod.merge_draft_and_guide(guide_mod.load_draft(draft_path),
                                               guide_mod.load_guide(guide_path))

    @app.post("/api/guide")
    def post_guide(payload: dict):
        errs = _check_must_decide_answered(payload)
        if errs:
            return JSONResponse({"ok": False, "errors": errs}, status_code=422)
        payload = apply_must_decide(payload)
        errs = validate(payload)
        if errs:
            return JSONResponse({"ok": False, "errors": errs}, status_code=422)
        guide_mod.save_guide(guide_path, payload)
        on_saved()
        return {"ok": True}

    return app


def run_review_server(draft_path: str, guide_path: str, *, host: str = "127.0.0.1",
                      port: int = 8765) -> int:
    """Vrací 0 jen když člověk návod skutečně uložil."""
    import uvicorn

    saved = {"ok": False}
    server_holder = {}

    def on_saved():
        saved["ok"] = True
        srv = server_holder.get("server")
        if srv is not None:
            srv.should_exit = True     # uložením práce končí

    app = build_app(draft_path, guide_path, on_saved)
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    server_holder["server"] = server

    url = f"http://{host}:{port}/"
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    print(f"Review UI běží na {url} - ulož návod a okno zavři.")
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    return 0 if saved["ok"] else 1
