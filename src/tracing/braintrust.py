from __future__ import annotations
from typing import Any


class NoopSpan:
    def start_span(self, **kwargs) -> NoopSpan:
        return NoopSpan()

    def log(self, **kwargs) -> None:
        pass

    def end(self) -> None:
        pass

    def export(self) -> str:
        return ""


def init_logger(**kwargs):
    from braintrust import init_logger as _init_logger
    return _init_logger(**kwargs)


class TracingManager:
    def __init__(self, project: str, api_key: str):
        self._project = project
        self._api_key = api_key
        self._logger = None

        if api_key:
            try:
                self._logger = init_logger(project=project, api_key=api_key)
            except Exception:
                pass

    def start_session(self, session_id: str) -> Any:
        if self._logger is None:
            return NoopSpan()
        return self._logger.start_span(name="session", session_id=session_id)
