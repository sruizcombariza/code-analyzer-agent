# 🚀 Ejercicio Práctico: Agente Autónomo de Análisis y Refactorización

El ejercicio consiste en construir un sistema multi-agente autónomo capaz de analizar y refactorizar código, gobernando sus decisiones y costes de ejecución. Se busca demostrar que el comportamiento no determinista de los LLMs puede ser trazable, medible y seguro para su paso a producción.

## 🎯 Objetivo

Validar empíricamente la **Observabilidad de IA** y el concepto de **Harness Engineering** (Ingeniería de Arnés).


## Pilares Técnicos
*   **Orquestación:** LangGraph (Python) para gestionar el estado y el enrutamiento.
*   **Harness Engineering:** RAG para guías de estilo (Feedforward) y políticas Zero Trust (Feedback).
*   **Observabilidad:** OpenTelemetry interceptando consumos de tokens y trazas del grafo, exportados localmente a Jaeger y Prometheus vía OTel Collector.
*   **Metodología:** OpenSpec Propose (Spec-Driven Development) asistido por Claude Code.



## 🗺️ Arquitectura de Estado: Flujo LangGraph

### Arquitectura objetivo

El flujo se basa en un diseño jerárquico de **1 Orquestador y 3 Sub-agentes**. El Orquestador centraliza el estado global (LangGraph `StateGraph`) y toma decisiones de enrutamiento basadas en las respuestas de los sub-agentes.

```mermaid
graph TD
    START((Inicio)) --> SUP[🧠 Orquestador]
    
    SUP -->|1. Busca contexto| RAG[📚 Sub-agente: RAG]
    RAG --> SUP
    
    SUP -->|2. Revisa código| SEC[🛡️ Sub-agente: Seguridad]
    SEC --> SUP
    
    SUP -->|3. Si hay fallos| REF[🛠️ Sub-agente: Refactor]
    REF --> SUP
    
    SUP -->|4. Si está limpio| END((Fin))
``` 

### Implementación actual

El Orquestador no es un nodo que llame al LLM ni lea código: es la función de enrutamiento que corre justo después de Seguridad, y decide leyendo únicamente `is_valid` e `iteration_count` del estado compartido. De los 3 sub-agentes, solo **Seguridad** y **Refactor** invocan a Claude — **Contexto** es una lectura determinista de `team-rules.md`, sin LLM ni RAG (ver decisiones de diseño en `openspec/changes/archive/2026-09-09-add-code-analyzer-agent/design.md`).

```mermaid
graph TD
    START((Inicio)) --> CTX[📄 Sub-agente: Contexto]
    CTX --> SEC[🛡️ Sub-agente: Seguridad]

    SEC -->|"🧠 Orquestador: is_valid = true"| END((Fin))
    SEC -->|"🧠 Orquestador: is_valid = false<br>e iteraciones disponibles"| REF[🛠️ Sub-agente: Refactor]
    SEC -->|"🧠 Orquestador: máx. iteraciones alcanzado"| END

    REF --> SEC
```

## 🏗️ Arquitectura de Componentes y Observabilidad

### Arquitectura objetivo

El sistema separa la lógica del agente de la infraestructura de observabilidad. La aplicación Python instrumentada envía datos en crudo (OTLP) al Collector, el cual se encarga de enrutar las métricas (tokens) y trazas (decisiones) a sus respectivos motores.

```mermaid
graph LR
    subgraph App ["Aplicación Python"]
        AGENT[🧠 LangGraph Orquestador<br>+ OpenTelemetry SDK]
    end

    subgraph Dependencias ["Servicios Externos / Datos"]
        VDB[(Vector DB<br>RAG Context)]
        LLM((API LLM<br>Claude))
    end

    subgraph Observabilidad ["Stack Local (Docker Compose)"]
        COL[⚙️ OTel Collector]
        JAE[🔎 Jaeger<br>Visor de Trazas]
        PRO[📊 Prometheus<br>Métricas / Costes]
    end

    %% Flujo de datos y ejecución
    AGENT <-->|1. Recupera guías locales| VDB
    AGENT <-->|2. Inferencia y razonamiento| LLM
    
    %% Flujo de telemetría
    AGENT -->|3. Envía datos OTLP<br>Spans + Tokens| COL
    COL -->|Exporta Trazas| JAE
    COL -->|Exporta Métricas| PRO
```     

### Implementación actual

`team-rules.md` es un archivo local empaquetado con la propia app, no una dependencia externa — por eso no hay una `Vector DB` en la topología real.

```mermaid
graph LR
    subgraph App ["Aplicación Python"]
        AGENT[🧠 LangGraph Orquestador<br>+ OpenTelemetry SDK]
    end

    subgraph Dependencias ["Servicios Externos / Datos"]
        RULES[📄 team-rules.md<br>archivo local]
        LLM((API LLM<br>Claude))
    end

    subgraph Observabilidad ["Stack Local (Docker Compose)"]
        COL[⚙️ OTel Collector]
        JAE[🔎 Jaeger<br>Visor de Trazas]
        PRO[📊 Prometheus<br>Métricas / Costes]
    end

    %% Flujo de datos y ejecución
    AGENT -->|1. Lee reglas de equipo| RULES
    AGENT <-->|2. Inferencia y razonamiento| LLM

    %% Flujo de telemetría
    AGENT -->|3. Envía datos OTLP<br>Spans + Tokens| COL
    COL -->|Exporta Trazas| JAE
    COL -->|Exporta Métricas| PRO
```