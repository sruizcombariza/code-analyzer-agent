"""Definición del workflow del agente con LangGraph.

Topología (ver openspec/changes/add-code-analyzer-agent/design.md):

    START -> context -> security --[Orquestador]--> refactor -> security
                                  \\--[Orquestador]--> END

El "Orquestador" no es un nodo del grafo que llame al LLM ni lea `code`:
es la función `orchestrator_route`, usada como enrutador condicional tras
el nodo de Seguridad. Lee únicamente `is_valid` e `iteration_count` del
estado compartido para decidir entre reintentar con Refactor o terminar
(máximo `max_iterations` ciclos Seguridad↔Refactor).
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Callable

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from opentelemetry import metrics

from src.agent.state import AgentState

# Ruta por defecto de las reglas de equipo: raíz del repositorio.
DEFAULT_TEAM_RULES_PATH = Path(__file__).resolve().parents[2] / "team-rules.md"

DEFAULT_MODEL = "claude-sonnet-5"

SecurityReviewer = Callable[[str, str], tuple[bool, list[str]]]
Refactorer = Callable[[str, list[str]], str]

# Métrica de coste (FinOps): tokens consumidos por llamada al LLM, con
# atributos `node` (security/refactor) y `type` (input/output) para poder
# desglosar el gasto por sub-agente. Se crea vía proxy: funciona igual si
# `setup_telemetry()` (que fija el MeterProvider real) corre antes o después
# de importar este módulo.
_meter = metrics.get_meter("code_analyzer.agent")
_TOKEN_USAGE_COUNTER = _meter.create_counter(
    name="llm.token.usage",
    unit="{token}",
    description="Tokens consumidos por llamada al LLM, por nodo y tipo (input/output).",
)


def _record_token_usage(node: str, usage) -> None:
    _TOKEN_USAGE_COUNTER.add(usage.input_tokens, {"node": node, "type": "input"})
    _TOKEN_USAGE_COUNTER.add(usage.output_tokens, {"node": node, "type": "output"})


# ---------------------------------------------------------------------------
# Nodo de Contexto: única autoridad sobre `team_rules` / `rules_status`.
# ---------------------------------------------------------------------------
def context_node(state: AgentState, *, rules_path: Path) -> dict:
    if not rules_path.exists():
        return {"team_rules": "", "rules_status": "missing"}

    content = rules_path.read_text(encoding="utf-8").strip()
    if not content:
        return {"team_rules": "", "rules_status": "empty"}

    return {"team_rules": content, "rules_status": "loaded"}


# ---------------------------------------------------------------------------
# Nodo de Seguridad (Zero Trust): única autoridad sobre `is_valid` / `findings`.
# ---------------------------------------------------------------------------
_REVIEW_TOOL = {
    "name": "report_security_review",
    "description": "Reporta el veredicto Zero Trust de la revisión de seguridad del código.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_valid": {
                "type": "boolean",
                "description": "true si el código cumple TODAS las reglas de equipo dadas",
            },
            "findings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Incumplimientos detectados; vacío si is_valid es true",
            },
        },
        "required": ["is_valid", "findings"],
    },
}


def review_code(
    code: str,
    team_rules: str,
    *,
    client=None,
    model: str = DEFAULT_MODEL,
) -> tuple[bool, list[str]]:
    """Contrato de la revisión de seguridad: (code, team_rules) -> (is_valid, findings).

    Zero Trust: el código se trata como no confiable hasta que este veredicto
    se calcula explícitamente contra las reglas dadas.
    """
    from anthropic import Anthropic

    client = client or Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=(
            "Eres el sub-agente de Seguridad de un pipeline de revisión de código "
            "Zero Trust. Evalúa el código EXCLUSIVAMENTE contra las reglas de "
            "equipo proporcionadas. No des por válido nada que no esté "
            "explícitamente verificado contra esas reglas."
        ),
        tools=[_REVIEW_TOOL],
        tool_choice={"type": "tool", "name": "report_security_review"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Reglas de equipo:\n{team_rules}\n\n"
                    f"Código a revisar:\n```\n{code}\n```"
                ),
            }
        ],
    )
    _record_token_usage("security", message.usage)

    tool_use = next(block for block in message.content if block.type == "tool_use")
    result = tool_use.input
    return bool(result["is_valid"]), list(result["findings"])


def security_node(state: AgentState, *, reviewer: SecurityReviewer) -> dict:
    if state["rules_status"] != "loaded":
        return {
            "is_valid": False,
            "findings": [
                "No se pudieron cargar las reglas de equipo "
                f"(rules_status={state['rules_status']!r}); Zero Trust: el "
                "código no puede darse por válido sin reglas contra las "
                "que verificarlo."
            ],
        }

    is_valid, findings = reviewer(state["code"], state["team_rules"])
    return {"is_valid": is_valid, "findings": findings}


# ---------------------------------------------------------------------------
# Nodo de Refactor: única autoridad sobre `code` / `iteration_count`.
# ---------------------------------------------------------------------------
_REFACTOR_TOOL = {
    "name": "return_refactored_code",
    "description": "Devuelve la versión corregida y completa del código.",
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Código corregido completo"},
        },
        "required": ["code"],
    },
}


def refactor_code(
    code: str,
    findings: list[str],
    *,
    client=None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Contrato del refactor: (code, findings) -> nuevo code.

    No decide si el resultado es correcto: esa autoridad sigue siendo
    exclusiva del sub-agente de Seguridad en la siguiente iteración.
    """
    from anthropic import Anthropic

    client = client or Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=(
            "Eres el sub-agente de Refactor. Corrige el código para resolver "
            "EXCLUSIVAMENTE los hallazgos indicados, sin introducir cambios "
            "de comportamiento no relacionados."
        ),
        tools=[_REFACTOR_TOOL],
        tool_choice={"type": "tool", "name": "return_refactored_code"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Hallazgos a corregir:\n- "
                    + "\n- ".join(findings)
                    + f"\n\nCódigo actual:\n```\n{code}\n```"
                ),
            }
        ],
    )
    _record_token_usage("refactor", message.usage)

    tool_use = next(block for block in message.content if block.type == "tool_use")
    return str(tool_use.input["code"])


