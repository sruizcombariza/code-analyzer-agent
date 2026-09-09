## Why

Los LLMs son motores no deterministas: la misma entrada de código puede producir distintos veredictos o distintos refactors entre ejecuciones. Para llevar un agente autónomo de análisis/refactor a un contexto productivo hace falta demostrar, con evidencia técnica, que ese comportamiento puede gobernarse — que las decisiones son trazables, que el coste (tokens) es medible, y que existe una frontera de seguridad (Zero Trust) que ningún cambio de código puede saltarse sin pasar validación explícita.

Esta PoC aporta esa evidencia construyendo un "arnés" (Harness Engineering, en línea con el Tech Radar de Thoughtworks) alrededor de un LLM: un orquestador determinista en código convencional (LangGraph) que delega el razonamiento a sub-agentes especializados, pero que él mismo nunca interpreta código ni decide directamente sobre su seguridad.

## What Changes

- Se añade el **Agente Analizador de Código**: un grafo de LangGraph con 1 Orquestador y 3 sub-agentes (Contexto, Seguridad, Refactor).
- El Orquestador actúa como enrutador ligero: solo lee banderas de estado (p. ej. `is_valid`) y decide la siguiente arista con `add_conditional_edges`. No contiene lógica de análisis de código ni llama al LLM directamente.
- El sub-agente **Contexto** carga las reglas del equipo desde un archivo local `team-rules.md` (sin Vector DB / sin RAG) y las añade al estado compartido.
- El código a analizar es, en esta PoC, un snippet/archivo de prueba fijo con un error intencionado, cargado por el punto de entrada (`src/main.py`) al iniciar el grafo — no se integra con un repositorio Git, un diff ni una selección de archivos en esta fase.
- El sub-agente **Seguridad** aplica un enfoque Zero Trust: llama a la API del LLM para revisar el código de entrada contra las reglas cargadas, y es el único nodo con autoridad para escribir el veredicto (`is_valid`) y el detalle de fallos en el estado.
- El sub-agente **Refactor** solo se invoca cuando `is_valid = false`; modifica el código para intentar corregir los fallos reportados y devuelve el control al Orquestador.
- Se introduce un límite duro de iteraciones (máx. 3 ciclos Seguridad→Refactor) para acotar coste y evitar bucles infinitos ante código que el LLM no logra corregir.
- El estado global del grafo (`AgentState`) queda definido como el contrato único de comunicación entre nodos — ningún nodo se comunica con otro salvo a través de ese estado.
- Esta fase es de diseño puro (OpenSpec `propose`): no se escribe código Python ni configuración Docker; esos entregables se abordan en fases posteriores del plan de acción (`PLAN_ACCION_CODE.md`).

## Capabilities

### New Capabilities
- `code-analyzer`: comportamiento de orquestación y enrutamiento del flujo multi-agente (Orquestador + Contexto + Seguridad + Refactor) que analiza código contra reglas de equipo y lo refactoriza de forma acotada cuando falla la validación.

### Modified Capabilities
_Ninguna — no existen specs previas en este repositorio._

## Impact

- **Código afectado (futuro, fuera de esta fase):** `src/agent/state.py`, `src/agent/graph.py`, `src/main.py`.
- **Configuración nueva:** archivo local `team-rules.md` en la raíz o en `src/agent/` (a fijar en `design.md`) como única fuente de reglas de contexto.
- **Dependencias:** LangGraph como motor de orquestación; API de Claude (Anthropic) invocada exclusivamente desde el sub-agente de Seguridad.
- **Observabilidad:** este diseño deja puntos de instrumentación explícitos (transiciones de nodo, veredicto de Seguridad, nº de iteraciones) que la fase de telemetría (OpenTelemetry / OTel Collector) consumirá más adelante — no se implementa en este cambio.
- **Sin impacto en:** infraestructura Docker existente (`docker/`), que se aborda en una fase de aplicación posterior y separada.
