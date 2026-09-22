"""Lokální web UI pro odpovídání na otevřené otázky (`state.questions`
tabulka - nové termíny/jména k potvrzení, cross-kapitolový drift stejného
slova). Jiný zdroj dat než `server.py` (ten je jen guide.draft, scan fáze,
před prvním překladem) - tenhle běží NAD DB, stejný mechanismus jako CLI
`python main.py answer <ID> "text"` (`requeue.apply_answer`), jen s webovým
formulářem místo příkazové řádky.

Zámek drží `main()`'s `_MUTATING` obal (main.py, stejný vzor jako `review`/
`polish-review`) po CELOU dobu běhu serveru - žádný vlastní heartbeat
potřeba (`_LOCK_STALE_SECONDS` je 6h, dostatečná rezerva na jedno sezení
odpovídání na otázky, stejná úvaha jako u `review`).
"""
import os
import threading
import webbrowser

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src import requeue, state

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def build_app(db_path: str, guide_path: str) -> FastAPI:
    app = FastAPI(title="Book translator - otevřené otázky")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_STATIC, "questions.html"))

    @app.get("/api/questions")
    def get_questions():
        return state.unanswered_questions(db_path)

    @app.post("/api/answer")
    def post_answer(payload: dict):
        qid = payload.get("qid")
        text = payload.get("text") or ""
        try:
            out = requeue.apply_answer(db_path, guide_path, qid, text)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return out

    return app


def run_questions_review_server(db_path: str, guide_path: str, *,
                                host: str = "127.0.0.1", port: int = 8767) -> int:
    """Vrací VŽDY 0 - žádný CLI krok po `questions-review` nezávisí na tom,
    kolik otázek bylo zodpovězeno (stejný vzor jako `polish-review`)."""
    import uvicorn
    app = build_app(db_path, guide_path)
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    url = f"http://{host}:{port}/"
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    server.run()
    return 0
