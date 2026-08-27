import os
import sys
import tempfile
from lobster.config import Config
from lobster.models.gemini import GeminiBackend
from lobster.agent.core import Agent
from lobster.tools.terminal import TerminalTool
from lobster.tools.filesystem import FileTool
from lobster.tools.system import SystemInfoTool
from lobster.tools.base import Tool
from lobster.tools.web import WebTool

class SelfTester:
    def __init__(self):
        self.errors = []

    def _fail(self, component: str, msg: str):
        self.errors.append(f"[{component}] {msg}")
        print(f"❌ FAILED: {component} - {msg}", file=sys.stderr)

    def _pass(self, component: str, msg: str = "OK"):
        print(f"✅ PASSED: {component} - {msg}")

    def run_all(self):
        print("Running Lobster Self-Diagnostics...")
        
        # 1. Configuration Check
        try:
            config = Config()
            self._pass("Config", f"Model: {config.model}, Timeout: {config.command_timeout}s")
        except Exception as e:
            self._fail("Config", str(e))
            return False

        # 2. Workspace Directory Check
        try:
            workspace_files_path = os.path.join(
                os.getcwd(), ".lobster_data", "workspace", "lobsters_files"
            )
            existed = os.path.exists(workspace_files_path)
            os.makedirs(workspace_files_path, exist_ok=True)
            status_msg = "Existing directory verified" if existed else "Created missing directory (.lobster_data/.../lobsters_files)"
            self._pass("Workspace", status_msg)
        except Exception as e:
            self._fail("Workspace", f"Failed to initialize workspace: {str(e)}")
            return False


        # 3. Tool Integrity Check
        try:
            term_tool = TerminalTool(config)
            res = term_tool.execute(command="echo test_lobster")
            if "test_lobster" not in res: raise Exception("Output mismatch")
            self._pass("TerminalTool", "Command execution verified")

            file_tool = FileTool(config)
            temp_path = os.path.join(tempfile.gettempdir(), "lobster_test.txt")
            file_tool.execute(action="write", path=temp_path, content="verify")
            read_res = file_tool.execute(action="read", path=temp_path)
            if read_res != "verify": raise Exception("Read/Write mismatch")
            os.remove(temp_path)
            self._pass("FileTool", "Read/Write operations verified")

            sys_tool = SystemInfoTool()
            info = sys_tool.execute()
            if "python_version" not in info: raise Exception("Missing system info")
            self._pass("SystemInfoTool", "Environment detection verified")
            
            
            web_tool = WebTool(config)
            # Test SSRF block safety
            ssrf_check = web_tool.execute(action="fetch", url="http://127.0.0.1:8080")
            if "blocked" not in ssrf_check.lower() and "prohibited" not in ssrf_check.lower():
                raise Exception("WebTool failed to block local SSRF attempt")
            self._pass("WebTool", "Built-in web subsystem and SSRF validation verified")

        except Exception as e:
            self._fail("Tools", str(e))
            return False

        # 4. Model Connectivity Check (Lightweight)
        try:
            model = GeminiBackend(config)
            
            # Create a dummy tool for the test
            class DummyTool(Tool):
                name = "dummy"
                description = "A dummy tool"
                parameters = {"type": "object", "properties": {}, "required": []}
                def execute(self, **kwargs): return "dummy result"
            
            model.start_session("You are a test assistant.", [DummyTool()])
            response = model.send_message("Say 'pong'")
            
            if "pong" not in response["text"].lower():
                raise Exception(f"Model response unexpected: {response['text']}")
            
            model.clear_session()
            self._pass("GeminiBackend", "API connection and response verified")
        except Exception as e:
            self._fail("GeminiBackend", f"Connection failed: {str(e)}")
            return False

        if self.errors:
            print("\n⚠️  Diagnostics failed. Fix the errors above before running Lobster.")
            return False
        
        print("\n✨ All systems operational. Starting Hina...\n")
        return True
