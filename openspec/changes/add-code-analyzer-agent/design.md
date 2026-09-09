## Context

El repositorio ya tiene el esqueleto de carpetas (`src/agent/state.py`, `src/agent/graph.py`, `src/main.py`, `src/telemetry/setup.py`, `tests/`, `docker/`), todos como stubs `TODO`. `.env` declara `ANTHROPIC_API_KEY` y `OTLP_ENDPOINT`, lo que fija el proveedor LLM de esta PoC (Claude, vía la API de Anthropic) y confirma que la telemetría se diseñará para exportar vía OTLP en una fase posterior — ninguna de las dos cosas se implementa en este cambio. Ver `proposal.md` — Why para la motivación completa.

Esta fase es puramente de diseño (OpenSpec `propose`): el resultado es el contrato de comportamiento del grafo, no su código.

## Goals / Non-Goals

**Goals:**
- Definir un único esquema de estado compartido (`AgentState`) como el exclusivo canal de comunicación entre nodos del grafo.
- Fijar la separación de responsabilidades: el Orquestador solo enruta leyendo banderas; cada sub-agente es el único autor de una porción concreta del estado.
- Acotar el ciclo Seguridad → Refactor con un límite duro de iteraciones, para que el coste en tokens y el tiempo de ejecución sean predecibles.
- Dejar costuras de instrumentación explícitas (qué transición, qué veredicto, qué iteración) para que la fase de telemetría (OpenTelemetry) pueda instrumentarlas sin rediseñar el grafo.

**Non-Goals:**
- No se diseña ni implementa RAG / Vector DB — el sub-agente de Contexto lee un único archivo plano `team-rules.md`.
- No se implementa la instrumentación OpenTelemetry en sí (se referencia como punto de extensión futuro).
- No se diseña la infraestructura Docker/observabilidad (`docker-compose.yml`, OTel Collector) — corresponde a una fase de `apply` separada.
- No se elige aquí un modelo LLM concreto ni se ajustan prompts; solo se define el contrato de entrada/salida que el sub-agente de Seguridad debe cumplir al invocar la API.
- No se diseña ingesta de código desde un repositorio real (Git, diffs, selección de archivos) ni análisis multi-archivo; el código de entrada es un único snippet/string fijo, cargado por el punto de entrada.

## Decisions

### 1. El Orquestador es un router puro sobre el estado, no un nodo de razonamiento
El grafo usa `add_conditional_edges` desde el Orquestador, cuya función de enrutamiento lee exclusivamente banderas ya calculadas (`is_valid`, `iteration_count`) y decide entre `security`, `refactor` o `END`. El Orquestador nunca invoca al LLM ni inspecciona el código fuente directamente.
- **Alternativa considerada:** un supervisor que también revisa el código antes de rutear (patrón "supervisor con criterio propio"). Se descarta porque duplicaría la autoridad de decisión de Seguridad y rompería la trazabilidad de "qué nodo decidió qué" — el objetivo central de la PoC es poder señalar un único punto (Seguridad) como origen del veredicto.

### 2. `team-rules.md` como fuente de contexto, sin Vector DB
El sub-agente de Contexto lee un archivo Markdown local en cada ejecución y vuelca su contenido íntegro al estado (`team_rules: str`).
- **Alternativa considerada:** RAG con Vector DB (como sugiere el diagrama general del README). Se descarta explícitamente para esta PoC: el volumen de reglas de un equipo cabe en una ventana de contexto sin necesidad de recuperación semántica, y evita introducir una dependencia de infraestructura (embeddings, base vectorial) que no aporta valor de gobernanza aquí. Queda como evolución futura documentada, no como decisión pendiente.

### 3. Zero Trust: Seguridad es la única autoridad de escritura sobre el veredicto
Ningún otro nodo puede fijar `is_valid` ni el listado de fallos (`findings`). El sub-agente de Seguridad recibe `code` + `team_rules` del estado, invoca la API del LLM con un contrato de salida estructurado (veredicto + lista de hallazgos), y es el único que escribe esos campos.
- **Alternativa considerada:** dejar que el Orquestador interprete la respuesta libre del LLM y decida él mismo si es válida. Se descarta porque mezclaría responsabilidad de negocio (interpretar seguridad) con responsabilidad de control de flujo, y porque dificultaría auditar "qué agente tomó la decisión de seguridad" en las trazas.

