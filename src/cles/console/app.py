"""The CLES web console: one landing page for the whole system.

Serves the product home page (ask the expert system), the results explorer, and a platform view
that embeds and checks the tools (MLflow, Grafana, Phoenix, Prometheus). It reuses the advisor API
(`/advise`, `/feedback`) and the explorer API (`/api/data`, `/api/label`).

    scripts/pipeline.sh console   (or: uv run uvicorn cles.console.app:create_app --factory)
"""

import json
import logging
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cles.config import Settings, get_settings
from cles.db import connect
from cles.domain.pack import load_pack
from cles.evaluation.explorer import add_explorer_routes
from cles.inference.app import create_app as create_advisor_app
from cles.inference.guard import is_external

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
PROBE_TIMEOUT = 1.5


def tool_catalog(settings: Settings) -> list[dict]:
    """The platform tools: what each is for, where it lives, how to check it."""
    mlflow = settings.mlflow_tracking_uri.rstrip("/")
    grafana, phoenix, prom = (
        u.rstrip("/") for u in (settings.grafana_url, settings.phoenix_url, settings.prometheus_url)
    )
    return [
        {
            "id": "mlflow",
            "name": "MLflow",
            "purpose": "Experiments and model registry: runs per stage, system and training.",
            "url": mlflow,
            "embed": mlflow,
            "probe": f"{mlflow}/health",
        },
        {
            "id": "grafana-quality",
            "name": "Grafana: model quality",
            "purpose": "Scores per system, progress per evaluation, pipeline cost, firing alerts.",
            "url": f"{grafana}/d/cles-quality",
            "embed": f"{grafana}/d/cles-quality?kiosk",
            "probe": f"{grafana}/api/health",
        },
        {
            "id": "grafana-overview",
            "name": "Grafana: runtime",
            "purpose": "Answer latency, evidence strength, citation failures, tokens, stage runs.",
            "url": f"{grafana}/d/cles-overview",
            "embed": f"{grafana}/d/cles-overview?kiosk",
            "probe": f"{grafana}/api/health",
        },
        {
            "id": "phoenix",
            "name": "Phoenix",
            "purpose": "Traces of stages and requests: prompts, context, timings (internal).",
            "url": phoenix,
            "embed": phoenix,
            "probe": f"{phoenix}/healthz",
        },
        {
            "id": "prometheus",
            "name": "Prometheus: alerts",
            "purpose": "Alert rules for quality, pipeline health and drift, with their state.",
            "url": f"{prom}/alerts",
            "embed": f"{prom}/alerts",
            "probe": f"{prom}/-/ready",
        },
        {
            "id": "api-docs",
            "name": "API reference",
            "purpose": "The advisor HTTP API (OpenAPI): /advise, /feedback, explorer endpoints.",
            "url": "/docs",
            "embed": "/docs",
            "probe": None,
        },
    ]


def probe(url: str | None) -> tuple[bool, str]:
    """(reachable, detail) of an HTTP health URL."""
    if url is None:
        return True, "built in"
    try:
        with urllib.request.urlopen(url, timeout=PROBE_TIMEOUT) as reply:  # our own tools
            return reply.status < 500, f"HTTP {reply.status}"
    except Exception as exc:
        return False, str(exc)[:80]


def status(settings: Settings) -> dict:
    tools = tool_catalog(settings)
    with ThreadPoolExecutor(max_workers=8) as pool:
        probes = list(pool.map(lambda t: probe(t["probe"]), tools))
    items = [
        {k: t[k] for k in ("id", "name", "purpose", "url", "embed")} | {"ok": ok, "detail": detail}
        for t, (ok, detail) in zip(tools, probes, strict=True)
    ]
    items += [_check_postgres(settings), _check_model(settings)]
    return {"tools": items, "all_ok": all(i["ok"] for i in items)}


def _check_postgres(settings: Settings) -> dict:
    try:
        with connect(settings) as conn:
            conn.execute("SELECT 1")
        ok, detail = True, "connected"
    except Exception as exc:
        ok, detail = False, str(exc)[:80]
    return {
        "id": "postgres",
        "name": "Postgres (documents, vectors, audit)",
        "ok": ok,
        "detail": detail,
        "purpose": "",
        "url": None,
        "embed": None,
    }


def _check_model(settings: Settings) -> dict:
    host = urlparse(settings.llm_base_url).hostname or ""
    external = is_external(settings.llm_base_url, settings.trusted_generator_hosts)
    if external:  # no probing of a paid third-party endpoint
        ok, detail = bool(settings.openai_api_key), f"external service {host}"
    else:
        ok, detail = probe(f"{settings.llm_base_url.rstrip('/')}/models")
    return {
        "id": "model",
        "name": f"Model: {model_label(settings)}",
        "ok": ok,
        "detail": detail,
        "purpose": "",
        "url": None,
        "embed": None,
    }


def model_label(settings: Settings) -> str:
    return settings.adapter_version or settings.llm_model or "not configured"


def info(settings: Settings) -> dict:
    """What the home page shows about the system: model, corpus, pack, latest quality checks."""
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    corpus: dict = {}
    try:
        with connect(settings) as conn:
            n, first, last = conn.execute(
                "SELECT count(*), min(doc_date), max(doc_date) FROM documents"
            ).fetchone()
            chunks = conn.execute("SELECT count(*) FROM chunks WHERE level = 'child'").fetchone()[0]
        corpus = {"decisions": n, "passages": chunks, "from": str(first), "to": str(last)}
    except Exception as exc:
        log.warning("corpus statistics unavailable: %s", exc)
    return {
        "name": "CLES",
        "pack": {
            "name": pack.info.name,
            "version": pack.info.version,
            "scope": pack.info.scope,
            "disclaimer": pack.info.disclaimer,
        },
        "model": {
            "name": model_label(settings),
            "external": is_external(settings.llm_base_url, settings.trusted_generator_hosts),
        },
        "corpus": corpus,
        "quality": _quality(settings),
    }


def _quality(settings: Settings) -> dict | None:
    """Headline numbers of the latest offline evaluation of the fine-tuned system (honest and
    dated by the metrics file), or None when there is none."""
    path = settings.eval_metrics_file
    if not path.is_file():
        return None
    m = json.loads(path.read_text())
    keys = {
        "schema_valid": "finetuned.all.valid_schema",
        "stage_correct": "finetuned.all.stage_ok",
        "citation_failure_rate": "finetuned.all.citation_failure_rate",
        "examples": "finetuned.all.examples",
    }
    if any(v not in m for v in keys.values()):
        return None
    return {k: m[v] for k, v in keys.items()}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = create_advisor_app(settings, page_route=None)
    app.title = "CLES console"
    add_explorer_routes(app, settings, page_route="/explorer")

    @app.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "console.html")

    @app.get("/api/info")
    def api_info() -> dict:
        return info(settings)

    @app.get("/api/status")
    def api_status() -> dict:
        return status(settings)

    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
    return app
