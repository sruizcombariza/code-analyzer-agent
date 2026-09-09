"""Definición del estado compartido entre los nodos del grafo (LangGraph).

Es el único canal de comunicación entre nodos (ver design.md de
`add-code-analyzer-agent`, sección "Estado compartido"). Cada campo tiene
un único nodo autorizado a escribirlo; el resto de nodos solo lo leen:

- `team_rules`, `rules_status` -> escritos únicamente por el nodo de Contexto.
- `is_valid`, `findings`       -> escritos únicamente por el nodo de Seguridad
                                   (autoridad Zero Trust exclusiva sobre el veredicto).
- `code`, `iteration_count`    -> escritos únicamente por el nodo de Refactor
                                   una vez arrancado el grafo (la carga inicial
                                   de `code` la hace el punto de entrada, antes
                                   de invocar el grafo).
- `max_iterations`             -> fijado una vez al construir el estado inicial;
                                   ningún nodo lo modifica durante la ejecución.
"""

from typing import Literal, TypedDict

# "pending": el nodo de Contexto todavía no se ha ejecutado.
# "loaded": team-rules.md existe y tiene contenido.
# "missing": team-rules.md no existe en la ruta esperada.
# "empty": team-rules.md existe pero no tiene contenido.
RulesStatus = Literal["pending", "loaded", "missing", "empty"]


class AgentState(TypedDict):
    code: str
    team_rules: str
    rules_status: RulesStatus
    is_valid: bool | None
    findings: list[str]
    iteration_count: int
    max_iterations: int


def initial_state(code: str, *, max_iterations: int = 3) -> AgentState:
    """Construye el estado inicial a partir del código a analizar.

    `is_valid` arranca en `None` (todavía sin veredicto) para distinguir
    "no evaluado" de "evaluado como inválido".
    """
    return AgentState(
        code=code,
        team_rules="",
        rules_status="pending",
        is_valid=None,
        findings=[],
        iteration_count=0,
        max_iterations=max_iterations,
    )
