import os

def load_markdown_file(file_path: str) -> str:
    """Reads a markdown file and returns its content as a string."""
    if not os.path.exists(file_path):
        return ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"[WARN] Could not load {file_path}: {e}")
        return ""