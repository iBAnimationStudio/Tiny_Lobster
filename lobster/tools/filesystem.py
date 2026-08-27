import os
import re
from lobster.tools.base import Tool
from lobster.config import Config

PROTECTED_SYSTEM_DIRS = (
    "/system",
    "/vendor",
    "/apex",
    "/data/data/com.termux/files/usr/bin",
    "/data/data/com.termux/files/usr/lib",
    "/data/data/com.termux/files/usr/etc",
    "/etc",
    "/proc",
    "/sys",
    "/dev"
)

PROTECTED_USER_PATTERNS = (
    r"\.git($|/)",
    r"\.ssh($|/)",
    r"\.gnupg($|/)",
    r"\.(bashrc|bash_profile|zshrc|profile)$",
    r"\.netrc$",
    r"\.env.*$",
    r"id_rsa",
    r"id_ed25519",
    r"known_hosts"
)

PROTECTED_STORAGE_DIRS = (
    "/storage/emulated/0/Android/data",
    "/storage/emulated/0/Android/obb"
)

PROTECTED_CORE_FILES = (
    "main.py",
    "lobster/agent/core.py",
    "lobster/config.py",
    "lobster/ui/server.py",
    "lobster/tools/filesystem.py",
    "lobster/tools/terminal.py",
    "lobster/utils/approval.py"
)


def is_dangerous_file_op(action: str, target_path: str) -> bool:
    """Check if a filesystem action poses destructive, privilege, or overwrite risks."""
    if not target_path:
        return False

    norm_path = os.path.abspath(os.path.expanduser(target_path.strip()))

    # 1. Any file or directory deletion
    if action in ("delete", "remove", "unlink", "rmdir"):
        return True

    # 2. System and package paths
    if any(norm_path.startswith(d) for d in PROTECTED_SYSTEM_DIRS):
        return True

    # 3. Android restricted app data/obb
    if any(norm_path.startswith(d) for d in PROTECTED_STORAGE_DIRS):
        return True

    # 4. SSH keys, shell dotfiles, and git internals
    for pattern in PROTECTED_USER_PATTERNS:
        if re.search(pattern, norm_path):
            return True

    # 5. Lobster core codebase files
    if any(norm_path.endswith(core_file) for core_file in PROTECTED_CORE_FILES):
        return True

    # 6. Overwriting an existing file with 'write' (truncation safeguard)
    if action == "write" and os.path.exists(norm_path):
        if not norm_path.endswith((".log", ".tmp", ".cache")):
            return True

    return False


class FileTool(Tool):
    name = "file"
    description = "Perform filesystem operations: read, write, append, delete, list, exists, metadata."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "append", "delete", "list", "exists", "metadata"],
                "description": "File operation to perform."
            },
            "path": {"type": "string", "description": "Target file or directory path."},
            "content": {"type": "string", "description": "Required for 'write' or 'append'."}
        },
        "required": ["action", "path"]
    }

    def __init__(self, config: Config):
        self.config = config

    def execute(self, action: str, path: str, content: str = None, **kwargs) -> str:
        try:
            path = os.path.expanduser(path.strip())

            if action == "read":
                if not os.path.isfile(path):
                    return f"Error: File not found: {path}"
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                if len(text) > self.config.max_output:
                    text = text[:self.config.max_output] + "\n[OUTPUT TRUNCATED]"
                return text

            elif action in ("write", "append"):
                if content is None:
                    return f"Error: 'content' parameter is required for '{action}'."
                
                parent = os.path.dirname(path)
                if parent and not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)

                mode = "w" if action == "write" else "a"
                with open(path, mode, encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully {action}d {len(content)} characters to {path}"

            elif action == "delete":
                if not os.path.exists(path):
                    return f"Error: Path does not exist: {path}"
                if os.path.isdir(path):
                    os.rmdir(path)
                    return f"Successfully removed directory: {path}"
                else:
                    os.remove(path)
                    return f"Successfully deleted file: {path}"

            elif action == "list":
                if not os.path.isdir(path):
                    return f"Error: Directory not found: {path}"
                items = os.listdir(path)
                return "\n".join(sorted(items)) if items else "Empty directory"

            elif action == "exists":
                return str(os.path.exists(path))

            elif action == "metadata":
                if not os.path.exists(path):
                    return f"Error: Path not found: {path}"
                stat = os.stat(path)
                return (
                    f"Path: {path}\n"
                    f"Size: {stat.st_size} bytes\n"
                    f"Is File: {os.path.isfile(path)}\n"
                    f"Is Dir: {os.path.isdir(path)}"
                )

            return f"Error: Unknown action '{action}'"
        except Exception as e:
            return f"Error: {str(e)}"
