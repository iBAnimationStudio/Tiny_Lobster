import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config
from models.gemini import GeminiBackend
from agent.core import Agent
from utils.self_test import SelfTester

def main():
    tester = SelfTester()
    if not tester.run_all():
        sys.exit(1)

    try:
        config = Config()
        model = GeminiBackend(config)
        agent = Agent(config, model)
    except Exception as e:
        print(f"Fatal Initialization Error: {e}")
        sys.exit(1)
    
    print("Type /help for commands, /exit to quit.\n")
    
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaving history and exiting...")
            agent.history_manager.save_history(agent.history) # Safety save
            break
            
        if not user_input: continue
            
        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd in ("/exit", "/quit"): 
                agent.history_manager.save_history(agent.history) # Safety save
                print("Goodbye!"); break
            elif cmd == "/clear": agent.clear_history()
            elif cmd == "/help": print("Commands: /help, /clear, /status, /model, /memory, /exit")
            elif cmd == "/status": print(f"Model: {config.model}\nMax Iter: {config.max_iterations}\nTimeout: {config.command_timeout}s")
            elif cmd == "/model": print(f"Current model: {config.model}")
            elif cmd == "/memory": 
                count = len(agent.history)
                print(f"Persistent memory active. {count} messages stored in ~/.lobster/history.json")
            else: print("Unknown command.")
            continue
            
        print("🦞 thinking...")
        try:
            response = agent.run_turn(user_input)
            print(f"\nlobster> {response}\n")
        except Exception as e:
            print(f"\nError: {str(e)}\n")

if __name__ == "__main__":
    main()