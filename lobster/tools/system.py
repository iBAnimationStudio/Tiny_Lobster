import os
import platform
import sys
from .base import Tool

class SystemInfoTool(Tool):
    name = "system_info"
    description = "Get information about the current system and environment."
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs) -> str:
        info = {
            "os": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "python_version": sys.version.split()[0],
            "user": os.environ.get("USER", "unknown"),
            "home": os.environ.get("HOME", "unknown"),
            "prefix": os.environ.get("PREFIX", "unknown"),
            "cwd": os.getcwd(),
            "is_termux": "com.termux" in os.environ.get("PREFIX", "") or "ANDROID_ROOT" in os.environ
        }
        return "\n".join(f"{k}: {v}" for k, v in info.items())
