import os
import yaml
from typing import Dict, Any, List
from lobster.config import Config

class FactMemory:
    def __init__(self):
        self.data_dir = os.path.join(os.getcwd(), ".lobster_data")
        self.memory_file = os.path.join(self.data_dir, "facts.yaml")
        os.makedirs(self.data_dir, exist_ok=True)
        self.facts = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
        return {}

    def save(self):
        with open(self.memory_file, 'w') as f:
            yaml.dump(self.facts, f, default_flow_style=False)

    def add_fact(self, category: str, key: str, value: Any):
        if category not in self.facts:
            self.facts[category] = {}
        self.facts[category][key] = value
        self.save()

    def get_facts(self, category: str = None) -> Dict[str, Any]:
        if category:
            return self.facts.get(category, {})
        return self.facts

    def delete_fact(self, category: str, key: str):
        if category in self.facts and key in self.facts[category]:
            del self.facts[category][key]
            self.save()

    def clear_all(self):
        self.facts = {}
        self.save()