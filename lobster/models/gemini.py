import urllib.request
import urllib.error
import json
from typing import List, Dict, Any
from .base import ModelBackend
from tools.base import Tool
from config import Config

class GeminiBackend(ModelBackend):
    def __init__(self, config: Config):
        self.api_key = config.api_key
        self.model_name = config.model
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        self.history: List[Dict[str, Any]] = []
        self.system_prompt: str = ""
        self.tools_config: List[Dict[str, Any]] = []

    def _format_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "functionDeclarations": [
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
        self.history = []

    def send_message(self, text: str) -> Dict[str, Any]:
        self.history.append({"role": "user", "parts": [{"text": text}]})
        return self._call_api()

    def send_tool_results(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        parts = []
        for tr in tool_results:
            parts.append({
                "functionResponse": {
                    "name": tr["name"],
                    "response": {"result": tr["result"]}
                }
            })
        self.history.append({"role": "user", "parts": parts})
        return self._call_api()

    def _call_api(self) -> Dict[str, Any]:
        payload = {
            "contents": self.history,
            "tools": self.tools_config,
            "systemInstruction": {
                "parts": [{"text": self.system_prompt}]
            }
        }
        
        data = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}?key={self.api_key}"
        
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise Exception(f"API Error {e.code}: {error_body}")
        except Exception as e:
            raise Exception(f"Network Error: {str(e)}")
            
        result = {"text": "", "tool_calls": []}
        
        candidates = response_data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            for part in parts:
                if "text" in part:
                    result["text"] += part["text"]
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    tc = {
                        "name": fc.get("name"),
                        "arguments": fc.get("args", {})
                    }
                    # CRITICAL: Preserve thought_signature exactly as the API returns it
                    if "thought_signature" in fc:
                        tc["thought_signature"] = fc["thought_signature"]
                    
                    result["tool_calls"].append(tc)
                    
                    # CRITICAL: Add the model's functionCall to history so the 
                    # thought_signature is preserved for the next API turn.
                    self.history.append({"role": "model", "parts": [part]})
                    
        return result

    def clear_session(self) -> None:
        self.history = []
        self.system_prompt = ""
        self.tools_config = []