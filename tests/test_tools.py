import unittest
import os
import tempfile
from tools.terminal import TerminalTool, is_dangerous
from tools.filesystem import FileTool
from tools.system import SystemInfoTool

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

if __name__ == "__main__":
    unittest.main()
