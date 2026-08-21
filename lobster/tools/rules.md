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

## System Info Tool
- Use this tool first if the user asks about the environment, battery, or storage.