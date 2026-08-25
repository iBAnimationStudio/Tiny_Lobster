import time
from typing import Dict, Any
from lobster.tools.base import Tool
from lobster.config import Config
from lobster.task.manager import TaskManager

class TaskTool(Tool):
    name = "task_manager"
    description = (
        "Create, update, list, or inspect scheduled tasks. Tasks persist and execute based on "
        "priority and urgency with a 1-task-per-minute rate limit."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "update", "list", "get"],
                "description": "The task operation to perform."
            },
            "description": {
                "type": "string",
                "description": "Short summary of the task (required for 'create')."
            },
            "is_task_need_ai": {
                "type": "boolean",
                "description": "True if AI should reason & solve; False if direct shell command."
            },
            "prompt": {
                "type": "string",
                "description": "Required when is_task_need_ai is True: Instruction sent to AI upon execution."
            },
            "command": {
                "type": "string",
                "description": "Required when is_task_need_ai is False: Shell command to run directly."
            },
            "delay_seconds": {
                "type": "integer",
                "description": "Delay in seconds from now before executing (default: 0)."
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
                "description": "Task ID (required for 'update' or 'get')."
            },
            "status_filter": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed", "failed"],
                "description": "Filter list results by status."
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
        delay_seconds: int = 0,
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

                # Enforce prompt requirement for AI tasks
                if is_task_need_ai:
                    if not prompt or not prompt.strip():
                        return (
                            "Error: 'prompt' is required when 'is_task_need_ai' is True. "
                            "Please specify the prompt/instructions to send to the AI when executing."
                        )
                else:
                    # Enforce command requirement for non-AI tasks
                    if not command or not command.strip():
                        return (
                            "Error: 'command' is required when 'is_task_need_ai' is False. "
                            "Please specify the shell command to run directly."
                        )

                scheduled_epoch = time.time() + max(0, delay_seconds or 0)
                t = self.tm.create_task(
                    description=description.strip(),
                    is_task_need_ai=is_task_need_ai,
                    prompt=prompt.strip() if prompt else None,
                    command=command.strip() if command else None,
                    priority=priority,
                    urgency=urgency,
                    scheduled_epoch=scheduled_epoch
                )
                return f"✅ Task '{t['id']}' created successfully (AI: {is_task_need_ai}, Scheduled in: {delay_seconds}s)."

            elif action == "list":
                tasks = self.tm.list_tasks(status=status_filter)
                if not tasks:
                    return "No tasks found."
                lines = [f"Found {len(tasks)} tasks:"]
                for t in tasks:
                    lines.append(
                        f"- [{t['id']}] ({t['status']}) P:{t['priority']} U:{t['urgency']} "
                        f"AI:{t['is_task_need_ai']} | {t['description']}"
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
                
                success = self.tm.update_task(task_id, **updates)
                if success:
                    return f"✅ Task '{task_id}' updated successfully."
                return f"Error: Task '{task_id}' not found."

            return f"Error: Unknown action '{action}'."
        except Exception as e:
            return f"TaskTool error: {str(e)}"
