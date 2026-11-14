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
stage_value = _meter.create_gauge(
    "cles.stage.value", description="Numbers from the last stage summary (cost, counts, failures)"
)
eval_quality = _meter.create_gauge(
    "cles.eval.quality", description="Offline evaluation rates by system, scope and metric"
)
eval_count = _meter.create_gauge(
    "cles.eval.count", description="Offline evaluation counts by system, scope and metric"
)
drift_violations = _meter.create_gauge(
    "cles.drift.violations", description="Checks that failed in the last drift check"
)
