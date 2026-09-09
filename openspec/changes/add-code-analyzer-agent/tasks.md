## 1. Estado compartido (`src/agent/state.py`)

- [ ] 1.1 Definir `AgentState` (TypedDict) con los campos: `code`, `team_rules`, `rules_status` (cargado/ausente/vacío), `is_valid`, `findings`, `iteration_count`, `max_iterations`.
- [ ] 1.2 Documentar en el propio módulo qué nodo es el único autor de cada campo (Contexto → `team_rules`/`rules_status`; Seguridad → `is_valid`/`findings`; Refactor → `code`/`iteration_count`).

## 2. Reglas de equipo y sub-agente de Contexto

- [ ] 2.1 Crear `team-rules.md` de ejemplo con al menos una regla verificable por el sub-agente de Seguridad.
- [ ] 2.2 Implementar el nodo de Contexto: lee `team-rules.md` y escribe `team_rules` + `rules_status = "loaded"`.
- [ ] 2.3 Cubrir en el nodo de Contexto el caso de archivo ausente (`rules_status = "missing"`) y archivo vacío (`rules_status = "empty"`), sin lanzar una excepción no controlada.

## 3. Sub-agente de Seguridad (Zero Trust)

- [ ] 3.1 Definir el contrato de llamada a la API del LLM: entrada (`code`, `team_rules`) y salida estructurada (veredicto + lista de hallazgos).
- [ ] 3.2 Implementar el nodo de Seguridad: invoca la API del LLM y escribe `is_valid` + `findings` en el estado.
- [ ] 3.3 Asegurar que ningún otro nodo del grafo escribe `is_valid` o `findings` (revisión de código / test de contrato).

## 4. Sub-agente de Refactor

- [ ] 4.1 Implementar el nodo de Refactor: a partir de `code` + `findings`, produce una nueva versión de `code` e incrementa `iteration_count`.
- [ ] 4.2 Asegurar que el nodo de Refactor no escribe `is_valid` ni `findings`.

## 5. Orquestador y ensamblado del grafo (`src/agent/graph.py`)

- [ ] 5.1 Construir el `StateGraph` con los nodos Contexto, Seguridad, Refactor y las aristas de entrada/salida.
- [ ] 5.2 Implementar la función de enrutamiento condicional del Orquestador basada únicamente en `is_valid` e `iteration_count` (sin leer `code` ni llamar al LLM).
- [ ] 5.3 Fijar `max_iterations = 3` y verificar que el grafo termina en `END` al alcanzarlo, incluso con `is_valid = false`.
- [ ] 5.4 Exponer la función de compilación del grafo para su uso desde `src/main.py`.
- [ ] 5.5 En `src/main.py`, definir el snippet de código de prueba (con un error intencionado) e inicializar `AgentState.code` con él antes de invocar el grafo, sin lectura de repositorio ni de diffs de Git.

## 6. Pruebas (`tests/`)

- [ ] 6.1 Test del nodo de Contexto para los tres estados de `rules_status` (loaded/missing/empty), según los escenarios de `specs/code-analyzer/spec.md`.
- [ ] 6.2 Test del enrutamiento del Orquestador para las cuatro combinaciones de `is_valid`/`iteration_count` descritas en la spec (primera pasada, inválido con iteraciones, válido, límite alcanzado).
- [ ] 6.3 Test de extremo a extremo del grafo con un código de entrada que falla en la primera revisión y se resuelve dentro del límite de iteraciones.
- [ ] 6.4 Test de extremo a extremo del grafo con un código que nunca queda válido, verificando que se detiene en la iteración 3 y expone el resultado como no resuelto.

## 7. Validación de la capacidad

- [ ] 7.1 Ejecutar `openspec validate add-code-analyzer-agent --strict` y corregir cualquier hallazgo antes de pasar a la fase `apply`.
