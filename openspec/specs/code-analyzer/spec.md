# code-analyzer Specification

## Purpose

Gobierna un flujo multi-agente (LangGraph) que analiza código fuente contra las reglas de un equipo y lo refactoriza de forma acotada cuando falla la validación, manteniendo la decisión de seguridad, el enrutamiento y la modificación de código en autoridades separadas y auditables.

## Requirements

### Requirement: Enrutamiento del Orquestador basado exclusivamente en el estado
El Orquestador SHALL decidir la siguiente arista del grafo leyendo únicamente banderas del estado compartido (`is_valid`, `iteration_count`). El Orquestador SHALL NOT invocar la API del LLM ni inspeccionar el contenido del código fuente para tomar su decisión de enrutamiento.

#### Scenario: Primera pasada tras cargar el contexto
- **GIVEN** el estado contiene las reglas de equipo cargadas y aún no existe veredicto de seguridad
- **WHEN** el Orquestador evalúa a qué nodo enrutar
- **THEN** enruta al sub-agente de Seguridad

#### Scenario: Código inválido con iteraciones disponibles
- **GIVEN** el estado tiene `is_valid = false` y `iteration_count` por debajo del máximo permitido
- **WHEN** el Orquestador evalúa a qué nodo enrutar
- **THEN** enruta al sub-agente de Refactor

#### Scenario: Código válido
- **GIVEN** el estado tiene `is_valid = true`
- **WHEN** el Orquestador evalúa a qué nodo enrutar
- **THEN** finaliza el flujo (END) sin invocar a Refactor

#### Scenario: Límite de iteraciones alcanzado sin validación exitosa
- **GIVEN** el estado tiene `is_valid = false` y `iteration_count` igual al máximo permitido (3)
- **WHEN** el Orquestador evalúa a qué nodo enrutar
- **THEN** finaliza el flujo (END) y el resultado queda marcado como no resuelto automáticamente, sin iniciar una nueva iteración de Refactor

### Requirement: Carga de contexto desde `team-rules.md` sin recuperación vectorial
El sub-agente de Contexto SHALL leer las reglas del equipo desde un único archivo local `team-rules.md` y SHALL escribir su contenido en el estado compartido. El sub-agente de Contexto SHALL NOT emplear una base de datos vectorial ni ningún mecanismo de recuperación semántica (RAG) para obtener las reglas.

#### Scenario: Carga correcta de reglas
- **GIVEN** existe un archivo `team-rules.md` con contenido
- **WHEN** el sub-agente de Contexto se ejecuta
- **THEN** el estado compartido queda con el contenido íntegro del archivo disponible para los siguientes nodos

#### Scenario: Archivo de reglas ausente
- **GIVEN** no existe el archivo `team-rules.md` en la ruta esperada
- **WHEN** el sub-agente de Contexto se ejecuta
- **THEN** el estado compartido registra explícitamente la ausencia de reglas como condición, y el flujo NO continúa como si el código estuviera automáticamente validado

#### Scenario: Archivo de reglas vacío
- **GIVEN** el archivo `team-rules.md` existe pero no contiene reglas
- **WHEN** el sub-agente de Contexto se ejecuta
- **THEN** el estado compartido registra explícitamente que no hay reglas cargadas, distinguiendo este caso de un error de lectura del archivo

### Requirement: Revisión de seguridad Zero Trust con autoridad exclusiva sobre el veredicto
El sub-agente de Seguridad SHALL ser el único nodo del grafo autorizado a escribir el veredicto de validez (`is_valid`) y el detalle de fallos (`findings`) en el estado compartido. El sub-agente de Seguridad SHALL invocar la API del LLM pasando el código a revisar y las reglas de equipo cargadas, y SHALL tratar todo código de entrada como no confiable hasta que el veredicto se calcule explícitamente.

#### Scenario: Código que incumple las reglas de equipo
- **GIVEN** el estado contiene código fuente y reglas de equipo cargadas
- **WHEN** el sub-agente de Seguridad revisa el código contra las reglas mediante el LLM y detecta incumplimientos
- **THEN** escribe `is_valid = false` en el estado junto con el listado de hallazgos (`findings`) que describen cada incumplimiento

