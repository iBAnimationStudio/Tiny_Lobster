import os
import json
import time
import uuid
import re
import threading
import subprocess
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple


def _match_cron_part(val: int, expr: str, min_val: int, max_val: int) -> bool:
    """Matches an integer against standard cron segment syntax (*, */n, 1-5, 1,2,3)."""
    if expr == "*":
        return True
    for part in expr.split(","):
        if "/" in part:
            sub, step_s = part.split("/", 1)
            step = int(step_s)
            if sub == "*":
                if (val - min_val) % step == 0:
                    return True
            elif "-" in sub:
                start, end = map(int, sub.split("-", 1))
                if start <= val <= end and (val - start) % step == 0:
                    return True
        elif "-" in part:
            start, end = map(int, part.split("-", 1))
            if start <= val <= end:
                return True
        else:
            if int(part) == val:
                return True
    return False


def compute_next_cron(cron_expr: str, base_dt: Optional[datetime] = None) -> datetime:
    """Calculates next matching datetime for a standard 5-part cron string."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron format '{cron_expr}'. Expected: 'min hour day month weekday'")

    min_expr, hr_expr, dom_expr, mon_expr, dow_expr = parts
    current = (base_dt or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Search up to 1 year forward minute-by-minute
    for _ in range(525600):
        # Python weekday: Mon=0 ... Sun=6; Cron convention: Sun=0 ... Sat=6
        cron_dow = (current.weekday() + 1) % 7
        
        if (
            _match_cron_part(current.minute, min_expr, 0, 59)
            and _match_cron_part(current.hour, hr_expr, 0, 23)
            and _match_cron_part(current.day, dom_expr, 1, 31)
            and _match_cron_part(current.month, mon_expr, 1, 12)
            and _match_cron_part(cron_dow, dow_expr, 0, 6)
        ):
            return current
        current += timedelta(minutes=1)

    raise ValueError(f"Could not find next matching time for cron expression: {cron_expr}")


def parse_schedule_epoch(
    run_at: Optional[str] = None,
    delay_seconds: int = 0,
    interval_seconds: Optional[int] = None,
    cron_expr: Optional[str] = None
) -> Tuple[float, str]:
    """Calculates epoch timestamp and ISO datetime string for next run."""
    now = datetime.now()

    if cron_expr:
        next_dt = compute_next_cron(cron_expr, now)
        return next_dt.timestamp(), next_dt.isoformat()

    if run_at:
        run_at_str = run_at.strip()
        # HH:MM or HH:MM:SS format
        if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", run_at_str):
            t_parts = [int(p) for p in run_at_str.split(":")]
            target = now.replace(
                hour=t_parts[0],
                minute=t_parts[1],
                second=t_parts[2] if len(t_parts) > 2 else 0,
                microsecond=0
            )
            if target <= now:
                target += timedelta(days=1)
            return target.timestamp(), target.isoformat()

        # Full ISO timestamp
        try:
            target = datetime.fromisoformat(run_at_str.replace("Z", "+00:00"))
            return target.timestamp(), target.isoformat()
        except ValueError:
            pass

    if interval_seconds and interval_seconds > 0:
        target = now + timedelta(seconds=interval_seconds)
        return target.timestamp(), target.isoformat()

    target = now + timedelta(seconds=max(0, delay_seconds))
    return target.timestamp(), target.isoformat()


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
        run_at: Optional[str] = None,
        delay_seconds: int = 0,
        interval_seconds: Optional[int] = None,
        cron: Optional[str] = None,
        repeat: bool = False,
        repeat_count: Optional[int] = None
    ) -> Dict[str, Any]:
        if is_task_need_ai and not (prompt and prompt.strip()):
            raise ValueError("A prompt is strictly required when is_task_need_ai is True.")
        if not is_task_need_ai and not (command and command.strip()):
            raise ValueError("A shell command is strictly required when is_task_need_ai is False.")

        next_run_epoch, next_run_iso = parse_schedule_epoch(
            run_at=run_at,
            delay_seconds=delay_seconds,
            interval_seconds=interval_seconds,
            cron_expr=cron
        )

        with self.lock:
            tasks = self._load()
            task_id = f"task_{uuid.uuid4().hex[:6]}"
            
            task = {
                "id": task_id,
                "description": description.strip(),
                "is_task_need_ai": is_task_need_ai,
                "prompt": prompt.strip() if prompt else "",
                "command": command.strip() if command else "",
                "priority": max(1, min(int(priority), 10)),
                "urgency": max(1, min(int(urgency), 10)),
                
                # Scheduling fields
                "run_at": run_at,
                "delay_seconds": delay_seconds,
                "interval_seconds": interval_seconds,
                "cron": cron,
                "repeat": bool(repeat or interval_seconds or cron),
                "repeat_count": repeat_count,
                "next_run": next_run_iso,
                "next_run_epoch": next_run_epoch,
                "last_run": None,
                
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
                    
                    # Recompute schedule if time parameters changed
                    if any(k in kwargs for k in ("run_at", "delay_seconds", "interval_seconds", "cron")):
                        epoch, iso = parse_schedule_epoch(
                            run_at=t.get("run_at"),
                            delay_seconds=t.get("delay_seconds", 0),
                            interval_seconds=t.get("interval_seconds"),
                            cron_expr=t.get("cron")
                        )
                        t["next_run_epoch"] = epoch
                        t["next_run"] = iso

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
        """Finds the highest priority/urgency task due for execution."""
        with self.lock:
            tasks = self._load()
            now = time.time()
            eligible = [
                t for t in tasks 
                if t.get("status") == "pending" and t.get("next_run_epoch", 0) <= now
            ]
            if not eligible:
                return None

            def calculate_score(t):
                return (t.get("priority", 1) * 2) + t.get("urgency", 1)

            eligible.sort(key=calculate_score, reverse=True)
            return eligible[0]

    def complete_task(self, task_id: str, result: str, failed: bool = False):
        """Finalizes run; reschedules recurring tasks or marks one-offs completed."""
        with self.lock:
            tasks = self._load()
            for t in tasks:
                if t["id"] == task_id:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    t["last_run"] = now_iso
                    t["result"] = result

                    # Recurring task evaluation
                    is_recurring = t.get("repeat", False) or t.get("interval_seconds") or t.get("cron")
                    remaining_count = t.get("repeat_count")

                    if is_recurring and not failed:
                        if remaining_count is not None:
                            remaining_count -= 1
                            t["repeat_count"] = remaining_count

                        if remaining_count is None or remaining_count > 0:
                            # Schedule next recurrence
                            next_epoch, next_iso = parse_schedule_epoch(
                                interval_seconds=t.get("interval_seconds"),
                                cron_expr=t.get("cron")
                            )
                            t["next_run_epoch"] = next_epoch
                            t["next_run"] = next_iso
                            t["status"] = "pending"
                            break

                    t["status"] = "failed" if failed else "completed"
                    t["completed_at"] = now_iso
                    break
            self._save(tasks)


    def cancel_task(self, task_id: str, reason: str = "Cancelled by user") -> bool:
        """Stops/cancels an active or pending task without deleting its audit record."""
        with self.lock:
            tasks = self._load()
            for t in tasks:
                if t["id"] == task_id:
                    if t.get("status") in ("completed", "cancelled"):
                        return False
                    t["status"] = "cancelled"
                    t["result"] = f"Task cancelled: {reason}"
                    t["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(tasks)
                    return True
            return False



class TaskWorker:
    """Background daemon enforcing 1 task per minute execution rate limit."""
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
        print(f"\n⏰ [Task Manager] Executing '{task_id}': {task['description']}")

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
                    raw_out = "No command provided."

                follow_up_prompt = (
                    f"[SCHEDULED DIRECT TASK COMPLETED: {task_id}]\n"
                    f"Description: {task['description']}\n"
                    f"Command Output:\n{raw_out}\n\n"
                    f"Evaluate output and take necessary action."
                )
                output = self.agent_executor(follow_up_prompt)
                self.tm.complete_task(task_id, result=f"Raw:\n{raw_out}\n\nEval:\n{output}")

            print(f"✅ [Task Manager] Task '{task_id}' processed.\n")
        except Exception as e:
            self.tm.complete_task(task_id, result=f"Execution Failed: {str(e)}", failed=True)
            print(f"❌ [Task Manager] Task '{task_id}' failed: {e}\n")
