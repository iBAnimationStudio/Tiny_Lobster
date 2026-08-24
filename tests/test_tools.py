import unittest
import os
import tempfile
import json

# Import tools using the full package path
from lobster.tools.terminal import TerminalTool, is_dangerous
from lobster.tools.filesystem import FileTool
from lobster.tools.system import SystemInfoTool
from lobster.tools.memory_tool import MemoryTool
from lobster.tools.custom_tool_manager import CustomToolManager
from lobster.memory.facts import FactMemory

class MockConfig:
    command_timeout = 2
    max_output = 1000
    debug = False

class TestTerminalTool(unittest.TestCase):
    def setUp(self):
        self.tool = TerminalTool(MockConfig())

    def test_execute_simple(self):
        result = self.tool.execute(command="echo hello")
        self.assertIn("hello", result)
        self.assertIn("Exit Code: 0", result)

    def test_execute_timeout(self):
        result = self.tool.execute(command="sleep 5")
        self.assertIn("timed out", result)

    def test_is_dangerous(self):
        self.assertTrue(is_dangerous("rm -rf /"))
        self.assertTrue(is_dangerous("ls | rm file"))
        self.assertFalse(is_dangerous("ls -la"))

class TestFileTool(unittest.TestCase):
    def setUp(self):
        self.tool = FileTool(MockConfig())
        self.temp_dir = tempfile.mkdtemp()

    def test_read_write(self):
        path = os.path.join(self.temp_dir, "test.txt")
        self.tool.execute(action="write", path=path, content="hello")
        res = self.tool.execute(action="read", path=path)
        self.assertEqual(res, "hello")

class TestSystemInfoTool(unittest.TestCase):
    def test_execute(self):
        res = SystemInfoTool().execute()
        self.assertIn("os:", res)
        self.assertIn("python_version:", res)

class TestFactMemory(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory for test memory to avoid polluting real data
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
        self.memory = FactMemory()

    def tearDown(self):
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_add_and_get_fact(self):
        self.memory.add_fact("software", "gdrive", "~/go/bin/gdrive")
        facts = self.memory.get_facts("software")
        self.assertEqual(facts["gdrive"], "~/go/bin/gdrive")

    def test_secret_detection_in_memory(self):
        # Memory class itself doesn't block secrets, the Tool does. 
        # This just ensures the memory class stores data correctly.
        self.memory.add_fact("secrets", "test_key", "12345")
        self.assertEqual(self.memory.get_facts("secrets")["test_key"], "12345")

class TestMemoryTool(unittest.TestCase):
    def setUp(self):
        self.tool = MemoryTool(MockConfig())
        # Clear any existing test memory
        self.tool.memory.clear_all()

    def test_add_fact(self):
        res = self.tool.execute(action="add", category="tools", key="git", value="/usr/bin/git")
        self.assertIn("✅ Memory updated", res)
        
        res = self.tool.execute(action="get", category="tools", key="git")
        self.assertIn("/usr/bin/git", res)

    def test_block_secrets(self):
        res = self.tool.execute(action="add", category="auth", key="api_key", value="secret123")
        self.assertIn("Error: Refusing to store potentially sensitive data", res)

    def test_list_facts(self):
        self.tool.execute(action="add", category="env", key="home", value="/data/data/com.termux")
        res = self.tool.execute(action="list")
        self.assertIn("[env]", res)
        self.assertIn("home", res)

class TestCustomToolManager(unittest.TestCase):
    def setUp(self):
        self.tool = CustomToolManager(MockConfig())
        # Ensure clean registry for tests
        self.tool.registry.save_registry([])

    def test_create_and_list(self):
        code = "print('hello from custom tool')"
        res = self.tool.execute(
            action="create", 
            tool_name="test_tool", 
            code=code, 
            description="A test tool",
            parameters_schema={"type": "object", "properties": {}}
        )
        self.assertIn("created and registered", res)
        
        res = self.tool.execute(action="list")
        self.assertIn("test_tool", res)

    def test_execute_custom_tool(self):
        # First create it
        code = "import os, json; args = json.loads(os.environ.get('LOBSTER_TOOL_ARGS', '{}')); print(args.get('msg', 'no msg'))"
        self.tool.execute(
            action="create", 
            tool_name="echo_tool", 
            code=code, 
            description="Echoes a message",
            parameters_schema={"type": "object", "properties": {"msg": {"type": "string"}}}
        )
        
        # Then execute it
        res = self.tool.execute(
            action="execute", 
            tool_name="echo_tool", 
            arguments={"msg": "lobster rocks"}
        )
        self.assertIn("lobster rocks", res)

    def test_delete_tool(self):
        self.tool.execute(
            action="create", 
            tool_name="delete_me", 
            code="print('hi')", 
            description="To be deleted",
            parameters_schema={"type": "object", "properties": {}}
        )
        res = self.tool.execute(action="delete", tool_name="delete_me")
        self.assertIn("removed from registry", res)
        
        res = self.tool.execute(action="list")
        self.assertNotIn("delete_me", res)

if __name__ == "__main__":
    unittest.main()