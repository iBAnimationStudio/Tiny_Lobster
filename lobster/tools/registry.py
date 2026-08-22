import os
import json
import importlib.util
from typing import List, Dict, Any
from config import Config

class ToolRegistry:
    def __init__(self, config: Config):
        self.config = config
        self.data_dir = os.path.join(os.getcwd(), ".lobster_data")
        self.workspace = os.path.join(self.data_dir, "workspace")
        self.registry_file = os.path.join(self.data_dir, "custom_tools.json")
        os.makedirs(self.workspace, exist_ok=True)
        
        # Ensure registry exists
        if not os.path.exists(self.registry_file):
            self.save_registry([])

    def load_registry(self) -> List[Dict[str, Any]]:
        try:
            with open(self.registry_file, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def save_registry(self, tools: List[Dict[str, Any]]):
        with open(self.registry_file, "w") as f:
            json.dump(tools, f, indent=2)

    def register_tool(self, name: str, filename: str, description: str, parameters: Dict[str, Any]):
        registry = self.load_registry()
        # Update or add
        for i, tool in enumerate(registry):
            if tool["name"] == name:
                registry[i] = {"name": name, "filename": filename, "description": description, "parameters": parameters}
                self.save_registry(registry)
                return
        registry.append({"name": name, "filename": filename, "description": description, "parameters": parameters})
        self.save_registry(registry)

    def get_custom_tools(self):
        """Return list of registered custom tools."""
        return self.load_registry()