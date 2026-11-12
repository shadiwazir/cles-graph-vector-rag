"""HTTP API. Run: uv run uvicorn cles.inference.app:create_app --factory --port 8000"""

from contextlib import asynccontextmanager
from datetime import date

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from cles.config import ConfigError, Settings, get_settings
from cles.db import connect
from cles.domain.pack import load_pack
from cles.graph.client import make_driver
from cles.inference.advisor import AdviceRequest, Advisor
from cles.inference.guard import check_generator_allowed
from cles.inference.verifier import CitationVerifier
from cles.ingestion.embedder import Embedder
from cles.llm.openai_client import make_client
from cles.observability.logging import setup_logging
from cles.observability.telemetry import setup_telemetry, shutdown_telemetry
from cles.retrieval.graph import GraphRetriever
from cles.retrieval.hybrid import HybridRetriever


class AdviseBody(BaseModel):
    case_text: str = Field(min_length=20, max_length=20000)
    question: str = Field(min_length=5, max_length=2000)
    as_of: date | None = None  # only for evaluation: ignore decisions on or after this date


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    check_generator_allowed(settings)  # refuse to start if case text would leave our control
    setup_logging()
    setup_telemetry("cles-api", settings)
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.embedder = Embedder.from_settings(settings)  # loaded once, shared
        app.state.driver = make_driver(settings)
        app.state.client = make_client(settings)
        yield
        app.state.driver.close()
        shutdown_telemetry()

    app = FastAPI(title="CLES", lifespan=lifespan)

    def build_advisor(conn: psycopg.Connection) -> Advisor:
        graph = GraphRetriever(app.state.driver, pack)
        retriever = HybridRetriever(conn, app.state.embedder, graph, settings)
        verifier = CitationVerifier(conn, graph)
        return Advisor(conn, retriever, verifier, app.state.client, pack, settings)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "pack": pack.info.name, "version": pack.info.version}

    @app.post("/advise")
    def advise(body: AdviseBody) -> dict:
        try:
            with connect(
                settings
            ) as conn:  # one connection per request (psycopg is not thread-safe)
                response = build_advisor(conn).advise(
                    AdviceRequest(body.case_text, body.question, body.as_of)
                )
        except ConfigError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return response.__dict__

    return app
