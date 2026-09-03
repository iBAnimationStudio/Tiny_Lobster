import logging
from typing import List, Dict, Any, Generator
from google import genai
from google.genai import types
from lobster.models.base import ModelBackend
from lobster.tools.base import Tool
from lobster.config import Config

logging.getLogger("google.genai").setLevel(logging.INFO)


class GeminiBackend(ModelBackend):
    def __init__(self, config: Config):
        self.config = config
        self.client = genai.Client(api_key=config.api_key)
        self.model_name = config.model
        self._history: List[types.Content] = []
        self.system_prompt: str = ""
        self.raw_tools: List[Tool] = []

    @property
    def history(self) -> List[Dict[str, Any]]:
        serialized = []
        for item in self._history:
            if hasattr(item, "model_dump"):
                dumped = item.model_dump(mode="json", exclude_none=True)
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

    def _get_tools_config(self) -> Any:
        """Properly format function declarations for the genai SDK."""
        if not self.raw_tools:
            return None
        declarations = []
        for t in self.raw_tools:
            declarations.append(
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters=t.parameters if hasattr(t, "parameters") else None
                )
            )
        return [types.Tool(function_declarations=declarations)]

    def start_session(self, system_prompt: str, tools: List[Tool]) -> None:
        self.system_prompt = system_prompt
        self.raw_tools = tools or []
        self._history = []

    def set_system_context(self, system_prompt: str, tools: List[Tool]) -> None:
        self.system_prompt = system_prompt
        self.raw_tools = tools or []

    def load_history(self, history: List[Any]) -> None:
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
        try:
            tools = self._get_tools_config()
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt or None,
                tools=tools
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=self._history,
                config=config
            )
        except Exception as e:
            print(f"[ERROR] GenAI SDK Call Failed: {e}")
            raise Exception(f"Gemini SDK Error: {str(e)}")

        result = {"text": "", "tool_calls": []}

        if response and response.candidates:
            candidate = response.candidates[0]
            if candidate.content:
                self._history.append(candidate.content)

                for part in candidate.content.parts or []:
                    if getattr(part, "text", None):
                        result["text"] += part.text
                    elif getattr(part, "function_call", None):
                        fc = part.function_call
                        args = dict(fc.args) if fc.args else {}
                        result["tool_calls"].append({
                            "name": fc.name,
                            "arguments": args
                        })

        if not result["text"] and not result["tool_calls"]:
            print(f"[WARN] Empty response from Gemini. Candidate: {response.candidates if response else 'None'}")

        return result

    def clear_session(self) -> None:
        self._history = []
