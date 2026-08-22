from typing import List, Dict, Any
from config import Config
from models.base import ModelBackend
from tools.base import Tool
from tools.terminal import TerminalTool, is_dangerous
from tools.filesystem import FileTool
from tools.system import SystemInfoTool
from tools.codegen import CodeGenTool
from tools.dynamic import DynamicTool
from tools.registry import ToolRegistry
from utils.logging import log_debug
from utils.loader import load_markdown_file
from memory.history import HistoryManager

class Agent:
    def __init__(self, config: Config, model: ModelBackend):
        self.config = config
        self.model = model
        
        # 1. Initialize Memory Manager & Load History
        self.history_manager = HistoryManager(config)
        self.history: List[Dict[str, Any]] = self.history_manager.load_history()
        
        if self.history:
            print(f"🧠 Loaded {len(self.history)} messages from persistent memory.")
        else:
            print("🧠 Starting with a clean slate.")

        # 2. Initialize Tool Registry and Load Custom Tools
        self.tool_registry = ToolRegistry(config)
        
        # Base Tools
        self.tools = {
            "terminal": TerminalTool(config),
            "file": FileTool(config),
            "system_info": SystemInfoTool(),
            "codegen": CodeGenTool(config)
        }
        
        # Load Custom Tools from Registry
        custom_tools_meta = self.tool_registry.get_custom_tools()
        for meta in custom_tools_meta:
            try:
                dynamic_tool = DynamicTool(config, meta)
                self.tools[dynamic_tool.name] = dynamic_tool
                print(f"🔧 Loaded custom tool: {meta['name']}")
            except Exception as e:
                print(f"[WARN] Failed to load custom tool {meta['name']}: {e}")

        # 3. LOAD INSTRUCTIONS FROM MARKDOWN FILES
        personality = load_markdown_file("lobster/agent/personality.md")
        tool_rules = load_markdown_file("lobster/tools/rules.md")
        
        # Base technical constraints (kept minimal in code, detailed in rules.md)
        base_prompt = (
            "You are Lobster, an AI agent running inside Termux on Android. "
            "Follow the specific personality and tool rules provided below strictly."
        )
        
        # Combine all prompts
        self.system_prompt = f"{base_prompt}\n\n{personality}\n\n{tool_rules}"
        
        # Debug: Print how much instruction was loaded
        print(f"📜 Loaded {len(personality)} chars of personality and {len(tool_rules)} chars of tool rules.")

    def _ask_confirmation(self, command: str) -> bool:
        print(f"\n⚠️  Destructive command detected: {command}")
        resp = input("Allow execution? (y/N): ").strip().lower()
        return resp in ("y", "yes")

    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        if name not in self.tools: 
            return f"Error: Tool '{name}' not found."
        tool = self.tools[name]
        
        if name == "terminal" and is_dangerous(arguments.get("command", "")):
            if not self._ask_confirmation(arguments["command"]):
                return "Error: Command execution cancelled by user."
        
        log_debug(f"Executing {name}: {arguments}", self.config.debug)
        try:
            return tool.execute(**arguments)
        except Exception as e:
            return f"Error executing tool: {str(e)}"

    def run_turn(self, user_input: str) -> str:
        self.model.start_session(self.system_prompt, list(self.tools.values()))
        response = self.model.send_message(user_input)
        
        for i in range(self.config.max_iterations):
            log_debug(f"Iteration {i+1}", self.config.debug)
            
            if not response["tool_calls"]:
                final_text = response["text"] or "No response generated."
                
                self.history.append({"role": "user", "parts": [{"text": user_input}]})
                self.history.append({"role": "model", "parts": [{"text": final_text}]})
                
                self.history_manager.save_history(self.history)
                
                self.model.clear_session()
                return final_text
            
            tool_call_log = {
                "role": "assistant", 
                "type": "tool_call", 
                "tools": response["tool_calls"]
            }
            self.history.append(tool_call_log)
            
            executed_results = []
            for tc in response["tool_calls"]:
                result = self._execute_tool(tc["name"], tc["arguments"])
                executed_results.append({"name": tc["name"], "result": result})
                
                result_log = {
                    "role": "tool", 
                    "type": "tool_result", 
                    "name": tc["name"], 
                    "result": result
                }
                self.history.append(result_log)
                
                log_debug(f"Tool '{tc['name']}' result: {result[:100]}...", self.config.debug)
            
            response = self.model.send_tool_results(executed_results)
            
        self.model.clear_session()
        return "Error: Maximum reasoning iterations reached without a final answer."

    def clear_history(self):
        self.history = []
        self.history_manager.clear_history()
        print("Conversation history cleared from memory and disk.")