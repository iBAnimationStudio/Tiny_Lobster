import os
import json
from typing import List, Dict, Any
from lobster.config import Config

class HistoryManager:
    def __init__(self, config: Config):
        self.config = config
        self.memory_dir = os.path.join(os.getcwd(), ".lobster_data")
        self.history_file = os.path.join(self.memory_dir, "history.json")
        os.makedirs(self.memory_dir, exist_ok=True)

    def save_history(self, history: List[Dict[str, Any]]) -> None:
        """Save current conversation history to disk."""
        try:
            # Prune history if it's getting too large (keep last 50 turns)
            max_turns = 50
            if len(history) > max_turns:
                history = history[-max_turns:]
            
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] Could not save history: {e}")

    def load_history(self) -> List[Dict[str, Any]]:
        """Load conversation history from disk."""
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except (json.JSONDecodeError, Exception) as e:
            print(f"[WARN] Could not load history (file may be corrupted): {e}")
            return []

    def clear_history(self) -> None:
        """Delete persistent history file."""
        if os.path.exists(self.history_file):
            os.remove(self.history_file)