from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from agent.models import SessionState


@dataclass
class ToolResult:
    status: str
    output: Any
    latency_ms: float = 0.0


class Tool(ABC):
    name: str
    description: str
    parameters: dict

    @abstractmethod
    async def execute(self, params: dict, session: SessionState | None) -> ToolResult:
        ...
