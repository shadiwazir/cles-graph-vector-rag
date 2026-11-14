"""Results explorer: a small read-only dashboard that compares the evaluated systems side by side.

Reads files only (the dataset, artifacts/eval/*/outputs.jsonl and report.json from `eval_score`):
no database, no model, no network. Run:
    uv run uvicorn cles.evaluation.explorer:create_app --factory --port 8001
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field

from cles.config import Settings, get_settings
from cles.domain.pack import load_pack
from cles.evaluation.answers import parse_answer
from cles.evaluation.calibrate import read_labels
from cles.evaluation.generate import load_eval_examples, read_done

STATIC_DIR = Path(__file__).parent / "static"


def build_data(settings: Settings) -> dict:
    """Everything the page needs in one object: statistics, examples and each system's answer."""
    report_path = settings.eval_out_dir / "report.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"{report_path} not found: run `cles run eval_score` first")
    report = json.loads(report_path.read_text())
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    validator = Draft202012Validator(pack.advice_schema)
    folder, examples = load_eval_examples(settings)
    systems = list(report["rows"])
    outputs = {s: read_done(settings.eval_out_dir / s / "outputs.jsonl") for s in systems}
    judged = {s: read_done(settings.eval_out_dir / s / "judge.jsonl") for s in systems}
    labels = read_labels(settings.eval_labels_file)
    rows = {s: {r["example_id"]: r for r in report["rows"][s]} for s in systems}
    shown = [e for e in examples if all(e["example_id"] in rows[s] for s in systems)]

    items = []
    for e in shown:
        answers = {}
        for s in systems:
            out = outputs[s][e["example_id"]]
            advice, errors = parse_answer(out["text"], validator)
            row = rows[s][e["example_id"]]
            answers[s] = {
                "advice": advice,
                "schema_errors": errors,
                "raw": None if advice is not None else out["text"][:3000],
                "metrics": {k: v for k, v in row.items() if k != "citation_checks"},
                "citation_checks": row.get("citation_checks", []),
                "output_tokens": out.get("output_tokens"),
                "model": out.get("model"),
                "judge": (judged[s].get(e["example_id"]) or {}).get("judgement"),
                "label": labels.get((e["example_id"], s)),
            }
        items.append(
            {
                "example_id": e["example_id"],
                "doc_id": e["doc_id"],
                "stage": e["stage"],
                "question": e["question"],
                "case_text": e["case_text"],
                "outcome": e["outcome"],
                "remedies": e.get("remedies", []),
                "evidence_strength": e["evidence_strength"],
                "context_docs": [c["doc_id"] for c in e.get("context_docs", [])],
                "target": _target(e),
                "answers": answers,
            }
        )
    return {
        "dataset": str(folder),
        "systems": systems,
        "results": report["results"],
        "extra": {s: _extra_stats(items, s) for s in systems},
        "examples": items,
        "labels_file": str(settings.eval_labels_file),
    }


def _target(example: dict) -> dict | None:
    """The hindsight-written training target (for reference only; it is not ground truth)."""
    last = example["messages"][-1]
    if last["role"] != "assistant":
        return None
    try:
        return json.loads(last["content"])
    except json.JSONDecodeError:
        return None


def _extra_stats(items: list[dict], system: str) -> dict:
    answers = [i["answers"][system] for i in items]
    tokens = [a["output_tokens"] for a in answers if a["output_tokens"]]
    routes = [a["metrics"]["routes"] for a in answers]
    return {
        "mean_output_tokens": sum(tokens) / len(tokens) if tokens else None,
        "mean_routes": sum(routes) / len(routes) if routes else None,
        "model": next((a["model"] for a in answers if a["model"]), None),
    }


class LabelBody(BaseModel):
    example_id: str
    system: str
    faithfulness: int = Field(ge=1, le=5)  # is every claim supported by the supplied context?
    usefulness: int = Field(ge=1, le=5)  # would this help a lawyer decide what to do?
    comment: str = Field(default="", max_length=2000)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="CLES results explorer")
    cache: dict = {}

    @app.get("/", include_in_schema=False)
    def page() -> FileResponse:
        return FileResponse(STATIC_DIR / "explorer.html")

    @app.get("/api/data")
    def data() -> dict:
        report = settings.eval_out_dir / "report.json"
        stamp = report.stat().st_mtime if report.is_file() else None
        if cache.get("stamp") != stamp or "data" not in cache:  # reload after a new eval_score
            try:
                cache["data"] = build_data(settings)
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            cache["stamp"] = stamp
        return cache["data"]

    @app.post("/api/label")
    def label(body: LabelBody) -> dict:
        """Append one human review (the file is the record; the latest label per answer wins)."""
        data()  # makes sure the example exists in the current report
        known = {
            (i["example_id"], s)
            for i in cache["data"]["examples"]
            for s in cache["data"]["systems"]
        }
        if (body.example_id, body.system) not in known:
            raise HTTPException(status_code=404, detail="unknown example or system")
        row = {**body.model_dump(), "ts": datetime.now(UTC).isoformat(timespec="seconds")}
        settings.eval_labels_file.parent.mkdir(parents=True, exist_ok=True)
        with settings.eval_labels_file.open("a") as out:
            out.write(json.dumps(row) + "\n")
        cache.pop("data", None)  # reload so the saved label shows up
        return row

    return app
