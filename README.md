# 🦞 Lobster: Modular AI Agent for Termux

A lightweight, modular AI agent designed to run directly inside Termux on Android.

## Installation

1. Install dependencies:
```sh
   pkg update && pkg install python git
   pip install -r requirements.txt
```

2. Configure:
```sh
   cp .env.example .env
   # Edit .env to add your GEMINI_API_KEY
```

3. Run:
```sh
   python lobster/main.py
```

## Features
- Modular tool system (Terminal, Filesystem, System Info)
- Gemini backend with configurable model
- Safety checks for destructive commands
- Self-diagnostic startup verification
