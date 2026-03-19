from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ConversationState:
    goal_progress: str = "not_started"  # not_started, advancing, stalled, achieved, abandoned
    frustration: float = 0.0  # 0.0 to 1.0
    turns_taken: int = 0
    should_end: bool = False
    end_reason: str | None = None  # goal_achieved, frustrated, max_turns, gave_up
    next_behavior: str = "start_conversation"  # hint for user sim
