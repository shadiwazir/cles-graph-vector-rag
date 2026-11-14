"""Stage: LLM-as-judge faithfulness scoring of the evaluated answers (INSTRUCTIONS 19.2 and 19.3a).

The judge checks whether each answer's claims are supported by the context the advisor was given
(per-route verdicts with evidence, plus a 1 to 5 score). It does not judge legal correctness.
It is a trend and triage signal, never an acceptance gate: `judge_calibrate` compares it with
lawyer labels before it is relied on.

Backend interface: `JudgeBackend.judge(system, user) -> (text, tokens_in, tokens_out)`. The default
backend uses the configured OpenAI-compatible client with `JUDGE_MODEL` (paid; sends public case
text to a third party, guard: ALLOW_EXTERNAL_GENERATOR). Known caveat: a judge from the same model
family as a generator tends to favour that generator's answers; set JUDGE_MODEL to another model.
Results go to artifacts/eval/<system>/judge.jsonl, which is also the cache (a rerun costs nothing).
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Protocol

from jsonschema import Draft202012Validator

from cles.config import Settings, get_settings
from cles.evaluation.answers import parse_answer
from cles.evaluation.generate import load_eval_examples, prompt_of, read_done
from cles.inference.guard import check_generator_allowed
from cles.ingestion.chunker import count_tokens
from cles.llm.base import estimate_cost
from cles.llm.openai_client import make_client
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)
EST_OUTPUT_TOKENS = 700


class JudgeBackend(Protocol):
    name: str

    def judge(self, system: str, user: str) -> tuple[str, int, int]: ...


class OpenAIJudge:
    def __init__(self, settings: Settings):
        check_generator_allowed(settings)
        self._client = make_client(settings.model_copy(update={"llm_model": settings.judge_model}))
        self.name = self._client.model

    def judge(self, system: str, user: str) -> tuple[str, int, int]:
        reply = self._client.complete_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        return reply.text, reply.input_tokens, reply.output_tokens


def pack_files(settings: Settings) -> tuple[str, dict]:
    folder = settings.domain_packs_dir / settings.domain_pack
    return (folder / "judge_prompt.md").read_text(), json.loads(
        (folder / "judge_schema.json").read_text()
    )


def build_user_prompt(example: dict, advice: dict) -> str:
    """The context the advisor saw (the stored user message) and the answer to check."""
    context = prompt_of(example)[1]["content"]
    return f"{context}\n\nANSWER (JSON):\n{json.dumps(advice, ensure_ascii=False)}"


def judge_one(
    backend: JudgeBackend, system: str, schema: dict, example: dict, advice: dict
) -> dict:
    validator = Draft202012Validator(schema)
    text, tin, tout = backend.judge(system, build_user_prompt(example, advice))
    result, errors = parse_answer(text, validator)
    return {
        "example_id": example["example_id"],
        "judgement": result if not errors else None,
        "errors": errors,
        "input_tokens": tin,
        "output_tokens": tout,
        "judge_model": backend.name,
    }


def judged_systems(settings: Settings) -> list[str]:
    return [
        d.name for d in sorted(settings.eval_out_dir.glob("*/")) if (d / "outputs.jsonl").is_file()
    ]


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    system_prompt, schema = pack_files(settings)
    folder, examples = load_eval_examples(settings)
    validator = Draft202012Validator(
        json.loads(
            (settings.domain_packs_dir / settings.domain_pack / "advice_schema.json").read_text()
        )
    )
    work: list[tuple[str, dict, dict]] = []
    skipped = 0
    for name in judged_systems(settings):
        outputs = read_done(settings.eval_out_dir / name / "outputs.jsonl")
        done = {  # invalid judgements are retried, not cached
            k: v
            for k, v in read_done(settings.eval_out_dir / name / "judge.jsonl").items()
            if v.get("judgement")
        }
        for e in examples:
            out = outputs.get(e["example_id"])
            advice = parse_answer(out["text"], validator)[0] if out else None
            if advice is None or e["example_id"] in done:
                skipped += 1
                continue
            work.append((name, e, advice))
    work = work[: ctx.limit]
    tokens_in = sum(count_tokens(build_user_prompt(e, a) + system_prompt) for _, e, a in work)
    estimate = estimate_cost(
        tokens_in,
        EST_OUTPUT_TOKENS * len(work),
        settings.llm_price_input_per_mtok,
        settings.llm_price_output_per_mtok,
    )
    summary = {
        "to_judge": len(work),
        "skipped": skipped,
        "judge_model": settings.judge_model,
        "est_cost_usd": estimate,
    }
    if ctx.dry_run or not work:
        return summary

    backend = OpenAIJudge(settings)
    cost = 0.0
    results: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=settings.llm_concurrency) as pool:
        futures = {
            pool.submit(judge_one, backend, system_prompt, schema, e, a): name
            for name, e, a in work
        }
        for future in as_completed(futures):
            row = future.result()
            results.setdefault(futures[future], []).append(row)
            cost += (
                estimate_cost(
                    row["input_tokens"],
                    row["output_tokens"],
                    settings.llm_price_input_per_mtok,
                    settings.llm_price_output_per_mtok,
                )
                or 0.0
            )
    for name, rows in results.items():
        with (settings.eval_out_dir / name / "judge.jsonl").open("a") as out:
            for row in rows:
                out.write(json.dumps(row) + "\n")
    failed = sum(r["judgement"] is None for rows in results.values() for r in rows)
    return summary | {
        "judged": sum(map(len, results.values())),
        "invalid": failed,
        "cost_usd": cost,
    }


def mean_faithfulness(path: Path) -> tuple[int, float] | None:
    """(count, mean faithfulness) of a judge.jsonl, or None when there is none."""
    rows = [r for r in read_done(path).values() if r.get("judgement")]
    if not rows:
        return None
    scores = [r["judgement"]["faithfulness"] for r in rows]
    return len(scores), sum(scores) / len(scores)


if __name__ == "__main__":
    stage_main("judge_eval", run)
