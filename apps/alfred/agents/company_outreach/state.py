from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import BaseMessage


class OutreachState(TypedDict):
    messages: list[BaseMessage]

