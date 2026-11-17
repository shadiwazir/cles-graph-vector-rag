"""Advisor: retrieve context, generate structured advice, verify citations, record an audit row."""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import date

import psycopg

from cles.config import Settings
from cles.domain.pack import DomainPack
from cles.inference.calibration import apply_precedent_rule, cap_likelihood
from cles.inference.guard import check_generator_allowed
from cles.inference.prompt import build_messages
from cles.inference.verifier import CitationVerifier
from cles.llm.base import LLMClient
from cles.llm.structured import ask_for_json
from cles.observability import metrics as m
from cles.observability.logging import new_request_id
from cles.observability.telemetry import span, text_attribute
from cles.retrieval.hybrid import HybridRetriever
from cles.retrieval.types import SearchFilter

log = logging.getLogger(__name__)
_STRENGTH = {"weak": 0, "moderate": 1, "strong": 2}


@dataclass(frozen=True)
class AdviceRequest:
    case_text: str
    question: str
    as_of: date | None = None
    exclude_doc_ids: tuple[str, ...] = ()


@dataclass
class AdviceResponse:
    request_id: str
    advice: dict | None
    evidence_strength: str
    sources: list[dict]
    citations_total: int
    citations_failed: int
    warnings: list[str]
    scope: str
    disclaimer: str
    latency_ms: int
    prompt_version: str
    error: str | None = None
    extra: dict = field(default_factory=dict)


