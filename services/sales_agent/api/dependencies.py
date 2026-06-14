"""Dependency composition for the sales-agent API."""

from functools import lru_cache

from services.sales_agent.config import get_settings
from services.sales_agent.infrastructure.adk_runtime import SalesAgentRuntime


@lru_cache
def get_runtime() -> SalesAgentRuntime:
    return SalesAgentRuntime(get_settings())
