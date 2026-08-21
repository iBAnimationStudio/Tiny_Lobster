import os
import json
from typing import List, Dict, Any
from config import Config

class HistoryManager:
    def __init__(self, config: Config):
        self.config = config
        # Use $HOME environment variable which is standard in Termux
        self.memory_dir = os.path.join(os.environ.get("HOME", "."), ".lobster")
        self.history_file = os.path.join(self.memory_dir, "history.json")
        
        # Ensure directory exists
        os.makedirs(self.memory_dir, exist_ok=True)

    def save_history(self, history: List[Dict[str, Any]]) -> None:
        """Save current conversation history to disk."""
        try:
            # Prune history if it's getting too large to save tokens on next load
            # We keep the last 50 messages (25 turns)
            max_messages = 500
            if len(history) > max_messages:
                history = history[-max_messages:]
            
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