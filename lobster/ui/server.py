import os
import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from lobster.agent.core import Agent
from lobster.utils.approval import ApprovalManager

HTML_FILE_PATH = os.path.join(os.path.dirname(__file__), "index.html")
HISTORY_FILE_PATH = os.path.join(os.getcwd(), ".lobster_data", "history.json")

approval_mgr = ApprovalManager()

class LobsterHTTPHandler(BaseHTTPRequestHandler):
    agent: Agent = None

    def _set_headers(self, status=200, content_type="application/json"):
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
        except (ConnectionResetError, BrokenPipeError):
            pass

    def do_OPTIONS(self):
        self._set_headers(200)

    def _format_debug_events(self, events):
        """Extract clean tool call and result pairs, stripping API metadata."""
        cleaned = []
        for e in events:
            if not isinstance(e, dict):
                continue
            parts = e.get("parts", [])
            for p in parts:
                if not isinstance(p, dict):
                    continue
                
                # Format Tool Call
                if "functionCall" in p:
                    fc = p["functionCall"]
                    cleaned.append({
                        "type": "call",
                        "tool": fc.get("name", "unknown"),
                        "args": fc.get("args", {})
                    })
                
                # Format Tool Result
                elif "functionResponse" in p:
                    fr = p["functionResponse"]
                    res = fr.get("response", {}).get("result", "")
                    cleaned.append({
                        "type": "result",
                        "tool": fr.get("name", "unknown"),
                        "output": res
                    })
        return cleaned

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            
            # 1. Serve HTML WebUI
            if parsed.path in ("/", "/index.html"):
                if os.path.exists(HTML_FILE_PATH):
                    with open(HTML_FILE_PATH, "rb") as f:
                        content = f.read()
                    self._set_headers(200, "text/html; charset=utf-8")
                    self.wfile.write(content)
                else:
                    self._set_headers(404, "text/plain")
                    self.wfile.write(b"index.html not found in lobster/ui/")

            # 2. History
            elif parsed.path == "/api/history":
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
                                    elif "functionCall" in p or "functionResponse" in p:
                                        has_tool_event = True
                                elif isinstance(p, str):
                                    text_content += p
                            if has_tool_event:
                                pending_debug.extend(self._format_debug_events([item]))
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
                self._set_headers(200)
                self.wfile.write(json.dumps(formatted_history).encode("utf-8"))

            # 3. Tasks
            elif parsed.path == "/api/tasks":
                tasks = self.agent.task_manager.list_tasks()
                self._set_headers(200)
                self.wfile.write(json.dumps(tasks).encode("utf-8"))

            # 4. Facts
            elif parsed.path == "/api/facts":
                hist_count = 0
                if os.path.exists(HISTORY_FILE_PATH):
                    try:
                        with open(HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
                            hist_count = len(json.load(f))
                    except Exception:
                        hist_count = len(self.agent.history)
                data = {
                    "facts": self.agent.fact_memory.get_facts(),
                    "history_message_count": hist_count
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(data).encode("utf-8"))

            # 5. Tools
            elif parsed.path == "/api/tools":
                tools_list = [{"name": name, "description": getattr(t, "description", "")} for name, t in self.agent.tools.items()]
                self._set_headers(200)
                self.wfile.write(json.dumps(tools_list).encode("utf-8"))

            # 6. Approvals
            elif parsed.path == "/api/approvals":
                self._set_headers(200)
                self.wfile.write(json.dumps(approval_mgr.get_pending()).encode("utf-8"))

            else:
                self._set_headers(404)
                self.wfile.write(b'{"error": "Not Found"}')

        except (ConnectionResetError, BrokenPipeError):
            pass

    def do_POST(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/api/chat":
            length = int(self.headers.get('content-length', 0))
            body = json.loads(self.rfile.read(length).decode('utf-8'))
            user_msg = body.get("message", "")
            
            try:
                hist_len_before = len(self.agent.history)
                response = self.agent.run_turn(user_msg)
                
                new_entries = self.agent.history[hist_len_before:]
                tool_events = [
                    e for e in new_entries 
                    if isinstance(e, dict) and any("functionCall" in p or "functionResponse" in p for p in e.get("parts", []))
                ]
                
                debug_info = self._format_debug_events(tool_events) if tool_events else None

                self._set_headers(200)
                self.wfile.write(json.dumps({"response": response, "debug": debug_info}).encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                try:
                    self._set_headers(500)
                    self.wfile.write(json.dumps({"response": f"Agent Execution Error: {str(e)}", "debug": None}).encode("utf-8"))
                except (BrokenPipeError, ConnectionResetError):
                    pass

        elif parsed.path == "/api/approve":
            try:
                length = int(self.headers.get('content-length', 0))
                body = json.loads(self.rfile.read(length).decode('utf-8'))
                req_id = body.get("id")
                decision = bool(body.get("decision", False))
                
                success = approval_mgr.resolve(req_id, decision)
                self._set_headers(200)
                self.wfile.write(json.dumps({"success": success}).encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                try:
                    self._set_headers(500)
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                except (BrokenPipeError, ConnectionResetError):
                    pass

        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not Found"}')

    def log_message(self, format, *args):
        return


class WebUIServer:
    def __init__(self, agent: Agent, port: int = 8080):
        self.port = port
        self.agent = agent
        self.agent.mode = "web"
        LobsterHTTPHandler.agent = self.agent
        self.server = ThreadingHTTPServer(("0.0.0.0", port), LobsterHTTPHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        print(f"🌐 WebUI running at: http://localhost:{self.port}")

    def stop(self):
        self.server.shutdown()
