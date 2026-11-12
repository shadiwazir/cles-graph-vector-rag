"""Application metrics (OpenTelemetry instruments, no-ops until telemetry is set up)."""

from opentelemetry import metrics

_meter = metrics.get_meter("cles")

advise_duration = _meter.create_histogram(
    "cles.advise.duration", unit="ms", description="Time to answer one request"
)
answers = _meter.create_counter("cles.answers", description="Answers by evidence strength")
citations = _meter.create_counter("cles.citations", description="Citations checked, by result")
generation_failures = _meter.create_counter(
    "cles.generation.failures", description="Answers where the model output was unusable"
)
llm_tokens = _meter.create_counter("cles.llm.tokens", description="LLM tokens by direction")
stage_duration = _meter.create_histogram(
    "cles.stage.duration", unit="s", description="Pipeline stage run time"
)
stage_runs = _meter.create_counter("cles.stage.runs", description="Pipeline stage runs by status")