def refactor_node(state: AgentState, *, refactorer: Refactorer) -> dict:
    new_code = refactorer(state["code"], state["findings"])
    return {"code": new_code, "iteration_count": state["iteration_count"] + 1}


# ---------------------------------------------------------------------------
# Orquestador: enrutador ligero, sin lógica de análisis de código.
# ---------------------------------------------------------------------------
def orchestrator_route(state: AgentState) -> str:
    if state["is_valid"]:
        return END
    if state["iteration_count"] >= state["max_iterations"]:
        return END
    return "refactor"


# ---------------------------------------------------------------------------
# Ensamblado del grafo.
# ---------------------------------------------------------------------------
def build_graph(
    *,
    rules_path: Path | None = None,
    reviewer: SecurityReviewer | None = None,
    refactorer: Refactorer | None = None,
) -> CompiledStateGraph:
    rules_path = rules_path or DEFAULT_TEAM_RULES_PATH
    reviewer = reviewer or review_code
    refactorer = refactorer or refactor_code

    graph = StateGraph(AgentState)
    graph.add_node("context", partial(context_node, rules_path=rules_path))
    graph.add_node("security", partial(security_node, reviewer=reviewer))
    graph.add_node("refactor", partial(refactor_node, refactorer=refactorer))

    graph.set_entry_point("context")
    graph.add_edge("context", "security")
    graph.add_conditional_edges(
        "security",
        orchestrator_route,
        {"refactor": "refactor", END: END},
    )
    graph.add_edge("refactor", "security")

    return graph.compile()
