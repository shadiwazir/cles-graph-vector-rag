"""OpenTelemetry setup and small helpers. Only the OpenTelemetry API is used by application
code, so the backend (Phoenix, Prometheus, anything else) is chosen in the Collector config.

Case text is never exported unless TELEMETRY_CAPTURE_CONTENT allows it (see `redact`).
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span

from cles.config import Settings
from cles.observability.logging import redact

log = logging.getLogger(__name__)
_providers: list = []


def setup_telemetry(service_name: str, settings: Settings) -> bool:
    """Start exporting traces and metrics. Returns False (and does nothing) when disabled."""
    if not settings.telemetry_enabled or _providers:
        return bool(_providers)
    base = settings.otel_exporter_otlp_endpoint.rstrip("/")
    resource = Resource.create({"service.name": service_name, "openinference.project.name": "cles"})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(f"{base}/v1/traces")))
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(f"{base}/v1/metrics"), export_interval_millis=10_000
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)
    _providers.extend([tracer_provider, meter_provider])
    log.info("telemetry enabled, exporting to %s", base)
    return True


def shutdown_telemetry() -> None:
    """Flush pending spans and metrics (short-lived stages call this before exiting)."""
    for provider in _providers:
        provider.shutdown()
    _providers.clear()


_tracer = trace.get_tracer("cles")


@contextmanager
def span(name: str, kind: str = "CHAIN", **attributes) -> Iterator[Span]:
    """A span with the OpenInference kind (CHAIN, RETRIEVER, LLM...) that Phoenix understands."""
    with _tracer.start_as_current_span(name) as current:
        current.set_attribute("openinference.span.kind", kind)
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current


def text_attribute(text: str, settings: Settings) -> str:
    """Apply the capture policy to text before it becomes a span attribute."""
    return redact(text, settings.telemetry_capture_content)
