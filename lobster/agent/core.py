from typing import List, Dict, Any
from config import Config
from models.base import ModelBackend
from tools.base import Tool
from tools.terminal import TerminalTool, is_dangerous
from tools.filesystem import FileTool
from tools.system import SystemInfoTool
from utils.logging import log_debug
from utils.loader import load_markdown_file # NEW IMPORT
from memory.history import HistoryManager

class Agent:
    def __init__(self, config: Config, model: ModelBackend):
        self.config = config
        self.model = model
        
        # Initialize Memory Manager
        self.history_manager = HistoryManager(config)
        self.history: List[Dict[str, Any]] = self.history_manager.load_history()
        
        self.tools = {
            "terminal": TerminalTool(config),
            "file": FileTool(config),
            "system_info": SystemInfoTool()
        }
        
        # LOAD PERSONALITY AND RULES
        personality = load_markdown_file("personality.md")
        tool_rules = load_markdown_file("lobster/tools/rules.md")
        
        base_prompt = (
            "You are Lobster, an AI agent running inside Termux on Android.\n\n"
            "TOOL USAGE RULES:\n"
            "1. DIRECT ANSWERS: If you can answer directly, do so. Do NOT call tools unnecessarily.\n"
            "2. FACTUAL CHECKS: Use tools for environment checks, file ops, or commands. Never guess.\n"
            "3. TERMUX CONSTRAINTS: No 'sudo', no 'systemctl'. Use 'pkg' and '$PREFIX'.\n"
            "4. SAFETY: Destructive commands require user confirmation.\n"
        )
        
        # Combine all prompts
        self.system_prompt = f"{base_prompt}\n\n{personality}\n\n{tool_rules}"

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
            
            executed_results = []
            for tc in response["tool_calls"]:
                result = self._execute_tool(tc["name"], tc["arguments"])
                executed_results.append({"name": tc["name"], "result": result})
                log_debug(f"Tool '{tc['name']}' result: {result[:100]}...", self.config.debug)
            
            response = self.model.send_tool_results(executed_results)
            
        self.model.clear_session()
        return "Error: Maximum reasoning iterations reached without a final answer."

    def clear_history(self):
        self.history = []
        self.history_manager.clear_history()
        print("Conversation history cleared from memory and disk.")