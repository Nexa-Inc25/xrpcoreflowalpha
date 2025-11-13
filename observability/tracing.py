import os

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(service_name: str = "xrpflowalpha-api"):
    jaeger_host = os.getenv("JAEGER_AGENT_HOST", "jaeger")
    jaeger_port = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    trace.set_tracer_provider(provider)

    jaeger_exporter = JaegerExporter(agent_host_name=jaeger_host, agent_port=jaeger_port)
    span_processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(span_processor)
