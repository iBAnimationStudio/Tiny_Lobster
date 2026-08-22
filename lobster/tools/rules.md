# Tool Usage Rules

## Terminal Tool
- Always check if a command exists before running complex scripts.
- Prefer `pkg` over `apt` for package management.
- Never use `sudo` as it is not available in standard Termux.
- If a command output is large, summarize it instead of dumping everything.

---

## File Tool
- When reading files, only read what is necessary to answer the question.
- Be careful with write operations; always confirm the path is correct.
- Prefer relative paths when possible.
- Create any new file(s) inside the directory: `.lobster_data/workspace/lobsters_files/`.

---

## System Info Tool
- Use this tool first if the user asks about the environment, battery, or storage.
- You can also use `termux-api` via the terminal tool. If not available, suggest installing it via `pkg install termux-api`.

---

## Custom Tool Manager
- Use `custom_tool_manager` for ALL custom tool operations (creation, execution, and management).
- **Actions:**
  - `create`: Write Python code and register it. Provide `tool_name`, `code`, `description`, and `parameters_schema`.
  - `execute`: Run a registered tool. Provide `tool_name` and `arguments`.
  - `list`: See all available custom tools.
  - `delete`: Remove a tool from the registry.
  - `update`: Change a tool's description.
- **Code Structure**: When creating tools, ensure the Python code reads input arguments from the environment variable `LOBSTER_TOOL_ARGS` (a JSON string).
  - Example: 
    ```python
    import os, json
    args = json.loads(os.environ.get('LOBSTER_TOOL_ARGS', '{}'))
    city = args.get('city', 'London')
    print(f"Weather in {city}")
    ```
- **Safety**: The agent will ask for permission before deleting tools.

---

## Tool Selection Priority
- Prefer a registered specialized tool when it directly matches the requested task.
- Use built-in tools such as terminal for tasks that do not have a suitable specialized tool.
- Do not bypass an existing specialized tool merely because the same result can be achieved with a generic tool.

### Safety & Best Practices:
- Keep scripts focused on one specific task.
- Always handle missing arguments gracefully in your Python code.
- If a tool fails to execute, debug the error and try again.
- do not try to bypass if user rejects your action. Just return back. 