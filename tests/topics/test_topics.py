from topics.registry import TopicRegistry, get_default_registry


def test_default_registry_has_11_topics():
    registry = get_default_registry()
    assert len(registry.all()) == 11


def test_default_registry_topic_ids():
    registry = get_default_registry()
    ids = {t.id for t in registry.all()}
    assert ids == {
        "knowledge_faq", "case_creation", "agent_transfer", "case_management", "off_topic",
        "inappropriate_content", "ambiguous_question", "reverse_engineering", "prompt_injection",
        "appointment_scheduling", "contract_renewals",
    }


def test_safety_topics_have_no_tools():
    registry = get_default_registry()
    for topic_id in ["inappropriate_content", "ambiguous_question", "reverse_engineering", "prompt_injection"]:
        topic = registry.get(topic_id)
        assert topic.tools == [], f"{topic_id} should have no tools"


def test_classification_prompt_safety_first():
    registry = get_default_registry()
    prompt = registry.classification_prompt()
    # Safety topics should appear before functional topics
    pi_pos = prompt.index("prompt_injection")
    ic_pos = prompt.index("inappropriate_content")
    kf_pos = prompt.index("knowledge_faq")
    assert pi_pos < kf_pos, "prompt_injection should be before knowledge_faq"
    assert ic_pos < kf_pos, "inappropriate_content should be before knowledge_faq"


def test_get_topic_by_id():
    registry = get_default_registry()
    topic = registry.get("knowledge_faq")
    assert topic is not None
    assert topic.name == "Knowledge & FAQ"
    assert "search_knowledge" in topic.tools


def test_knowledge_topic_has_instructions():
    registry = get_default_registry()
    topic = registry.get("knowledge_faq")
    assert len(topic.instructions) > 50


def test_case_creation_tools():
    registry = get_default_registry()
    topic = registry.get("case_creation")
    assert "get_user_context" in topic.tools
    assert "create_case" in topic.tools
    assert "emit_event" in topic.tools


def test_off_topic_has_no_tools():
    registry = get_default_registry()
    topic = registry.get("off_topic")
    assert topic.tools == []


def test_classification_prompt():
    registry = get_default_registry()
    prompt = registry.classification_prompt()
    assert "knowledge_faq" in prompt
    assert "case_creation" in prompt
    assert "off_topic" in prompt
