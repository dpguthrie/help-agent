from __future__ import annotations
import tiktoken
from agent.models import Message


def truncate_history(
    messages: list[Message],
    max_tokens: int = 8000,
    min_turns: int = 4,
) -> list[Message]:
    """Truncate conversation history to fit within token budget.

    Always preserves the most recent `min_turns` turns.
    Removes oldest messages first.
    Never splits tool call / tool result pairs (would cause API errors).
    Filters out orphaned tool messages that lost their pair during truncation.
    """
    if not messages:
        return messages

    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    min_messages = min_turns * 2

    def count_tokens(msgs: list[Message]) -> int:
        return sum(len(enc.encode(m.content)) for m in msgs)

    # If already within budget, just validate pairs
    if count_tokens(messages) <= max_tokens:
        return _filter_orphaned_tool_messages(list(messages))

    if len(messages) <= min_messages:
        return _filter_orphaned_tool_messages(list(messages))

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

    result = list(reversed(kept)) + protected
    return _filter_orphaned_tool_messages(result)


def _filter_orphaned_tool_messages(messages: list[Message]) -> list[Message]:
    """Remove tool result messages that don't have a matching tool_calls message,
    and assistant messages with tool_calls that don't have matching tool results.
    This prevents API errors from orphaned tool call/result pairs after truncation."""
    if not messages:
        return messages

    # Collect all tool_call_ids from assistant messages with tool_calls
    available_tool_use_ids: set[str] = set()
    for msg in messages:
        if msg.role == "assistant" and msg.tool_calls:
            for tc in msg.tool_calls:
                tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                if tc_id:
                    available_tool_use_ids.add(tc_id)

    # Collect all tool_call_ids from tool result messages
    available_tool_result_ids: set[str] = set()
    for msg in messages:
        if msg.role == "tool" and msg.tool_call_id:
            available_tool_result_ids.add(msg.tool_call_id)

    filtered = []
    for msg in messages:
        # Keep tool results only if their tool_use exists
        if msg.role == "tool" and msg.tool_call_id:
            if msg.tool_call_id in available_tool_use_ids:
                filtered.append(msg)
            # else: orphaned tool result, skip it
            continue

        # Keep assistant messages with tool_calls only if at least one result exists
        if msg.role == "assistant" and msg.tool_calls:
            has_matching_result = False
            for tc in msg.tool_calls:
                tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                if tc_id in available_tool_result_ids:
                    has_matching_result = True
                    break
            if has_matching_result:
                filtered.append(msg)
            # else: orphaned tool_calls with no results, skip
            continue

        # Keep everything else (user, regular assistant)
        filtered.append(msg)

    return filtered
