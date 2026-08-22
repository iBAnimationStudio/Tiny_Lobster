# Tool Usage Rules

## Terminal Tool
- Always check if a command exists before running complex scripts.
- Prefer `pkg` over `apt` for package management.
- Never use `sudo` as it is not available in standard Termux.
- If a command output is large, summarize it instead of dumping everything.

## File Tool
- When reading files, only read what is necessary to answer the question.
- Be careful with write operations; always confirm the path is correct.
- Prefer relative paths when possible.
- Create any new file(s) inside the directory: `.lobster_data/workspace/lobsters_files/`.

## System Info Tool
- Use this tool first if the user asks about the environment, battery, or storage.
- You can also use `termux-api` via the terminal tool. If not available, suggest installing it via `pkg install termux-api`.

## Codegen Tool (Custom Tool Creator)
- Use this for tasks that require loops, complex math, data processing, or creating permanent tools.
- Do NOT use this for simple shell commands like `ls`, `cat`, or `pwd`.
- Ensure the code is valid Python 3.

### How to Create a Permanent Tool:
1. **Check Registry First**: Before creating a tool, check if a similar tool already exists in your registered tools list to avoid duplicates.
2. **Write the Code**: Your Python script should read input arguments from the environment variable `LOBSTER_TOOL_ARGS` (which is a JSON string).
   - Example: 
```python
     import os, json
     args = json.loads(os.environ.get('LOBSTER_TOOL_ARGS', '{}'))
     # Use args['param_name'] to get inputs
     print("Result here")
```
3. **Register the Tool**: When calling the `codegen` tool, you MUST provide these additional fields to save it permanently:
   - `tool_name`: A unique, snake_case name (e.g., `crypto_tracker`).
   - `tool_description`: A clear explanation of what the tool does.
   - `tool_parameters`: A JSON schema describing the inputs (e.g., `{"type": "object", "properties": {"city": {"type": "string"}}}`).
4. **Storage**: The script will be saved in `.lobster_data/workspace/` and registered in `.lobster_data/custom_tools.json`.

### Safety & Best Practices:
- Keep scripts focused on one specific task.
- Always handle missing arguments gracefully in your Python code.
- If a tool fails to execute, debug the error and try again.