class Advisor:
    def __init__(
        self,
        conn: psycopg.Connection,
        retriever: HybridRetriever,
        verifier: CitationVerifier,
        client: LLMClient,
        pack: DomainPack,
        settings: Settings,
    ):
        check_generator_allowed(settings)
        self._conn = conn
        self._retriever = retriever
        self._verifier = verifier
        self._client = client
        self._pack = pack
        self._settings = settings
        self.prompt_version = _prompt_version(pack)

    def _precedent_outcomes(self, doc_ids: list[str]) -> list[str]:
        """Outcome of each retrieved decision (latest successful extraction); a decision without
        one is left out, so it can never count as agreement."""
        if not doc_ids:
            return []
        rows = self._conn.execute(
            """SELECT DISTINCT ON (doc_id) result->>'outcome' FROM extractions
               WHERE status = 'ok' AND doc_id = ANY(%s) ORDER BY doc_id, created_at DESC""",
            (doc_ids,),
        ).fetchall()
        return [r[0] for r in rows if r[0]]

    def advise(self, req: AdviceRequest) -> AdviceResponse:
        started = time.monotonic()
        request_id = new_request_id()
        flt = SearchFilter(as_of=req.as_of, exclude_doc_ids=req.exclude_doc_ids)
        with span(
            "advise",
            request_id=request_id,
            **{"input.value": text_attribute(req.question, self._settings)},
        ) as root_span:
            response = self._advise(req, flt, request_id, started)
            root_span.set_attribute("evidence_strength", response.evidence_strength)
            root_span.set_attribute("citations.total", response.citations_total)
            root_span.set_attribute("citations.failed", response.citations_failed)
        self._record_metrics(response)
        return response

    def _advise(
        self, req: AdviceRequest, flt: SearchFilter, request_id: str, started: float
    ) -> AdviceResponse:
        context = self._retriever.retrieve(search_text(req), flt)

        messages = build_messages(self._pack, req.case_text, req.question, context)
        with span("generate", kind="LLM", **{"llm.model_name": self._client.model}) as gen:
            outcome = ask_for_json(self._client, messages, self._pack.advice_schema)
            gen.set_attribute("llm.token_count.prompt", outcome.input_tokens)
            gen.set_attribute("llm.token_count.completion", outcome.output_tokens)
            gen.set_attribute("generation.status", outcome.status)
        m.llm_tokens.add(outcome.input_tokens, {"direction": "in"})
        m.llm_tokens.add(outcome.output_tokens, {"direction": "out"})
        warnings: list[str] = []
        advice, total, failed = None, 0, 0
        strength = context.evidence_strength
        if outcome.status == "ok":
            with span("verify") as ver:
                report = self._verifier.verify(outcome.result, req.as_of)
                ver.set_attribute("citations.total", report.total)
                ver.set_attribute("citations.failed", report.failed)
            advice, total, failed = report.advice, report.total, report.failed
            warnings += report.warnings()
            strength = _weaker(outcome.result.get("evidence_strength", strength), strength)
            advice["evidence_strength"] = strength
            warnings += cap_likelihood(advice, strength, self._pack.info.likelihood_caps_by_stage)
            if self._settings.precedent_rule_enabled:
                warnings += apply_precedent_rule(
                    advice,
                    self._precedent_outcomes(context.retrieved_doc_ids),
                    set(self._pack.training.early_stages),
                    self._settings.precedent_rule_min_decisions,
                )
        else:
            warnings.append(f"generation failed: {outcome.error}")
        if strength == "weak":
            warnings.append("Weak evidence: little relevant material was found in the corpus.")

        response = AdviceResponse(
            request_id=request_id,
            advice=advice,
            evidence_strength=strength,
            sources=[
                {"label": p.label, "title": p.title, "distance": p.distance}
                for p in context.passages
            ],
            citations_total=total,
            citations_failed=failed,
            warnings=warnings,
            scope=self._scope(),
            disclaimer=self._pack.info.disclaimer,
            latency_ms=int((time.monotonic() - started) * 1000),
            prompt_version=self.prompt_version,
            error=None if outcome.status == "ok" else outcome.error,
        )
        self._audit(response, req, context.retrieved_doc_ids)
        return response

    def _record_metrics(self, r: AdviceResponse) -> None:
        m.advise_duration.record(r.latency_ms)
        m.answers.add(1, {"evidence": r.evidence_strength})
        m.citations.add(r.citations_total - r.citations_failed, {"result": "verified"})
        m.citations.add(r.citations_failed, {"result": "failed"})
        if r.error:
            m.generation_failures.add(1)

    def _scope(self) -> str:
        n, first, last = self._conn.execute(
            "SELECT count(*), min(doc_date), max(doc_date) FROM documents"
        ).fetchone()
        return (
            f"{self._pack.info.scope} Corpus: {n} decisions dated {first} to {last}. "
            "Law may have changed since."
        ).strip()

    def _audit(self, r: AdviceResponse, req: AdviceRequest, retrieved: list[str]) -> None:
        manifest = self._conn.execute(
            "SELECT manifest_id FROM build_manifest ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        self._conn.execute(
            """INSERT INTO request_audit
               (request_id, manifest_id, prompt_version, retrieved_ids, evidence_strength,
                citations_total, citations_failed, latency_ms, question_text,
                adapter_version, environment)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                uuid.UUID(r.request_id),
                manifest[0] if manifest else None,
                r.prompt_version,
                retrieved,
                r.evidence_strength,
                r.citations_total,
                r.citations_failed,
                r.latency_ms,
                req.question if self._settings.audit_store_question else None,
                self._settings.adapter_version or self._client.model,
                self._settings.audit_environment,
            ),
        )
        self._conn.commit()


def search_text(req: AdviceRequest) -> str:
    """Query for retrieval: the question plus the start of the case (embedder limit: 512 tokens)."""
    return f"{req.question}\n{req.case_text}"[:2000]


def _weaker(a: str, b: str) -> str:
    return a if _STRENGTH.get(a, 0) <= _STRENGTH.get(b, 0) else b


def _prompt_version(pack: DomainPack) -> str:
    digest = hashlib.sha256(
        (pack.advice_prompt + json.dumps(pack.advice_schema, sort_keys=True)).encode()
    ).hexdigest()[:8]
    return f"{pack.info.version}-{digest}"
