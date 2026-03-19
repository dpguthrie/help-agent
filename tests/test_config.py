import os
from agent.config import Settings

def test_settings_defaults():
    settings = Settings()
    assert settings.classifier_model == "claude-haiku-4-5"
    assert settings.executor_model == "claude-sonnet-4-5"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.classifier_temperature == 0.0
    assert settings.executor_temperature == 0.2
    assert settings.executor_max_tokens == 4096
    assert settings.confidence_threshold == 0.3

def test_settings_validation_defaults():
    settings = Settings()
    assert settings.enable_grounding_validation is False
    assert settings.validation_model == "claude-haiku-4-5"
    assert settings.validation_temperature == 0.0

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("EXECUTOR_MODEL", "gpt-4o")
    monkeypatch.setenv("EXECUTOR_TEMPERATURE", "0.5")
    settings = Settings()
    assert settings.executor_model == "gpt-4o"
    assert settings.executor_temperature == 0.5
