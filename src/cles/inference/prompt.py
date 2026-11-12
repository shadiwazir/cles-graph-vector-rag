"""Build the generation prompt from the case, the question and the retrieved context."""

import json

from cles.domain.pack import DomainPack
from cles.retrieval.types import ContextPack

MAX_FACT_ROWS = 15  # graph rows per template shown to the model


def build_messages(
    pack: DomainPack, case_text: str, question: str, context: ContextPack
) -> list[dict[str, str]]:
    system = (
        f"{pack.advice_prompt}\n\nReturn one JSON object that matches this JSON Schema:\n"
        f"{json.dumps(pack.advice_schema)}"
    )
    user = (
        f"CASE (as described by the lawyer):\n{case_text}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"RETRIEVED PASSAGES (cite only these; use the case id and paragraph shown):\n"
        f"{render_passages(context)}\n\n"
        f"GRAPH FACTS (structured, from earlier decisions):\n{render_graph(context)}\n\n"
        f"Retrieval found {context.evidence_strength} evidence."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def render_passages(context: ContextPack) -> str:
    if not context.passages:
        return "(none found)"
    return "\n\n".join(f"[{p.label}] {p.title}\n{p.text}" for p in context.passages)


def render_graph(context: ContextPack) -> str:
    lines = []
    for name, rows in context.graph.items():
        for row in rows[:MAX_FACT_ROWS]:
            lines.append(f"{name}: {json.dumps(row, default=str)}")
    return "\n".join(lines) or "(none)"
