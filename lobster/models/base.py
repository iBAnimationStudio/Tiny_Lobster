from abc import ABC, abstractmethod
from typing import List, Dict, Any
from tools.base import Tool

class ModelBackend(ABC):
    @abstractmethod
    def start_session(self, system_prompt: str, tools: List[Tool]) -> None:
        pass

    @abstractmethod
    def send_message(self, text: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def send_tool_results(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def clear_session(self) -> None:
        pass