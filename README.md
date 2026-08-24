# 🦞 Tiny Lobster

A lightweight, robust, and modular AI agent built from scratch specifically to run inside **Termux** on Android. Inspired by open-source agent architectures, Lobster brings the power of LLMs directly to your mobile terminal with full environment awareness, safe tool execution, and prompt-injection defense.

---

## ✨ Features

- **Termux Native**: Tailored for Android environments using `pkg` and local storage constraints (no `sudo` required).
- **Modular Tooling**: Equipped with built-in tools for:
  - **Terminal Execution**: Safely run shell commands.
  - **Filesystem Management**: Read, write, and inspect local files.
  - **System Info**: Monitor device state, battery, and storage.
  - **Custom Tool Manager**: Dynamically create, execute, and manage custom Python tools at runtime.
  - **Web Tools**: Search and fetch web page contents safely.
- **Robust Security**: Built-in Data-Instruction Separation to defend against indirect prompt injection attacks.
- **Persistent Memory**: Store and retrieve persistent facts across sessions.

---

## 🛠️ Project Structure

```text
├── .lobster_data/          # Workspace files, memory, and custom tools data
├── lobster/                # Core agent source code
├── tests/                  # Test suites
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Environment configuration template
└── README.md               # Project documentation
```

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```sh
   git clone https://github.com/iBAnimationStudio/Tiny_Lobster.git
   cd Tiny_Lobster
   ```

2. **Install Termux dependencies:**
   ```sh
   pkg update && pkg install python git termux-api
   ```

3. **Install Python packages:**
   ```sh
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```sh
   cp .env.example .env
   # Edit .env to add your GEMINI_API_KEY
   nano .env
   ```

5. **Run Lobster:**
   ```sh
   python main.py
   ```

---

## 🧩 Custom Tools

Lobster allows you to create and execute dynamic tools on the fly using the `custom_tool_manager` tool. Custom tools read JSON arguments from the `LOBSTER_TOOL_ARGS` environment variable.

---

## 🛡️ Security & Constraints

- **No Root (`sudo`)**: Operates entirely within standard Termux user permissions.
- **Prompt Injection Defense**: Tool outputs, fetched web pages, and external inputs are treated strictly as **Data**, never as instructions.

---

## 📜 License

Distributed under the GNU GPL3 License. See `LICENSE` for more information.
