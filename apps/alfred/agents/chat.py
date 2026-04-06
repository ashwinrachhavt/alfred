"""Chat node -- conversational LLM responses without tool use.

Handles greetings, questions, opinions, and general conversation.
No tools are invoked; the model answers directly from its training
data and the conversation history.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from alfred.agents.state import AlfredState
from alfred.core.settings import settings

CHAT_SYSTEM_PROMPT = SystemMessage(content="""\
You are Alfred, an intelligent knowledge assistant. You help the user think \
clearly, answer questions, discuss ideas, and provide thoughtful perspectives.

Guidelines:
- Answer questions directly and conversationally.
- Draw on the conversation history for context.
- Be concise but thorough. No filler.
- If the user asks about their knowledge base, notes, or zettels, tell them \
  you can search it — suggest they ask you to "search my knowledge base for X".
- Do NOT create, modify, or delete any zettels/cards/notes unless the user \
  explicitly asks you to.
- You are not a generic chatbot. You are a knowledge companion — bring depth, \
  make connections, challenge assumptions when appropriate.\
""")


async def chat(state: AlfredState) -> dict:
    """Direct conversational response — no tools, just the LLM."""
    model = ChatOpenAI(
        model="gpt-4.1-mini",
        api_key=(settings.openai_api_key.get_secret_value() if settings.openai_api_key else None),
        base_url=settings.openai_base_url,
    )

    messages = [CHAT_SYSTEM_PROMPT, *state["messages"]]
    response = await model.ainvoke(messages)

    return {
        "messages": [response],
        "final_response": response.content,
        "phase": "done",
    }
