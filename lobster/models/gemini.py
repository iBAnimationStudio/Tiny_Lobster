import os
import json
from datetime import datetime
from typing import List, Dict, Any
from google import genai
from google.genai import types
from lobster.models.base import ModelBackend
from lobster.tools.base import Tool
from lobster.config import Config
from lobster.utils.logging import log_debug

DEBUG_LOG_PATH = os.path.join(os.getcwd(), ".lobster_data", "gemini_debug.log")

class GeminiBackend(ModelBackend):
    def __init__(self, config: Config):
        self.config = config
        self.client = genai.Client(api_key=config.api_key)
        self.model_name = config.model
        self._history: List[types.Content] = []
        self.system_prompt: str = ""
        self.tools_config: List[Any] = []

    @property
    def history(self) -> List[Dict[str, Any]]:
        """Returns JSON-serializable history for HistoryManager and WebUI."""
        serialized = []
        for item in self._history:
            if hasattr(item, "model_dump"):
                dumped = item.model_dump(mode="json", exclude_none=True)
                # Keep compatibility with existing format
                if "parts" in dumped:
                    serialized.append({
                        "role": dumped.get("role", "user"),
                        "parts": dumped["parts"]
                    })
            elif isinstance(item, dict):
                serialized.append(item)
        return serialized

    @history.setter
    def history(self, value: List[Any]):
        self.load_history(value)

    def _log_api_traffic(self, direction: str, data: Any):
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            if hasattr(data, "model_dump"):
                formatted_json = json.dumps(data.model_dump(mode="json"), indent=2, ensure_ascii=False)
            elif isinstance(data, (dict, list)):
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            else:
                formatted_json = str(data)
        except Exception:
            formatted_json = str(data)

        log_entry = f"\n{'='*25} [{timestamp}] GEMINI {direction} {'='*25}\n{formatted_json}\n"

        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception:
            pass

        log_debug(f"Gemini API {direction} logged to file", self.config.debug)

    def _format_tools(self, tools: List[Tool]) -> List[Any]:
        return [
            {
                "function_declarations": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters
                    }
                    for t in tools
                ]
            }
        ]
        
    def start_session(self, system_prompt: str, tools: List[Tool]) -> None:
        self.system_prompt = system_prompt
        self.tools_config = self._format_tools(tools)
        self._history = []

    def set_system_context(self, system_prompt: str, tools: List[Tool]) -> None:
        self.system_prompt = system_prompt
        self.tools_config = self._format_tools(tools)

    def load_history(self, history: List[Any]) -> None:
        """Convert persisted raw dict history back to types.Content objects."""
        self._history = []
        for item in history:
            if isinstance(item, types.Content):
                self._history.append(item)
            elif isinstance(item, dict):
                try:
                    self._history.append(types.Content.model_validate(item))
                except Exception:
                    pass

    def send_message(self, text: str) -> Dict[str, Any]:
        self._history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=text)]
            )
        )
        return self._call_api()

    def send_tool_results(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        parts = []
        for tr in tool_results:
            parts.append(
                types.Part.from_function_response(
                    name=tr["name"],
                    response={"result": tr["result"]}
                )
            )
        self._history.append(types.Content(role="user", parts=parts))
        return self._call_api()

    def _call_api(self) -> Dict[str, Any]:
        self._log_api_traffic("REQUEST", {
            "contents": self.history,
            "tools": self.tools_config,
            "system_instruction": self.system_prompt
        })

        try:
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                tools=self.tools_config
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=self._history,
                config=config
            )

            self._log_api_traffic("RESPONSE", response)

        except Exception as e:
            self._log_api_traffic("SDK ERROR", str(e))
            raise Exception(f"Gemini SDK Error: {str(e)}")

        result = {"text": "", "tool_calls": []}

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content:
                self._history.append(candidate.content)

                for part in candidate.content.parts:
                    if getattr(part, "text", None):
                        result["text"] += part.text
                    elif getattr(part, "function_call", None):
                        fc = part.function_call
                        args = dict(fc.args) if fc.args else {}
                        result["tool_calls"].append({
                            "name": fc.name,
                            "arguments": args
                        })

        return result

    def clear_session(self) -> None:
        self._history = []
