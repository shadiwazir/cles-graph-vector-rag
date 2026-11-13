"""Conversation support: fold earlier questions and answers into the case description.

The model was fine-tuned on single-turn prompts (case, one question, retrieved passages), so a
conversation is not sent as chat turns. Instead the earlier turns are summarised and appended to
the case text, and the prompt keeps the shape the model was trained on (ADR 0018). The summary
is compact and the oldest turns are dropped first when it exceeds the token budget.
"""

from dataclasses import dataclass

from cles.ingestion.chunker import count_tokens

POSITION_CHARS = 400  # case_position is cut to this length in the summary
MAX_ROUTES = 5
MAX_STEPS = 4


@dataclass(frozen=True)
class Turn:
    question: str
    advice: dict | None = None  # the advice returned for that question, if it succeeded


def summarise_advice(advice: dict | None) -> str:
    """Key points of an earlier answer: position, routes with likelihood, next steps."""
    if not isinstance(advice, dict):
        return "(no advice was produced)"
    parts = []
    if advice.get("stage"):
        parts.append(f"stage {advice['stage']}")
    if advice.get("case_position"):
        parts.append(f"position: {str(advice['case_position'])[:POSITION_CHARS]}")
    routes = [r for r in advice.get("routes") or [] if isinstance(r, dict)][:MAX_ROUTES]
    if routes:
        names = "; ".join(f"{r.get('name', '?')} ({r.get('likelihood', '?')})" for r in routes)
        parts.append(f"routes: {names}")
    steps = [str(s) for s in advice.get("recommended_next_steps") or []][:MAX_STEPS]
    if steps:
        parts.append(f"next steps: {'; '.join(steps)}")
    return ". ".join(parts) or "(empty advice)"


def fold_history(case_text: str, history: list[Turn], max_tokens: int) -> tuple[str, int]:
    """Case text plus a transcript of the newest turns that fit in `max_tokens`.

    Returns (text, number of turns dropped). The case text itself is never cut.
    """
    entries = [
        f"Earlier question {i}: {t.question}\nAdvice given: {summarise_advice(t.advice)}"
        for i, t in enumerate(history, start=1)
    ]
    kept: list[str] = []
    used = 0
    for entry in reversed(entries):  # newest first
        cost = count_tokens(entry)
        if used + cost > max_tokens:
            break
        kept.append(entry)
        used += cost
    dropped = len(entries) - len(kept)
    if not kept:
        return case_text, dropped
    header = "EARLIER IN THIS CONVERSATION (the lawyer's earlier questions and the advice given):"
    omitted = f"\n({dropped} earlier turns omitted)" if dropped else ""
    return f"{case_text}\n\n{header}{omitted}\n" + "\n\n".join(reversed(kept)), dropped
