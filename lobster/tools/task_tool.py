from typing import Dict, Any, Optional
from lobster.tools.base import Tool
from lobster.config import Config
from lobster.task.manager import TaskManager

class TaskTool(Tool):
    name = "task_manager"
    description = (
        "Schedule, repeat, update, list, and inspect autonomous background tasks. "
        "Supports cron expressions, run_at timestamps, fixed intervals, priority/urgency sorting, "
        "and direct terminal or AI reasoning execution (1 task per minute rate limit)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "update", "cancel", "list", "get"],
                "description": "Task operation: 'create', 'update', 'list', or 'get'."
            },
            "description": {
                "type": "string",
                "description": "Short summary of the task (required for 'create')."
            },
            "is_task_need_ai": {
                "type": "boolean",
                "description": "True if AI should reason & solve; False if raw shell command."
            },
            "prompt": {
                "type": "string",
                "description": "Instruction sent to AI upon execution (MANDATORY if is_task_need_ai is True)."
            },
            "command": {
                "type": "string",
                "description": "Shell command to execute directly (MANDATORY if is_task_need_ai is False)."
            },
            "run_at": {
                "type": "string",
                "description": "Target execution time ('HH:MM', 'HH:MM:SS', or ISO 'YYYY-MM-DDTHH:MM:SS')."
            },
            "delay_seconds": {
                "type": "integer",
                "description": "One-off delay in seconds from current time."
            },
            "interval_seconds": {
                "type": "integer",
                "description": "Recurring interval in seconds (e.g. 3600 for every hour)."
            },
            "cron": {
                "type": "string",
                "description": "Standard 5-part cron expression (e.g. '*/30 * * * *', '0 9 * * 1-5')."
            },
            "repeat": {
                "type": "boolean",
                "description": "Whether the task repeats periodically."
            },
            "repeat_count": {
                "type": "integer",
                "description": "Number of times to repeat before completing (null/omit for indefinite)."
            },
            "priority": {
                "type": "integer",
                "description": "Priority score from 1 (low) to 10 (high)."
            },
            "urgency": {
                "type": "integer",
                "description": "Urgency score from 1 (low) to 10 (high)."
            },
            "task_id": {
                "type": "string",
                "description": "Target task ID (required for 'update' or 'get')."
            },
            "status_filter": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed", "failed"],
                "description": "Filter list by status."
            }
        },
        "required": ["action"]
    }

    def __init__(self, config: Config, task_manager: TaskManager):
        self.config = config
        self.tm = task_manager

    def execute(
        self,
        action: str,
        description: str = None,
        is_task_need_ai: bool = True,
        prompt: str = None,
        command: str = None,
        run_at: str = None,
        delay_seconds: int = 0,
        interval_seconds: int = None,
        cron: str = None,
        repeat: bool = False,
        repeat_count: int = None,
        priority: int = 1,
        urgency: int = 1,
        task_id: str = None,
        status_filter: str = None,
        **kwargs
    ) -> str:
        try:
            if action == "create":
                if not description or not description.strip():
                    return "Error: 'description' is required to create a task."

                if is_task_need_ai:
                    if not prompt or not prompt.strip():
                        return (
                            "Error: 'prompt' is required when 'is_task_need_ai' is True. "
                            "Please provide the exact prompt to feed the AI when the task runs."
                        )
                else:
                    if not command or not command.strip():
                        return (
                            "Error: 'command' is required when 'is_task_need_ai' is False. "
                            "Please provide the shell command to execute."
                        )

                t = self.tm.create_task(
                    description=description.strip(),
                    is_task_need_ai=is_task_need_ai,
                    prompt=prompt.strip() if prompt else None,
                    command=command.strip() if command else None,
                    priority=priority,
                    urgency=urgency,
                    run_at=run_at,
                    delay_seconds=delay_seconds,
                    interval_seconds=interval_seconds,
                    cron=cron,
                    repeat=repeat,
                    repeat_count=repeat_count
                )
                return (
                    f"✅ Task '{t['id']}' scheduled successfully.\n"
                    f"- Next Run: {t['next_run']}\n"
                    f"- AI Mode: {t['is_task_need_ai']}\n"
                    f"- Repeat: {t['repeat']} (Cron: {t.get('cron') or 'None'}, Interval: {t.get('interval_seconds') or 'None'}s)"
                )

            elif action == "list":
                tasks = self.tm.list_tasks(status=status_filter)
                if not tasks:
                    return "No tasks found."
                lines = [f"Found {len(tasks)} tasks:"]
                for t in tasks:
                    sched_info = f"Next: {t.get('next_run', 'N/A')}"
                    if t.get("cron"):
                        sched_info += f" [Cron: {t['cron']}]"
                    elif t.get("interval_seconds"):
                        sched_info += f" [Every: {t['interval_seconds']}s]"

                    lines.append(
                        f"- [{t['id']}] ({t['status']}) P:{t['priority']} U:{t['urgency']} "
                        f"AI:{t['is_task_need_ai']} | {t['description']} | {sched_info}"
                    )
                return "\n".join(lines)

            elif action == "get":
                if not task_id:
                    return "Error: 'task_id' is required."
                tasks = self.tm.list_tasks()
                match = next((t for t in tasks if t["id"] == task_id), None)
                if not match:
                    return f"Error: Task '{task_id}' not found."
                return (
                    f"Task {match['id']}:\n"
                    f"Description: {match['description']}\n"
                    f"Status: {match['status']}\n"
                    f"Next Run: {match.get('next_run')}\n"
                    f"Last Run: {match.get('last_run') or 'Never'}\n"
                    f"Schedule: Cron='{match.get('cron')}' | Interval={match.get('interval_seconds')}s | RunAt='{match.get('run_at')}'\n"
                    f"AI Required: {match['is_task_need_ai']}\n"
                    f"Priority: {match['priority']} | Urgency: {match['urgency']}\n"
                    f"Prompt: {match.get('prompt') or 'N/A'}\n"
                    f"Command: {match.get('command') or 'N/A'}\n"
                    f"Result: {match.get('result') or 'None'}"
                )

            elif action == "update":
                if not task_id:
                    return "Error: 'task_id' is required to update."
                updates = {k: v for k, v in kwargs.items() if v is not None}
                if priority: updates["priority"] = priority
                if urgency: updates["urgency"] = urgency
                if description: updates["description"] = description
                if prompt: updates["prompt"] = prompt
                if command: updates["command"] = command
                if run_at: updates["run_at"] = run_at
                if interval_seconds: updates["interval_seconds"] = interval_seconds
                if cron: updates["cron"] = cron
                if repeat is not None: updates["repeat"] = repeat

                success = self.tm.update_task(task_id, **updates)
                if success:
                    return f"✅ Task '{task_id}' updated successfully."
                return f"Error: Task '{task_id}' not found."

            elif action == "cancel":
                if not task_id:
                    return "Error: 'task_id' is required to cancel a task."
                reason = kwargs.get("reason") or "Cancelled by user/agent."
                success = self.tm.cancel_task(task_id, reason=reason)
                if success:
                    return f"🛑 Task '{task_id}' has been cancelled and stopped."
                return f"Error: Task '{task_id}' not found or already completed/cancelled."


            return f"Error: Unknown action '{action}'."
        except Exception as e:
            return f"TaskTool error: {str(e)}"
