import uuid
import time
import threading
from typing import Dict, Any, List

class ApprovalManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ApprovalManager, cls).__new__(cls)
            cls._instance.pending: Dict[str, Dict[str, Any]] = {}
            cls._instance.lock = threading.Lock()
        return cls._instance

    def request_approval(self, action_desc: str, timeout: int = 120) -> bool:
        """Pauses the running thread until user decides via UI or timeout occurs."""
        req_id = f"req_{uuid.uuid4().hex[:6]}"
        evt = threading.Event()

        with self.lock:
            self.pending[req_id] = {
                "id": req_id,
                "action": action_desc,
                "event": evt,
                "decision": False,
                "created_at": time.time()
            }

        signaled = evt.wait(timeout=timeout)

        with self.lock:
            data = self.pending.pop(req_id, None)

        if not signaled or not data:
            return False
        return data.get("decision", False)

    def get_pending(self) -> List[Dict[str, str]]:
        with self.lock:
            return [{"id": r["id"], "action": r["action"]} for r in self.pending.values()]

    def resolve(self, req_id: str, decision: bool) -> bool:
        with self.lock:
            if req_id in self.pending:
                self.pending[req_id]["decision"] = decision
                self.pending[req_id]["event"].set()
                return True
        return False
