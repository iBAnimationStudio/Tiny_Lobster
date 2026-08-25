import os
import json
import time
import uuid
import threading
import subprocess
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class TaskManager:
    def __init__(self, data_dir: str = ".lobster_data"):
        self.data_dir = data_dir
        self.tasks_file = os.path.join(data_dir, "tasks.json")
        self.lock = threading.Lock()
        os.makedirs(self.data_dir, exist_ok=True)
        if not os.path.exists(self.tasks_file):
            self._save([])

    def _load(self) -> List[Dict[str, Any]]:
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, tasks: List[Dict[str, Any]]):
        with open(self.tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)

    def create_task(
        self,
        description: str,
        is_task_need_ai: bool = True,
        prompt: Optional[str] = None,
        command: Optional[str] = None,
        priority: int = 1,
        urgency: int = 1,
        scheduled_epoch: Optional[float] = None
    ) -> Dict[str, Any]:
        if is_task_need_ai and not (prompt and prompt.strip()):
            raise ValueError("A prompt is strictly required when is_task_need_ai is True.")
        if not is_task_need_ai and not (command and command.strip()):
            raise ValueError("A shell command is strictly required when is_task_need_ai is False.")

        with self.lock:
            tasks = self._load()
            task_id = f"task_{uuid.uuid4().hex[:6]}"
            now = time.time()
            
            task = {
                "id": task_id,
                "description": description.strip(),
                "is_task_need_ai": is_task_need_ai,
                "prompt": prompt.strip() if prompt else "",
                "command": command.strip() if command else "",
                "priority": max(1, min(int(priority), 10)),
                "urgency": max(1, min(int(urgency), 10)),
                "scheduled_epoch": float(scheduled_epoch) if scheduled_epoch else now,
                "status": "pending",
                "result": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None
            }
            tasks.append(task)
            self._save(tasks)
            return task

    def update_task(self, task_id: str, **kwargs) -> bool:
        with self.lock:
            tasks = self._load()
            for t in tasks:
                if t["id"] == task_id:
                    for key, val in kwargs.items():
                        if key in t and key != "id":
                            t[key] = val
                    self._save(tasks)
                    return True
            return False

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.lock:
            tasks = self._load()
            if status:
                return [t for t in tasks if t.get("status") == status]
            return tasks

    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """Fetch highest priority/urgency task that is pending and due."""
        with self.lock:
            tasks = self._load()
            now = time.time()
            eligible = [
                t for t in tasks 
                if t.get("status") == "pending" and t.get("scheduled_epoch", 0) <= now
            ]
            if not eligible:
                return None

            # Priority weighted higher than urgency
            def calculate_score(t):
                return (t.get("priority", 1) * 2) + t.get("urgency", 1)

            eligible.sort(key=calculate_score, reverse=True)
            return eligible[0]

    def complete_task(self, task_id: str, result: str, failed: bool = False):
        """Mark task complete without deleting historical record."""
        with self.lock:
            tasks = self._load()
            for t in tasks:
                if t["id"] == task_id:
                    t["status"] = "failed" if failed else "completed"
                    t["result"] = result
                    t["completed_at"] = datetime.now(timezone.utc).isoformat()
                    break
            self._save(tasks)


class TaskWorker:
    """Background daemon enforcing 1 task per minute execution limit."""
    def __init__(self, task_manager: TaskManager, agent_executor):
        self.tm = task_manager
        self.agent_executor = agent_executor
        self.last_execution_time: float = 0.0
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            now = time.time()
            time_since_last = now - self.last_execution_time
            if time_since_last < 60:
                time.sleep(min(5.0, 60 - time_since_last))
                continue

            task = self.tm.get_next_task()
            if task:
                self.last_execution_time = time.time()
                self._execute(task)
            else:
                time.sleep(5.0)

    def _execute(self, task: Dict[str, Any]):
        task_id = task["id"]
        self.tm.update_task(task_id, status="in_progress")
        print(f"\n⏰ [Task Manager] Running scheduled task '{task_id}': {task['description']}")

        try:
            if task.get("is_task_need_ai", True):
                prompt = (
                    f"[SCHEDULED TASK: {task_id}]\n"
                    f"Description: {task['description']}\n"
                    f"Instruction: {task['prompt']}"
                )
                output = self.agent_executor(prompt)
                self.tm.complete_task(task_id, result=output)
            else:
                cmd = task.get("command", "")
                if cmd:
                    res = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=60
                    )
                    raw_out = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\nEXIT:{res.returncode}"
                else:
                    raw_out = "No command provided for direct execution."

                follow_up_prompt = (
                    f"[SCHEDULED DIRECT TASK COMPLETED: {task_id}]\n"
                    f"Description: {task['description']}\n"
                    f"Command Output:\n{raw_out}\n\n"
                    f"Evaluate this output and take any necessary actions."
                )
                output = self.agent_executor(follow_up_prompt)
                self.tm.complete_task(task_id, result=f"Raw Exec:\n{raw_out}\n\nAgent Eval:\n{output}")

            print(f"✅ [Task Manager] Task '{task_id}' marked as completed.\n")
        except Exception as e:
            self.tm.complete_task(task_id, result=f"Execution Failed: {str(e)}", failed=True)
            print(f"❌ [Task Manager] Task '{task_id}' failed: {e}\n")
