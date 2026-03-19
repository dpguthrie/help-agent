from __future__ import annotations
import tiktoken
from agent.models import Message


def truncate_history(
    messages: list[Message],
    max_tokens: int = 8000,
    min_turns: int = 4,
) -> list[Message]:
    if not messages:
        return messages

    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    min_messages = min_turns * 2

    def count_tokens(msgs: list[Message]) -> int:
        return sum(len(enc.encode(m.content)) for m in msgs)

    if count_tokens(messages) <= max_tokens:
        return list(messages)

    if len(messages) <= min_messages:
        return list(messages)

    protected = messages[-min_messages:]
    candidates = messages[:-min_messages]

    remaining_budget = max_tokens - count_tokens(protected)
    kept = []
    for msg in reversed(candidates):
        msg_tokens = len(enc.encode(msg.content))
        if remaining_budget >= msg_tokens:
            kept.append(msg)
            remaining_budget -= msg_tokens
        else:
            break

    return list(reversed(kept)) + protected
