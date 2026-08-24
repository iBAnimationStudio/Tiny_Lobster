import os
import subprocess
from lobster.tools.base import Tool
from lobster.config import Config

DANGEROUS_PATTERNS = [
    "rm ", "rm\t", "rm\n", "rm -", 
    "mv ", "mv\t", "mv\n",
    "chmod ", "chown ", "chgrp ",
    "dd ", "mkfs", "fdisk", "parted",
    "shutdown", "reboot", "halt", "poweroff",
    "pkg install", "apt install", "apt-get install",
    "kill ", "killall ", "pkill "
]

def is_dangerous(command: str) -> bool:
    cmd_lower = command.lower()
    return any(pattern in cmd_lower for pattern in DANGEROUS_PATTERNS)

class TerminalTool(Tool):
    name = "terminal"
    description = "Execute a shell command in the Termux environment."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."}
        },
        "required": ["command"]
    }

    def __init__(self, config: Config):
        self.config = config
        self.shell = os.environ.get("SHELL", "sh")

    def execute(self, command: str, **kwargs) -> str:
        try:
            result = subprocess.run(
                command, shell=True, executable=self.shell,
                capture_output=True, text=True, timeout=self.config.command_timeout
            )
            output = f"Exit Code: {result.returncode}\n"
            if result.stdout: output += f"Stdout:\n{result.stdout}\n"
            if result.stderr: output += f"Stderr:\n{result.stderr}\n"
            
            if len(output) > self.config.max_output:
                output = output[:self.config.max_output] + "\n[OUTPUT TRUNCATED]"
            return output.strip()
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {self.config.command_timeout} seconds."
        except Exception as e:
            return f"Error executing command: {str(e)}"
