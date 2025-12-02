import os
import sys


def main():
    print("Checking Agno environment...")
    try:
        from agno.agent import Agent

        print("Successfully imported Agno.")
    except ImportError as e:
        print(f"Failed to import Agno: {e}")
        sys.exit(1)

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("OPENAI_API_KEY not set. Skipping agent run.")
        return

    print("Running trivial agent test...")
    try:
        from alfred.core.llm import make_chat_model

        # Create a trivial agent using the factory
        model = make_chat_model()
        agent = Agent(model=model, markdown=True)
        # Run a one-line prompt
        response = agent.run("Hello, just checking if you are alive.")
        print(f"Agent response: {response.content}")
    except Exception as e:
        print(f"Agent run failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
