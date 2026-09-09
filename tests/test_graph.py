from langgraph.graph import END

from src.agent.graph import build_graph, context_node, orchestrator_route, refactor_node, security_node
from src.agent.state import AgentState, initial_state


def _state(**overrides) -> AgentState:
    state = initial_state("code")
    state.update(overrides)
    return state


class TestContextNode:
    """Cubre el requisito de carga de contexto (specs/code-analyzer/spec.md)."""

    def test_loaded(self, tmp_path):
        rules_file = tmp_path / "team-rules.md"
        rules_file.write_text("Regla 1: no hardcodear secretos.")

        result = context_node(_state(), rules_path=rules_file)

        assert result["rules_status"] == "loaded"
        assert "Regla 1" in result["team_rules"]

    def test_missing_file(self, tmp_path):
        rules_file = tmp_path / "does-not-exist.md"

        result = context_node(_state(), rules_path=rules_file)

        assert result == {"team_rules": "", "rules_status": "missing"}

    def test_empty_file(self, tmp_path):
        rules_file = tmp_path / "team-rules.md"
        rules_file.write_text("   \n")

        result = context_node(_state(), rules_path=rules_file)

        assert result == {"team_rules": "", "rules_status": "empty"}


class TestOrchestratorRoute:
    """El Orquestador enruta solo con `is_valid` / `iteration_count`.

    El caso "primera pasada tras cargar el contexto" es la arista fija
    context -> security (no pasa por esta función) y queda cubierto en
    TestGraphEndToEnd, donde el reviewer solo recibe control tras el nodo
    de Contexto.
    """

    def test_invalid_with_iterations_left_routes_to_refactor(self):
        state = _state(is_valid=False, iteration_count=1, max_iterations=3)
        assert orchestrator_route(state) == "refactor"

    def test_valid_routes_to_end(self):
        state = _state(is_valid=True, iteration_count=0, max_iterations=3)
        assert orchestrator_route(state) == END

    def test_max_iterations_reached_routes_to_end(self):
        state = _state(is_valid=False, iteration_count=3, max_iterations=3)
        assert orchestrator_route(state) == END


class TestNodeFieldOwnership:
    """Cada nodo solo debe devolver los campos de los que es autor."""

    def test_context_node_only_writes_team_rules_and_rules_status(self, tmp_path):
        rules_file = tmp_path / "team-rules.md"
        rules_file.write_text("regla")

        result = context_node(_state(), rules_path=rules_file)

        assert set(result.keys()) == {"team_rules", "rules_status"}

    def test_security_node_only_writes_is_valid_and_findings(self):
        state = _state(rules_status="loaded", team_rules="regla")

        result = security_node(state, reviewer=lambda code, rules: (False, ["hallazgo"]))

        assert set(result.keys()) == {"is_valid", "findings"}

    def test_security_node_rejects_when_rules_not_loaded_without_calling_reviewer(self):
        state = _state(rules_status="missing")
        called = False

        def reviewer(code, rules):
            nonlocal called
            called = True
            return True, []

        result = security_node(state, reviewer=reviewer)

        assert result["is_valid"] is False
        assert result["findings"]
        assert called is False

    def test_refactor_node_only_writes_code_and_iteration_count(self):
        state = _state(is_valid=False, findings=["f1"], iteration_count=0, code="old")

        result = refactor_node(state, refactorer=lambda code, findings: "new code")

        assert set(result.keys()) == {"code", "iteration_count"}
        assert result["code"] == "new code"
        assert result["iteration_count"] == 1


class TestGraphEndToEnd:
    def _graph(self, tmp_path, reviewer, refactorer):
        rules_file = tmp_path / "team-rules.md"
        rules_file.write_text("No hardcodear secretos.")
        return build_graph(rules_path=rules_file, reviewer=reviewer, refactorer=refactorer)

    def test_resolves_within_iteration_limit(self, tmp_path):
        calls = {"n": 0}

        def reviewer(code, team_rules):
            assert team_rules  # el nodo de Contexto ya corrió antes que Seguridad
            calls["n"] += 1
            if calls["n"] == 1:
                return False, ["contiene un secreto hardcodeado"]
            return True, []

        def refactorer(code, findings):
            return "code sin secretos"

        graph = self._graph(tmp_path, reviewer, refactorer)
        result = graph.invoke(initial_state("code con secreto"))

        assert result["is_valid"] is True
        assert result["iteration_count"] == 1
        assert result["code"] == "code sin secretos"

    def test_stops_at_max_iterations_when_never_valid(self, tmp_path):
        def reviewer(code, team_rules):
            return False, ["sigue sin cumplir la regla"]

        def refactorer(code, findings):
            return code + "!"

        graph = self._graph(tmp_path, reviewer, refactorer)
        result = graph.invoke(initial_state("code con secreto", max_iterations=3))

        assert result["is_valid"] is False
        assert result["iteration_count"] == 3
