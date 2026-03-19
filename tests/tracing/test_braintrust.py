from unittest.mock import MagicMock, patch
from tracing.braintrust import TracingManager


def test_tracing_manager_creates_session_span():
    with patch("tracing.braintrust.init_logger") as mock_init:
        mock_logger = MagicMock()
        mock_init.return_value = mock_logger
        mock_span = MagicMock()
        mock_logger.start_span.return_value = mock_span

        manager = TracingManager(project="test-project", api_key="test")
        session_span = manager.start_session("session-123")

        mock_logger.start_span.assert_called_once()
        assert session_span is not None


def test_tracing_manager_noop_without_api_key():
    manager = TracingManager(project="test", api_key="")
    session_span = manager.start_session("session-123")
    turn_span = session_span.start_span(name="turn.0")
    turn_span.log(output={"test": True})
    turn_span.end()
