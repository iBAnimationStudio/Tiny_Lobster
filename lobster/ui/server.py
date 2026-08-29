import os
import json
import queue
import threading
import uvicorn
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from lobster.agent.core import Agent
from lobster.utils.approval import ApprovalManager

approval_mgr = ApprovalManager()
HTML_FILE_PATH = os.path.join(os.path.dirname(__file__), "index.html")
HISTORY_FILE_PATH = os.path.join(os.getcwd(), ".lobster_data", "history.json")


def is_tool_part(p: Any) -> bool:
    if not isinstance(p, dict):
        return False
    return any(k in p for k in ("functionCall", "function_call", "functionResponse", "function_response"))


def format_debug_events(events):
    cleaned = []
    for e in events:
        if not isinstance(e, dict):
            continue
        parts = e.get("parts", [])
        for p in parts:
            if not isinstance(p, dict):
                continue
            fc = p.get("function_call") or p.get("functionCall")
            if fc:
                cleaned.append({
                    "type": "call",
                    "tool": fc.get("name", "unknown"),
                    "args": fc.get("args", {})
                })
            fr = p.get("function_response") or p.get("functionResponse")
            if fr:
                resp = fr.get("response", {})
                res = resp.get("result", resp) if isinstance(resp, dict) else resp
                cleaned.append({
                    "type": "result",
                    "tool": fr.get("name", "unknown"),
                    "output": res
                })
    return cleaned


class ChatPayload(BaseModel):
    message: str


class ApprovePayload(BaseModel):
    id: str
    decision: bool


def create_app(agent: Agent) -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    @app.get("/index.html")
    def serve_ui():
        if os.path.exists(HTML_FILE_PATH):
            return FileResponse(HTML_FILE_PATH, media_type="text/html")
        raise HTTPException(status_code=404, detail="index.html not found")

    @app.get("/api/history")
    def get_history():
        formatted_history = []
        if os.path.exists(HISTORY_FILE_PATH):
            try:
                with open(HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
                    raw_history = json.load(f)
                pending_debug = []
                for item in raw_history:
                    role = item.get("role", "user")
                    parts = item.get("parts", [])
                    text_content = ""
                    has_tool_event = False
                    for p in parts:
                        if isinstance(p, dict):
                            if "text" in p and p["text"]:
                                text_content += p["text"]
                            elif is_tool_part(p):
                                has_tool_event = True
                        elif isinstance(p, str):
                            text_content += p

                    if has_tool_event:
                        pending_debug.extend(format_debug_events([item]))

                    if text_content.strip():
                        display_role = "user" if role == "user" else "lobster"
                        formatted_history.append({
                            "role": display_role,
                            "text": text_content.strip(),
                            "debug": pending_debug if (display_role == "lobster" and pending_debug) else None
                        })
                        if display_role == "lobster":
                            pending_debug = []
            except Exception as e:
                print(f"[WARN] Error reading history.json: {e}")
        return formatted_history

    @app.get("/api/tasks")
    def get_tasks():
        return agent.task_manager.list_tasks()

    @app.get("/api/facts")
    def get_facts():
        hist_count = 0
        if os.path.exists(HISTORY_FILE_PATH):
            try:
                with open(HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
                    hist_count = len(json.load(f))
            except Exception:
                hist_count = len(agent.history)
        return {
            "facts": agent.fact_memory.get_facts(),
            "history_message_count": hist_count
        }

    @app.get("/api/tools")
    def get_tools():
        return [{"name": name, "description": getattr(t, "description", "")} for name, t in agent.tools.items()]

    @app.get("/api/approvals")
    def get_approvals():
        return approval_mgr.get_pending()

    @app.post("/api/approve")
    def approve_action(payload: ApprovePayload):
        success = approval_mgr.resolve(payload.id, payload.decision)
        return {"success": success}

    @app.post("/api/chat")
    def chat_stream(payload: ChatPayload):
        def event_stream():
            event_queue = queue.Queue()

            def event_callback(data):
                event_queue.put(data)

            def runner():
                try:
                    agent.run_turn_stream(payload.message, event_callback=event_callback)
                except Exception as e:
                    event_queue.put({"type": "error", "content": str(e)})
                finally:
                    event_queue.put({"type": "done"})

            worker = threading.Thread(target=runner, daemon=True)
            worker.start()

            while True:
                data = event_queue.get()
                yield f"data: {json.dumps(data)}\n\n"
                if isinstance(data, dict) and data.get("type") in ("done", "error"):
                    break

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    return app


class WebUIServer:
    def __init__(self, agent: Agent, port: int = 8080):
        self.port = port
        self.agent = agent
        self.agent.mode = "web"
        self.app = create_app(self.agent)
        # log_level="info" enables full request logging to terminal
        self.config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="debug",
            access_log=True
        )
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self):
        self.thread.start()
        print(f"🌐 WebUI running at: http://localhost:{self.port}")

    def stop(self):
        self.server.should_exit = True
