import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agent.classifier import TopicClassifier
from agent.config import Settings
from agent.models import ClassifierResult, Message
from topics.registry import get_default_registry


@pytest.fixture
def classifier():
    settings = Settings(braintrust_api_key="test-key")
    return TopicClassifier(settings=settings, topic_registry=get_default_registry())


@pytest.mark.asyncio
async def test_classify_knowledge_query(classifier):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"topic_id": "knowledge_faq", "confidence": 0.95})

    with patch.object(classifier._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("How do I reset my Salesforce password?", [])
    assert result.topic_id == "knowledge_faq"
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_classify_case_creation(classifier):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"topic_id": "case_creation", "confidence": 0.92})

    with patch.object(classifier._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("I want to create a case", [])
    assert result.topic_id == "case_creation"


@pytest.mark.asyncio
async def test_classify_low_confidence_defaults_to_off_topic(classifier):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"topic_id": "knowledge_faq", "confidence": 0.1})

    with patch.object(classifier._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("asdfghjkl", [])
    assert result.topic_id == "off_topic"


@pytest.mark.asyncio
async def test_classify_includes_history(classifier):
    history = [Message(role="user", content="I have an issue"), Message(role="assistant", content="How can I help?")]
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"topic_id": "case_creation", "confidence": 0.8})

    with patch.object(classifier._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response) as mock_create:
        await classifier.classify("create a case", history)
    call_args = mock_create.call_args
    messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
    user_msg = [m for m in messages if m["role"] == "user"][0]
    assert "I have an issue" in user_msg["content"]
