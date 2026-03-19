from __future__ import annotations
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://sfdc:sfdc@localhost:5432/sfdc"
    braintrust_api_key: str = ""
    gateway_base_url: str = "https://gateway.braintrust.dev"

    classifier_model: str = "claude-haiku-4-5"
    executor_model: str = "claude-sonnet-4-5"
    embedding_model: str = "text-embedding-3-small"

    classifier_temperature: float = 0.0
    executor_temperature: float = 0.2
    executor_max_tokens: int = 4096

    enable_grounding_validation: bool = False
    validation_model: str = "claude-haiku-4-5"
    validation_temperature: float = 0.0

    confidence_threshold: float = 0.3
    history_token_limit: int = 8000
    history_min_turns: int = 4

    model_config = {"env_prefix": "", "case_sensitive": False}
