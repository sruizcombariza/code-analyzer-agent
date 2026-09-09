"""Punto de entrada de la aplicación (CLI o API).

Inicializa la telemetría (OpenTelemetry/OpenInference), carga un código de
prueba con un error intencionado y ejecuta el flujo completo del grafo de
LangGraph definido en `src/agent/graph.py`.
"""

from pathlib import Path

from dotenv import load_dotenv

from src.agent.graph import build_graph
from src.agent.state import initial_state
from src.telemetry.setup import setup_telemetry

# Código de prueba con un error intencionado (secreto hardcodeado), pensado
# para violar la regla 1 de `team-rules.md`. Vive en su propio archivo para
# que sea fácil de localizar, leer y modificar sin tocar la lógica del agente.
SAMPLE_CODE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample_code_with_error.py"


def main() -> None:
    load_dotenv()
    setup_telemetry()

    sample_code = SAMPLE_CODE_PATH.read_text(encoding="utf-8")

    graph = build_graph()
    result = graph.invoke(initial_state(sample_code))

    print(f"is_valid: {result['is_valid']}")
    print(f"iteration_count: {result['iteration_count']}/{result['max_iterations']}")
    print(f"findings: {result['findings']}")
    print("code final:")
    print(result["code"])


if __name__ == "__main__":
    main()
