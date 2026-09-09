"""Inicialización de Tracer, Meter y OpenInference.

Centraliza la configuración del SDK de OpenTelemetry (proveedores de
trazas y métricas + exportadores OTLP hacia el Collector local) y la
instrumentación automática de LangChain/LangGraph vía OpenInference, para
que las llamadas del agente queden trazadas sin instrumentar el código a mano.
"""

import os

from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

DEFAULT_OTLP_ENDPOINT = "localhost:4317"
SERVICE_NAME_VALUE = "code-analyzer-agent"

_initialized = False


def _otlp_endpoint() -> str:
    endpoint = os.environ.get("OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)
    # El exportador OTLP/gRPC espera "host:puerto", sin esquema.
    return endpoint.removeprefix("http://").removeprefix("https://")


def setup_telemetry() -> None:
    """Configura el SDK de OpenTelemetry e instrumenta LangChain/LangGraph.

    Idempotente: llamadas repetidas no duplican proveedores ni instrumentación.
    """
    global _initialized
    if _initialized:
        return

    endpoint = _otlp_endpoint()
    resource = Resource.create({SERVICE_NAME: SERVICE_NAME_VALUE})

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True)
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

    _initialized = True
