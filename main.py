import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from lobster.config import Config
from lobster.models.gemini import GeminiBackend
from lobster.agent.core import Agent
from lobster.utils.self_test import SelfTester
from lobster.task.manager import TaskWorker

def main():
    tester = SelfTester()
    if not tester.run_all():
        sys.exit(1)

    try:
        config = Config()
        model = GeminiBackend(config)
        agent = Agent(config, model)
        
        # Start background task scheduler (1 task/min rate limit)
        worker = TaskWorker(agent.task_manager, agent.run_turn)
        worker.start()
        print("⏱️ Task Scheduler daemon active (1 task/min rate limit).")
    except Exception as e:
        print(f"Fatal Initialization Error: {e}")
        sys.exit(1)
    
    print("Type /help for commands, /exit to quit.\n")
    
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down Task Scheduler and saving history...")
            worker.stop()
            agent.history_manager.save_history(agent.history)
            break
            
        if not user_input:
            continue
            
        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd in ("/exit", "/quit"):
                worker.stop()
                agent.history_manager.save_history(agent.history)
                print("Goodbye!")
                break
            elif cmd == "/clear":
                agent.clear_history()
            elif cmd == "/help":
                print("Commands: /help, /tasks, /clear, /status, /model, /memory, /exit")
            elif cmd == "/tasks":
                tasks = agent.task_manager.list_tasks()
                if not tasks:
                    print("No tasks registered.")
                else:
                    print(f"Registered Tasks ({len(tasks)}):")
                    for t in tasks:
                        print(f" - [{t['id']}] ({t['status']}) P:{t['priority']} U:{t['urgency']} AI:{t['is_task_need_ai']} | {t['description']}")
            elif cmd == "/status":
                print(f"Model: {config.model}\nMax Iter: {config.max_iterations}\nTimeout: {config.command_timeout}s")
            elif cmd == "/model":
                print(f"Current model: {config.model}")
            elif cmd == "/memory":
                count = len(agent.history)
                print(f"Persistent memory active. {count} messages stored in .lobster_data/history.json")
            else:
                print("Unknown command.")
            continue
            
        print("🦞 thinking...")
        try:
            response = agent.run_turn(user_input)
            print(f"\nlobster> {response}\n")
        except Exception as e:
            print(f"\nError: {str(e)}\n")

if __name__ == "__main__":
    main()
