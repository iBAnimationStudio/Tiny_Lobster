from lobster.tools.base import Tool
from lobster.memory.facts import FactMemory # FIXED: Changed from memory.facts to lobster.memory.facts
from lobster.config import Config

class MemoryTool(Tool):
    name = "memory"
    description = "Manage persistent memory facts. Use this to store important discoveries like installed software paths, versions, or environment configurations."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "get", "delete", "list"]},
            "category": {"type": "string", "description": "Category of the fact (e.g., 'software', 'paths', 'env')."},
            "key": {"type": "string", "description": "Key for the fact (e.g., 'gdrive')."},
            "value": {"type": "string", "description": "Value to store (required for 'add')."}
        },
        "required": ["action"]
    }

    def __init__(self, config: Config):
        self.config = config
        self.memory = FactMemory()

    def execute(self, action: str, category: str = None, key: str = None, value: str = None, **kwargs) -> str:
        try:
            if action == "add":
                if not all([category, key, value]):
                    return "Error: 'category', 'key', and 'value' are required for 'add'."
                # Simple secret detection
                sensitive_words = ["key", "secret", "token", "password", "auth"]
                if any(word in key.lower() or word in value.lower() for word in sensitive_words):
                    return "Error: Refusing to store potentially sensitive data."
                
                self.memory.add_fact(category, key, value)
                return f"✅ Memory updated: {category}.{key} = {value}"
            
            elif action == "get":
                if not category: return "Error: 'category' is required for 'get'."
                facts = self.memory.get_facts(category)
                if not facts: return f"No facts found in category '{category}'."
                if key:
                    return f"{category}.{key}: {facts.get(key, 'Not found')}"
                return "\n".join([f"{k}: {v}" for k, v in facts.items()])
            
            elif action == "list":
                facts = self.memory.get_facts()
                if not facts: return "Memory is empty."
                result = []
                for cat, items in facts.items():
                    result.append(f"[{cat}]")
                    for k, v in items.items():
                        result.append(f"  - {k}: {v}")
                return "\n".join(result)
            
            elif action == "delete":
                if not all([category, key]):
                    return "Error: 'category' and 'key' are required for 'delete'."
                self.memory.delete_fact(category, key)
                return f"🗑️ Deleted {category}.{key}"
            
            return f"Error: Unknown action '{action}'."
        except Exception as e:
            return f"Error managing memory: {str(e)}"