### 4. Límite duro de iteraciones (máx. 3 ciclos Seguridad↔Refactor)
El estado lleva un contador `iteration_count`. El Orquestador termina el flujo (aunque `is_valid` siga en `false`) al alcanzar el máximo, marcando el resultado final como "no resuelto automáticamente" en vez de reintentar indefinidamente.
- **Alternativa considerada:** sin límite, confiando en que el LLM converja. Se descarta por riesgo de coste no acotado (tokens) y por ser precisamente el tipo de comportamiento no determinista que esta PoC busca gobernar — un límite explícito es en sí mismo evidencia de Harness Engineering.

### 5. Refactor solo se invoca condicionalmente, y solo modifica `code`
El sub-agente de Refactor recibe `code` + `findings` y devuelve una nueva versión de `code`. No re-evalúa seguridad ni fija `is_valid` — eso vuelve a ser responsabilidad exclusiva de Seguridad en la siguiente iteración del ciclo.
- **Alternativa considerada:** que Refactor también autoevalúe si su corrección es correcta (optimización, menos llamadas al LLM). Se descarta porque eliminaría la garantía Zero Trust de que todo código modificado por IA vuelve a pasar por el mismo control de Seguridad antes de aceptarse.

### 6. El código de entrada es un snippet de prueba fijo, cargado por el entrypoint
`src/main.py` inicializa `AgentState.code` con un snippet/archivo de ejemplo con un error intencionado (según `PLAN_ACCION_CODE.md`, Fase 4) antes de invocar el grafo. Ni el Orquestador ni ningún sub-agente descubren, listan o leen archivos de un repositorio.
- **Alternativa considerada:** que el sub-agente de Contexto (o un nuevo nodo) reciba una ruta de archivo o un diff de Git y lo lea del disco. Se descarta para esta PoC porque el objetivo es validar el patrón de gobernanza (trazabilidad, coste, Zero Trust) con la menor superficie posible; la ingesta desde un repositorio real es una evolución natural pero añade complejidad (selección de archivos, contexto parcial, permisos de lectura) que no aporta señal adicional al experimento.

## Risks / Trade-offs

- **[Riesgo]** El LLM de Seguridad puede ser inconsistente entre ejecuciones (falso negativo/positivo) al no haber determinismo garantizado. → **Mitigación:** el límite de iteraciones acota el impacto máximo, y el diseño deja el veredicto y los `findings` en el estado para que la fase de telemetría los haga trazables y auditables por ejecución.
- **[Riesgo]** `team-rules.md` sin versión ni validación de formato podría no cargar o quedar vacío. → **Mitigación:** el sub-agente de Contexto debe tratar la ausencia/vacío del archivo como una condición de estado explícita (ver spec), nunca como un fallo silencioso que Seguridad interprete como "sin reglas = todo válido".
- **[Riesgo]** Acoplar Seguridad y Refactor al mismo proveedor/API de LLM puede amplificar un fallo del proveedor a todo el flujo. → **Mitigación:** fuera de alcance de esta PoC (un único proveedor es aceptable para validar el patrón); se documenta como evolución futura, no como decisión pendiente de esta fase.
- **[Trade-off]** No usar RAG/Vector DB simplifica la PoC pero no escala a bases de reglas grandes. Aceptado deliberadamente (ver Decisión 2) porque el objetivo de esta fase es la gobernanza del flujo, no la escalabilidad del contexto.

## Migration Plan

No aplica: es una capacidad nueva sobre un esqueleto de proyecto vacío, sin usuarios ni datos previos que migrar. El plan de construcción incremental (infraestructura → estado/grafo → telemetría → dockerización) ya está descrito en `PLAN_ACCION_CODE.md` y se traduce a `tasks.md` en esta misma fase de planificación.
