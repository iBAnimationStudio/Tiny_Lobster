from typing import List, Dict, Any
import yaml
from lobster.config import Config
from lobster.models.base import ModelBackend
from lobster.tools.base import Tool
from lobster.tools.terminal import TerminalTool, is_dangerous
from lobster.tools.filesystem import FileTool
from lobster.tools.system import SystemInfoTool
from lobster.tools.custom_tool_manager import CustomToolManager
from lobster.tools.dynamic import DynamicTool
from lobster.tools.registry import ToolRegistry
from lobster.tools.memory_tool import MemoryTool
from lobster.utils.logging import log_debug
from lobster.utils.loader import load_markdown_file
from lobster.memory.history import HistoryManager
from lobster.memory.facts import FactMemory
from lobster.tools.web import WebTool

class Agent:
    def __init__(self, config: Config, model: ModelBackend):
        self.config = config
        self.model = model
        
        # 1. Initialize Memory Manager & Load History FIRST
        self.history_manager = HistoryManager(config)
        self.history: List[Dict[str, Any]] = self.history_manager.load_history()
        self.model.load_history(self.history)
        
        if self.history:
            print(f"🧠 Loaded {len(self.history)} messages from persistent memory.")
        else:
            print("🧠 Starting with a clean slate.")

        # 2. Initialize Fact Memory
        self.fact_memory = FactMemory()

        # 3. Initialize Tool Registry
        self.tool_registry = ToolRegistry(config)
        
        # 4. Register Base Tools
        self.tools = {
            "terminal": TerminalTool(config),
            "file": FileTool(config),
            "system_info": SystemInfoTool(),
            "web": WebTool(config),
            "custom_tool_manager": CustomToolManager(config),
            "memory": MemoryTool(config)
        }
        
        # 5. Load Custom Tools from Registry
        custom_tools_meta = self.tool_registry.get_custom_tools()
        for meta in custom_tools_meta:
            try:
                dynamic_tool = DynamicTool(config, meta)
                self.tools[dynamic_tool.name] = dynamic_tool
                print(f"🔧 Loaded custom tool: {meta['name']}")
            except Exception as e:
                print(f"[WARN] Failed to load custom tool {meta['name']}: {e}")

        # 6. Load Personality and Rules
        personality = load_markdown_file("lobster/agent/personality.md")
        tool_rules = load_markdown_file("lobster/tools/rules.md")
        
        base_prompt = (
            "You are Lobster, an AI agent running inside Termux on Android.\n\n"
            "TOOL USAGE RULES:\n"
            "1. DIRECT ANSWERS: If you can answer directly, do so. Do NOT call tools unnecessarily.\n"
            "2. MEMORY: Use the 'memory' tool to store important discoveries (installed software, paths, versions).\n"
            "3. CUSTOM TOOLS: Use 'custom_tool_manager' to create, list, update, delete, or execute custom tools.\n"
            "4. TERMUX CONSTRAINTS: No 'sudo', no 'systemctl'. Use 'pkg' and '$PREFIX'.\n"
            "5. SAFETY: Destructive commands require user confirmation.\n"
            "6. CODE STRUCTURE: When creating tools, ensure code reads 'LOBSTER_TOOL_ARGS' from the environment.\n"
        )
        
        self.system_prompt = f"{base_prompt}\n\n{personality}\n\n{tool_rules}"
        print(f"📜 Loaded {len(personality)} chars of personality and {len(tool_rules)} chars of tool rules.")


    def _ask_confirmation(self, command: str) -> bool:
        print(f"\n⚠️  Destructive command detected: {command}")
        resp = input("Allow execution? (y/N): ").strip().lower()
        return resp in ("y", "yes")

    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        if name not in self.tools: 
            return f"Error: Tool '{name}' not found."
        tool = self.tools[name]
        
        # Safety check for terminal commands
        if name == "terminal" and is_dangerous(arguments.get("command", "")):
            if not self._ask_confirmation(arguments["command"]):
                return "Error: Command execution cancelled by user."
        
        log_debug(f"Executing {name}: {arguments}", self.config.debug)
        try:
            return tool.execute(**arguments)
        except Exception as e:
            return f"Error executing tool: {str(e)}"
            

    def run_turn(self, user_input: str) -> str:
        facts = self.fact_memory.get_facts()
        memory_context = ""
        if facts:
            memory_context = "\n\nCURRENT PERSISTENT MEMORY:\n" + yaml.dump(facts, default_flow_style=False)
    
        final_prompt = self.system_prompt + memory_context

        # Update system prompt/tools while keeping previous history intact
        self.model.set_system_context(final_prompt, list(self.tools.values()))
    
        response = self.model.send_message(user_input)
    
        for i in range(self.config.max_iterations):
            log_debug(f"Iteration {i+1}", self.config.debug)
        
            if not response.get("tool_calls"):
                final_text = response.get("text", "").strip() or "No response generated."
                # Save the backend's synced history
                self.history = self.model.history
                self.history_manager.save_history(self.history)
                return final_text
        
            executed_results = []
            for tc in response["tool_calls"]:
                result = self._execute_tool(tc["name"], tc["arguments"])
                executed_results.append({"name": tc["name"], "result": result})
        
            response = self.model.send_tool_results(executed_results)
        
        return "Error: Maximum reasoning iterations reached without a final answer."


    def clear_history(self):
        self.history = []
        self.history_manager.clear_history()
        self.fact_memory.clear_all() # Also clear facts on /clear
        print("Conversation history and persistent memory cleared.")