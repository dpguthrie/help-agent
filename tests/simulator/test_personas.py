from simulator.personas import PERSONA_TEMPLATES, PersonaTemplate, get_random_persona


def test_persona_templates_not_empty():
    assert len(PERSONA_TEMPLATES) >= 10


def test_all_templates_have_required_fields():
    for p in PERSONA_TEMPLATES:
        assert p.id
        assert p.role
        assert p.goal_type in ("knowledge", "case_creation", "transfer", "case_management", "mixed")
        assert 0.0 <= p.patience <= 1.0
        assert p.language


def test_get_random_persona():
    p = get_random_persona()
    assert isinstance(p, PersonaTemplate)


def test_get_random_persona_filtered():
    p = get_random_persona(pattern="edge_*")
    assert p.id.startswith("edge_")


def test_edge_case_personas_exist():
    edge = [p for p in PERSONA_TEMPLATES if p.id.startswith("edge_")]
    assert len(edge) >= 3
