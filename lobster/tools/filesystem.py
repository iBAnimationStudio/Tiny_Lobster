import os
from .base import Tool
from ..config import Config

class FileTool(Tool):
    name = "file"
    description = "Perform basic filesystem operations: read, write, list, exists, metadata."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write", "list", "exists", "metadata"]},
            "path": {"type": "string"},
            "content": {"type": "string", "description": "Required for 'write' action."}
        },
        "required": ["action", "path"]
    }

    def __init__(self, config: Config):
        self.config = config

    def execute(self, action: str, path: str, content: str = None, **kwargs) -> str:
        try:
            if action == "read":
                if not os.path.isfile(path): return f"Error: File not found: {path}"
                with open(path, "r", encoding="utf-8", errors="ignore") as f: text = f.read()
                if len(text) > self.config.max_output: text = text[:self.config.max_output] + "\n[TRUNCATED]"
                return text
            elif action == "write":
                if content is None: return "Error: 'content' required for 'write'."
                with open(path, "w", encoding="utf-8") as f: f.write(content)
                return f"Successfully wrote to {path}"
            elif action == "list":
                if not os.path.isdir(path): return f"Error: Directory not found: {path}"
                items = os.listdir(path)
                return "\n".join(items) if items else "Empty directory"
            elif action == "exists":
                return str(os.path.exists(path))
            elif action == "metadata":
                if not os.path.exists(path): return f"Error: Path not found: {path}"
                stat = os.stat(path)
                return f"Size: {stat.st_size}\nModified: {stat.st_mtime}\nIs File: {os.path.isfile(path)}\nIs Dir: {os.path.isdir(path)}"
            return f"Error: Unknown action '{action}'"
        except Exception as e:
            return f"Error: {str(e)}"
