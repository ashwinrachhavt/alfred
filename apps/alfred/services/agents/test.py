from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

load_dotenv()

# Create your Agent
agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    instructions="You are a helpful AI assistant.",
    markdown=True,
)

# Run
agent.print_response("What is artificial intelligence?", stream=True)