#### Scenario: Código que cumple las reglas de equipo
- **GIVEN** el estado contiene código fuente y reglas de equipo cargadas
- **WHEN** el sub-agente de Seguridad revisa el código contra las reglas mediante el LLM y no detecta incumplimientos
- **THEN** escribe `is_valid = true` en el estado y `findings` queda vacío

#### Scenario: Ningún otro nodo altera el veredicto de seguridad
- **GIVEN** el sub-agente de Refactor acaba de modificar el código en una iteración del ciclo
- **WHEN** el flujo vuelve al Orquestador tras el Refactor
- **THEN** el estado mantiene el código actualizado pero `is_valid` permanece sin recalcular hasta que Seguridad vuelva a ejecutarse sobre la nueva versión del código

### Requirement: Ciclo de refactor acotado por un límite duro de iteraciones
El sub-agente de Refactor SHALL activarse únicamente cuando el estado indique `is_valid = false` y queden iteraciones disponibles. El sub-agente de Refactor SHALL modificar exclusivamente el código en el estado a partir de los `findings` reportados, SHALL incrementar `iteration_count`, y SHALL NOT escribir `is_valid`. El sistema SHALL detener el ciclo Seguridad↔Refactor al alcanzar un máximo de 3 iteraciones.

#### Scenario: Refactor corrige el código y solicita nueva revisión
- **GIVEN** el estado tiene `is_valid = false` con al menos un hallazgo reportado y `iteration_count` por debajo del máximo
- **WHEN** el sub-agente de Refactor se ejecuta
- **THEN** produce una nueva versión del código en el estado, incrementa `iteration_count` en uno, y no modifica `is_valid` ni `findings`

#### Scenario: El ciclo se detiene al alcanzar el máximo de iteraciones
- **GIVEN** el estado tiene `is_valid = false` e `iteration_count` ya igual a 3 (el máximo permitido)
- **WHEN** el Orquestador evalúa el estado tras la última revisión de Seguridad
- **THEN** el flujo finaliza sin ejecutar una nueva iteración de Refactor, y el resultado final expone que el código no quedó validado dentro del límite de iteraciones

### Requirement: Origen del código analizado limitado a un snippet fijo de entrada
El punto de entrada del sistema SHALL inicializar el estado compartido con un único snippet de código (proporcionado como cadena de texto, p. ej. un archivo de prueba con un error intencionado) antes de iniciar la ejecución del grafo. Ningún nodo del grafo (Orquestador, Contexto, Seguridad, Refactor) SHALL descubrir, listar o leer archivos de un repositorio, ni interpretar diffs de control de versiones, para obtener el código a analizar.

#### Scenario: El grafo arranca con un snippet de código ya cargado en el estado
- **GIVEN** el punto de entrada ha inicializado `AgentState.code` con un snippet de código de prueba
- **WHEN** el grafo comienza su ejecución
- **THEN** el sub-agente de Contexto y, posteriormente, el de Seguridad, operan sobre ese mismo snippet sin intentar localizar o leer código adicional de un repositorio

### Requirement: Estado compartido como único canal de comunicación entre nodos
Todos los nodos del grafo (Orquestador, Contexto, Seguridad, Refactor) SHALL comunicarse exclusivamente a través de un esquema de estado compartido único. Cada nodo SHALL escribir únicamente en los campos del estado de los que es responsable, definidos en `design.md`.

#### Scenario: Un nodo no escribe fuera de sus campos de responsabilidad
- **GIVEN** el grafo está en ejecución y cada nodo tiene un conjunto de campos de estado que le pertenece (p. ej. Contexto → reglas cargadas, Seguridad → veredicto y hallazgos, Refactor → código)
- **WHEN** cualquiera de los sub-agentes completa su ejecución
- **THEN** el estado resultante solo refleja cambios en los campos propios de ese nodo, dejando intactos los campos que pertenecen a los demás nodos
