import os

class Config:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model = os.environ.get("LOBSTER_MODEL", "gemini-1.5-flash-latest")
        self.max_iterations = int(os.environ.get("LOBSTER_MAX_ITERATIONS", "8"))
        self.command_timeout = int(os.environ.get("LOBSTER_COMMAND_TIMEOUT", "30"))
        self.max_output = int(os.environ.get("LOBSTER_MAX_OUTPUT", "4000"))
        self.debug = os.environ.get("LOBSTER_DEBUG", "0") == "1"
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
