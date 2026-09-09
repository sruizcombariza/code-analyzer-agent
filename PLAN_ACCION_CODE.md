## 📋 Plan de Ejecución con Claude Code

Este plan utiliza la metodología **OpenSpec** para acordar la arquitectura antes de la implementación, seguido de fases iterativas para construir la infraestructura, los agentes y la telemetría. 

### Fase 1: Diseño y Contrato (OpenSpec Propose)
Obligamos a Claude a definir el contrato de la arquitectura considerando la estructura existente, sin escribir una sola línea de código fuente.

> **Prompt 1 (Terminal):** 
> Contexto: Estamos construyendo una prueba de concepto inspirada en el Tech Radar de Thoughtworks sobre "Harness Engineering" y "Observabilidad de IA". El objetivo es aportar evidencia técnica para gobernar el comportamiento no determinista de los LLMs. La estructura base del proyecto (`src/`, `docker/`, `tests/`, etc.) ya está creada en este repositorio.
> 
> Actúa como Arquitecto de Software y utiliza el framework OpenSpec (fase `propose`) para diseñar el Agente Analizador de Código. Crea los artefactos de diseño en `openspec/changes/add-code-analyzer-agent/`.
> 
> La arquitectura debe usar LangGraph con 1 Orquestador y 3 Sub-agentes:
> 1. Contexto (lee reglas desde un archivo `team-rules.md` local, sin Vector DB).
> 2. Seguridad (Zero Trust, llama a la API del LLM para revisar el código contra las reglas y actualiza el estado).
> 3. Refactor (modifica el código si hay fallos).
> *Nota Arquitectónica:* El Orquestador NO analiza código directamente, actúa como un enrutador ligero que lee las banderas de estado (ej. `is_valid`) generadas por el agente de Seguridad.
> 
> Genera: `proposal.md`, `design.md`, `specs/code-analyzer/spec.md` (escenarios GIVEN/WHEN/THEN) y `tasks.md`. 
> REGLA ESTRICTA: NO escribas código de implementación en Python ni Docker. Presenta un resumen y espera mi validación explícita.

### Fase 2: Infraestructura de Observabilidad
Una vez apruebes el diseño, construimos la base para recopilar métricas y trazas.

> **Prompt 2 (Terminal):** 
> Basado en las tareas de OpenSpec, pasa a la fase `apply` para la infraestructura. Crea el archivo `docker/docker-compose.yml` y la configuración `docker/otel-collector-config.yaml`.
> 
> Incluye los servicios: OpenTelemetry Collector (recibiendo por OTLP), Jaeger (puerto UI 16686) y Prometheus (puerto UI 9090). Asegúrate de que el Collector enruta correctamente las trazas y métricas. 

### Fase 3: Construcción del Grafo (LangGraph)
Con el contenedor de observabilidad corriendo (`docker compose up -d`), construimos la máquina de estados en el directorio `src/`.

> **Prompt 3 (Terminal):** 
> Continúa con las tareas de implementación de Python. Crea el archivo de estado global en `src/agent/state.py` usando `TypedDict`. Debe incluir un flag como `is_valid` y el reporte de fallos.
> 
> Implementa los nodos en `src/agent/graph.py` respetando la separación de responsabilidades: 
> - El nodo de Seguridad hace la llamada al LLM y establece `is_valid`. 
> - El nodo Supervisor/Orquestador solo evalúa ese estado mediante `add_conditional_edges` para enrutar al Refactor o terminar (máximo 3 iteraciones).
> Simula o implementa las llamadas al LLM para los sub-agentes correspondientes.

### Fase 4: El Arnés de Telemetría (OpenTelemetry)
Unimos el grafo de LangGraph con el OTel Collector local.

> **Prompt 4 (Terminal):** 
> Ejecuta la tarea de telemetría. En `src/telemetry/setup.py`, configura el SDK de OpenTelemetry apuntando al localhost:4317. 
> 
> Instala e integra `openinference-instrumentation-langchain` para auto-instrumentar las llamadas. Modifica `src/main.py` para inicializar la telemetría, cargar un código de prueba con un error intencionado y ejecutar el flujo completo.

### Fase 5: Dockerización de la Solución (Cloud-Native Ready)
Empaquetamos el agente Python para aislarlo y prepararlo para un futuro despliegue en OpenShift/AWS.

> **Prompt 5 (Terminal):** 
> Crea un `Dockerfile` en la raíz del proyecto utilizando `python:3.12-slim` para empaquetar nuestra aplicación. 
> 
> Luego, actualiza el `docker/docker-compose.yml` añadiendo un nuevo servicio llamado `app`. Este servicio debe hacer build desde el `Dockerfile`, depender del OTel Collector, y tener configuradas las variables de entorno necesarias (API keys y el endpoint OTLP). IMPORTANTE: Ajusta el endpoint OTLP en el código de Python o en el `.env` para que apunte al nombre del contenedor del collector dentro de la red de Docker (ej. `http://otel-collector:4317`), en lugar de localhost.