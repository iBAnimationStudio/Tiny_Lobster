import sys

def log_debug(msg: str, debug: bool):
    if debug:
        print(f"[DEBUG] {msg}", file=sys.stderr)
