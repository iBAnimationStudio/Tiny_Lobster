import os
import json
import subprocess
from lobster.tools.base import Tool
from lobster.tools.registry import ToolRegistry
from lobster.config import Config

class CustomToolManager(Tool):
    name = "custom_tool_manager"
    description = "Manage the entire lifecycle of custom tools: create, execute, list, update, or delete them."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string", 
                "enum": ["create", "execute", "list", "delete", "update"],
                "description": "The action to perform on custom tools."
            },
            "tool_name": {
                "type": "string", 
                "description": "Name of the tool (required for execute, delete, update, and create)."
            },
            "code": {
                "type": "string", 
                "description": "Python code for the tool (required for 'create')."
            },
            "description": {
                "type": "string", 
                "description": "Description of what the tool does (required for 'create' and 'update')."
            },
            "parameters_schema": {
                "type": "object", 
                "description": "JSON schema for tool inputs (required for 'create'). Must include 'type': 'object'."
            },
            "arguments": {
                "type": "object", 
                "description": "Input arguments for the tool (required for 'execute')."
            }
        },
        "required": ["action"]
    }

    def __init__(self, config: Config):
        self.config = config
        self.registry = ToolRegistry(config)
        self.workspace = os.path.join(os.getcwd(), ".lobster_data", "workspace")
        os.makedirs(self.workspace, exist_ok=True)

    def execute(self, action: str, tool_name: str = None, code: str = None, description: str = None, parameters_schema: dict = None, arguments: dict = None, **kwargs) -> str:
        try:
            if action == "create":
                if not all([tool_name, code, description]):
                    return "Error: 'tool_name', 'code', and 'description' are required for creation."
                
                # Ensure parameters_schema is valid
                if not parameters_schema:
                    parameters_schema = {"type": "object", "properties": {}, "required": []}
                if parameters_schema.get("type") != "object":
                    parameters_schema["type"] = "object"

                filename = f"{tool_name}.py"
                file_path = os.path.join(self.workspace, filename)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)
                
                self.registry.register_tool(tool_name, filename, description, parameters_schema)
                return f"✅ Tool '{tool_name}' created and registered successfully."

            elif action == "execute":
                if not tool_name: return "Error: 'tool_name' is required for execution."
                if not arguments: arguments = {}
                
                tools = self.registry.load_registry()
                tool_meta = next((t for t in tools if t["name"] == tool_name), None)
                if not tool_meta: return f"Error: Tool '{tool_name}' not found in registry."
                
                file_path = os.path.join(self.workspace, tool_meta["filename"])
                if not os.path.exists(file_path):
                    return f"Error: Script file '{tool_meta['filename']}' missing from workspace."
                
                env = os.environ.copy()
                env["LOBSTER_TOOL_ARGS"] = json.dumps(arguments)
                
                result = subprocess.run(
                    ["python", file_path],
                    capture_output=True, text=True, timeout=self.config.command_timeout,
                    env=env, cwd=self.workspace
                )
                
                output = f"Executed '{tool_name}'.\n"
                if result.stdout: output += f"Output:\n{result.stdout}\n"
                if result.stderr: output += f"Errors:\n{result.stderr}\n"
                return output.strip()

            elif action == "list":
                tools = self.registry.load_registry()
                if not tools: return "No custom tools registered."
                return "\n".join([f"- **{t['name']}**: {t['description']}" for t in tools])

            elif action == "delete":
                if not tool_name: 
                    return "Error: 'tool_name' is required for deletion."
                
                tools = self.registry.load_registry()
                target_tool = next((t for t in tools if t["name"] == tool_name), None)
                
                if not target_tool: 
                    return f"Error: Tool '{tool_name}' not found."
                
                # 1. Delete physical script file from workspace
                filename = target_tool.get("filename", f"{tool_name}.py")
                file_path = os.path.join(self.workspace, filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        return f"Error deleting script file '{filename}': {str(e)}"
                
                # 2. Remove metadata from registry
                new_tools = [t for t in tools if t["name"] != tool_name]
                self.registry.save_registry(new_tools)
                
                return f"🗑️ Tool '{tool_name}' and script '{filename}' deleted successfully."


            elif action == "update":
                if not tool_name or not description: return "Error: 'tool_name' and 'description' required for update."
                tools = self.registry.load_registry()
                for i, t in enumerate(tools):
                    if t["name"] == tool_name:
                        tools[i]["description"] = description
                        self.registry.save_registry(tools)
                        return f"✏️ Updated description for '{tool_name}'."
                return f"Error: Tool '{tool_name}' not found."

            return f"Error: Unknown action '{action}'."
        except Exception as e:
            return f"Error in CustomToolManager: {str(e)}"