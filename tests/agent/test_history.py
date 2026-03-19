from agent.models import Message
from agent.history import truncate_history


def test_short_history_unchanged():
    msgs = [Message(role="user", content="hi"), Message(role="assistant", content="hello")]
    result = truncate_history(msgs, max_tokens=8000, min_turns=4)
    assert len(result) == 2


def test_long_history_truncated():
    msgs = []
    for i in range(50):
        msgs.append(Message(role="user", content=f"Message number {i} " * 100))
        msgs.append(Message(role="assistant", content=f"Response number {i} " * 100))
    result = truncate_history(msgs, max_tokens=2000, min_turns=4)
    assert len(result) < len(msgs)
    assert len(result) >= 8


def test_preserves_most_recent_turns():
    msgs = []
    for i in range(20):
        msgs.append(Message(role="user", content=f"msg-{i}"))
        msgs.append(Message(role="assistant", content=f"resp-{i}"))
    result = truncate_history(msgs, max_tokens=500, min_turns=4)
    assert result[-1].content == "resp-19"
    assert result[-2].content == "msg-19"
