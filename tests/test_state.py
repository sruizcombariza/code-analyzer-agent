from src.agent.state import initial_state


def test_initial_state_defaults():
    state = initial_state("print('hola')")

    assert state["code"] == "print('hola')"
    assert state["team_rules"] == ""
    assert state["rules_status"] == "pending"
    assert state["is_valid"] is None
    assert state["findings"] == []
    assert state["iteration_count"] == 0
    assert state["max_iterations"] == 3


def test_initial_state_custom_max_iterations():
    state = initial_state("code", max_iterations=5)

    assert state["max_iterations"] == 5
