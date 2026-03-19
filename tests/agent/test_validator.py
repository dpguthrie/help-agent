import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agent.validator import GroundingValidator, ValidationResult
from agent.config import Settings


@pytest.fixture
def validator():
    settings = Settings(braintrust_api_key="test-key")
    return GroundingValidator(settings=settings)


@pytest.mark.asyncio
async def test_validate_grounded(validator):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "result": "GROUNDED",
        "reason": "Response is supported by tool results.",
        "sources": ["tool_call.search_knowledge[0]"],
    })

    with patch.object(validator._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await validator.validate(
            response="To reset your password, go to Settings.",
            tool_results=[{"tool": "search_knowledge", "output": "password reset steps"}],
            conversation_context=[{"role": "user", "content": "How do I reset my password?"}],
        )
    assert result.is_grounded is True
    assert "GROUNDED" in result.reason or "supported" in result.reason.lower()


@pytest.mark.asyncio
async def test_validate_not_grounded(validator):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "result": "NOT_GROUNDED",
        "reason": "Response contains claims not supported by tool results.",
        "sources": [],
    })

    with patch.object(validator._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await validator.validate(
            response="You should delete your org and start over.",
            tool_results=[],
            conversation_context=[{"role": "user", "content": "How do I fix this?"}],
        )
    assert result.is_grounded is False


@pytest.mark.asyncio
async def test_validate_handles_bad_json(validator):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not json"

    with patch.object(validator._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await validator.validate(
            response="anything", tool_results=[], conversation_context=[],
        )
    # Should default to grounded on parse failure (fail-open)
    assert result.is_grounded is True
