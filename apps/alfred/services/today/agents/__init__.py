"""Explicit agent imports - registers each agent with DailyPipeline at load time.

Adding a new agent? Import it here. The decorator
``@DailyPipeline.register`` fires on module import, which happens when
this file is imported (which :meth:`DailyPipeline.run` does at the start
of every run).
"""

from alfred.services.today.agents.carryover_agent import CarryoverAgent
from alfred.services.today.agents.digest_agent import DigestAgent

__all__ = ["CarryoverAgent", "DigestAgent"]
