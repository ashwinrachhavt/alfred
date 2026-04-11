"""Chat node -- conversational LLM responses without tool use.

Handles greetings, questions, opinions, and general conversation.
No tools are invoked; the model answers directly from its training
data and the conversation history.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage

from alfred.agents.state import AlfredState
from alfred.core.llm_factory import get_chat_model
from alfred.core.settings import LLMProvider, settings

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
    if settings.app_env in {"test", "ci"} or (
        settings.llm_provider == LLMProvider.openai and not settings.openai_api_key
    ):
        content = str(getattr(state["messages"][-1], "content", "")).strip()
        response = AIMessage(content=f"Alfred heard: {content}")
    else:
        model = get_chat_model(model=state.get("model") or "gpt-4.1-mini")
        messages = [CHAT_SYSTEM_PROMPT, *state["messages"]]
        response = await model.ainvoke(messages)

    return {
        "messages": [response],
        "final_response": response.content,
        "phase": "done",
    }
