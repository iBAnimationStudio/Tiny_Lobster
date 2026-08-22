import os
import subprocess
from .base import Tool
from config import Config

class DynamicTool(Tool):
    def __init__(self, config: Config, meta: dict):
        self.name = meta["name"]
        self.description = meta["description"]
        self.parameters = meta["parameters"]
        self.filename = meta["filename"]
        self.config = config
        self.workspace = os.path.join(os.getcwd(), ".lobster_data", "workspace")

    def execute(self, **kwargs) -> str:
        file_path = os.path.join(self.workspace, self.filename)
        if not os.path.exists(file_path):
            return f"Error: Custom tool script '{self.filename}' not found in workspace."
        
        try:
            # We pass the arguments as environment variables or a JSON file for the script to read
            # For simplicity in v0.1, we'll assume the script uses sys.argv or input() 
            # But to make it robust, let's pass args as a JSON string via env var
            import json
            env = os.environ.copy()
            env["LOBSTER_TOOL_ARGS"] = json.dumps(kwargs)
            
            result = subprocess.run(
                ["python", file_path],
                capture_output=True,
                text=True,
                timeout=self.config.command_timeout,
                env=env,
                cwd=self.workspace
            )
            
            output = f"Custom Tool '{self.name}' executed.\n"
            if result.stdout: output += f"Output:\n{result.stdout}\n"
            if result.stderr: output += f"Errors:\n{result.stderr}\n"
            output += f"Exit Code: {result.returncode}"
            
            if len(output) > self.config.max_output:
                output = output[:self.config.max_output] + "\n[OUTPUT TRUNCATED]"
                
            return output.strip()
        except Exception as e:
            return f"Error executing custom tool: {str(e)}"