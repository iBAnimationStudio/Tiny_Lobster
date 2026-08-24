import os
import subprocess
import json
from lobster.tools.base import Tool
from lobster.config import Config
from lobster.tools.registry import ToolRegistry

class CodeGenTool(Tool):
    name = "codegen"
    description = "Write and execute a Python script. Use this for complex logic. If you want to save this as a permanent tool, provide 'tool_name', 'tool_description', and 'tool_parameters'."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "The Python code to execute."},
            "filename": {"type": "string", "description": "A name for the script (e.g., 'calculator.py')."},
            "tool_name": {"type": "string", "description": "Optional: Name to register this as a permanent tool."},
            "tool_description": {"type": "string", "description": "Optional: Description for the permanent tool."},
            "tool_parameters": {"type": "object", "description": "Optional: JSON schema for the permanent tool's inputs."}
        },
        "required": ["code", "filename"]
    }

    def __init__(self, config: Config):
        self.config = config
        self.workspace = os.path.join(os.getcwd(), ".lobster_data", "workspace")
        self.registry = ToolRegistry(config)
        os.makedirs(self.workspace, exist_ok=True)

    def execute(self, code: str, filename: str = "temp_script.py", tool_name: str = None, tool_description: str = None, tool_parameters: dict = None, **kwargs) -> str:
        safe_filename = os.path.basename(filename)
        if not safe_filename.endswith(".py"):
            safe_filename += ".py"
            
        file_path = os.path.join(self.workspace, safe_filename)
        
        try:
            # 1. Write the code
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            # 2. Register if requested
            if tool_name and tool_description:
                params = tool_parameters or {
                    "type": "object", 
                    "properties": {}, 
                    "required": []
                }
                self.registry.register_tool(tool_name, safe_filename, tool_description, params)
                registration_msg = f"\n[SYSTEM] Tool '{tool_name}' has been registered permanently."
            else:
                registration_msg = ""
            
            # 3. Execute the code
            result = subprocess.run(
                ["python", file_path],
                capture_output=True,
                text=True,
                timeout=self.config.command_timeout,
                cwd=self.workspace
            )
            
            output = f"Script '{safe_filename}' executed.{registration_msg}\n"
            if result.stdout: output += f"Output:\n{result.stdout}\n"
            if result.stderr: output += f"Errors:\n{result.stderr}\n"
            output += f"Exit Code: {result.returncode}"
            
            if len(output) > self.config.max_output:
                output = output[:self.config.max_output] + "\n[OUTPUT TRUNCATED]"
                
            return output.strip()
            
        except Exception as e:
            return f"Error executing script: {str(e)}"