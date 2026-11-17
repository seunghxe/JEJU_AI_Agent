"""제주 충전 Plan B 웹 서버.

실행: python server.py  →  브라우저에서 http://localhost:8501
"""
from __future__ import annotations

import os
import threading
import uuid
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env", override=True)

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import llm_agent  # noqa: E402
import request_progress
from agent_service import AgentService  # noqa: E402
from conversation_graph import ConversationGraph  # noqa: E402

service = AgentService(APP_DIR / "data")
conversation = ConversationGraph(service)
app = FastAPI(title="제주 EV Plan B AI Agent", version="last2-full")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


class AskRequest(BaseModel):
    progress_id: uuid.UUID | None = None
    query: str = Field(..., min_length=1, max_length=2000)
    connector: str | None = Field(None, max_length=30)
    vehicle: str | None = None
    battery: int = Field(40, ge=1, le=100)
    battery_override: bool = False
    origin: str = ""
    origin_lat: float | None = None
    origin_lon: float | None = None
    preference: str = "균형 추천"
    count: int = Field(3, ge=1, le=5)
    thread_id: str | None = Field(None, max_length=100)


@app.get("/")
def index():
    return FileResponse(APP_DIR / "static" / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/meta")
def meta():
    payload = service.meta()
    js_key = os.getenv("KAKAO_MAP_JS_KEY", "").strip()
    payload["map_js_key"] = js_key if js_key != os.getenv("KAKAO_REST_API_KEY", "").strip() else ""
    payload["orchestration"] = {"name": "LangGraph", "memory": "서버 실행 중 세션 기억"}
    return payload


@app.get("/api/stations")
def stations():
    return service.station_points()


@app.get("/api/status")
def status():
    return service.status()


@app.post("/api/ask")
def ask(req: AskRequest):
    thread_id = req.thread_id or str(uuid.uuid4())
    token = request_progress.active.set(str(req.progress_id) if req.progress_id else None)
    try:
        request_progress.mark(1)
        return conversation.invoke(thread_id, {
        "query": req.query, "vehicle": req.vehicle, "connector": req.connector, "battery": req.battery, "battery_override": req.battery_override,
        "origin": req.origin, "origin_lat": req.origin_lat, "origin_lon": req.origin_lon,
        "preference": req.preference, "count": req.count,
        })
    finally:
        request_progress.active.reset(token)

@app.get("/api/progress/{progress_id}")
def progress(progress_id: uuid.UUID):
    return {"step": request_progress.get(str(progress_id))}


@app.delete("/api/conversation/{thread_id}")
def reset_conversation(thread_id: str):
    conversation.clear(thread_id)
    return {"ok": True, "thread_id": thread_id}


@app.post("/api/live/refresh")
def refresh_live():
    service.live(force=True)
    return service.status()


@app.post("/api/datahub/refresh")
def refresh_datahub():
    service.datahub.refresh()
    return service.status()


@app.get("/api/live/station/{facility_id}")
def station_live(facility_id: str):
    return service.station_live(facility_id)


class BackupRequest(BaseModel):
    facility_id: str = Field(..., max_length=100)
    exclude_ids: list[str] = Field(default_factory=list, max_length=900)


@app.post("/api/planb/recheck")
def recheck_plan_b(req: BackupRequest):
    return service.recheck_plan_b(req.facility_id, req.exclude_ids)


@app.post("/api/gemini/check")
def gemini_check():
    ok, msg = llm_agent.check_connection()
    return {"ok": ok, "message": msg}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8501"))
    if os.getenv("NO_BROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
