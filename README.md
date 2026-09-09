# 🚀 Ejercicio Práctico: Agente Autónomo de Análisis y Refactorización

El ejercicio consiste en construir un sistema multi-agente autónomo capaz de analizar y refactorizar código, gobernando sus decisiones y costes de ejecución. Se busca demostrar que el comportamiento no determinista de los LLMs puede ser trazable, medible y seguro para su paso a producción.

## 🎯 Objetivo

Validar empíricamente la **Observabilidad de IA** y el concepto de **Harness Engineering** (Ingeniería de Arnés).

---

## Pilares Técnicos
*   **Orquestación:** LangGraph (Python) para gestionar el estado y el enrutamiento.
*   **Harness Engineering:** RAG para guías de estilo (Feedforward) y políticas Zero Trust (Feedback).
*   **Observabilidad:** OpenTelemetry interceptando consumos de tokens y trazas del grafo, exportados localmente a Jaeger y Prometheus vía OTel Collector.
*   **Metodología:** OpenSpec Propose (Spec-Driven Development) asistido por Claude Code.



## 🗺️ Arquitectura de Estado: Flujo LangGraph

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

## 🏗️ Arquitectura de Componentes y Observabilidad

El sistema separa la lógica del agente de la infraestructura de observabilidad. La aplicación Python instrumentada envía datos en crudo (OTLP) al Collector, el cual se encarga de enrutar las métricas (tokens) y trazas (decisiones) a sus respectivos motores.

```mermaid
graph LR
    subgraph App ["Aplicación Python"]
        AGENT[🧠 LangGraph Orquestador<br>+ OpenTelemetry SDK]
    end

    subgraph Dependencias ["Servicios Externos / Datos"]
        VDB[(Vector DB<br>RAG Context)]
        LLM((APIs LLM<br>Claude/OpenAI))
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