"""Stage: build the rolling-origin folds (ADR 0023): one dataset folder per fold.

The decisions are sorted by date. The newest window is the `test` fold, kept for a final check and
never used for a choice; before it come `FOLD_DEV_COUNT` development folds. Fold k trains on every
decision older than its window and is evaluated on the window itself, so training grows from fold
to fold and every fold obeys leakage rules L1 to L5. Each fold is an ordinary dataset folder
(train.jsonl, eval.jsonl, manifest.json), so `check_dataset`, `train_sft` and `eval_generate` work
on it unchanged (select it with DATASET_DIR).

Training targets are the paid part. They are cached by the hash of their prompt and shared by all
folds (a training example's context depends on its own date only), and evaluation examples need
no target at all. FOLDS_TARGETS=cached (default) writes only what is already cached and reports
the rest as missing; FOLDS_TARGETS=generate pays for the missing ones. `--dry-run` retrieves,
plans and estimates without calling or writing anything.
"""

import json
import logging

from cles.config import ConfigError, get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import load_pack
from cles.extraction.extractor import schema_version
from cles.graph.client import make_driver
from cles.ingestion.chunker import count_tokens
from cles.ingestion.embedder import Embedder
from cles.llm.base import estimate_cost
from cles.retrieval.graph import GraphRetriever
from cles.retrieval.hybrid import HybridRetriever
from cles.stage import StageContext, stage_main
from cles.training.build_dataset import (
    Prepared,
    _generate_missing,
    cached_target,
    collect_examples,
    document_dates,
    load_docs,
    prepare_examples,
    write_dataset,
)
from cles.training.dataset import DocInfo, Fold, fold_split, plan_folds

log = logging.getLogger(__name__)


def describe_fold(docs: list[DocInfo], fold: Fold, split: dict[str, str]) -> dict:
    """Decisions per side and the case-type and outcome mix of the evaluation window."""
    by_id = {d.doc_id: d for d in docs}
    evaluation = [by_id[i] for i, s in split.items() if s == "eval"]
    train_outcomes: dict[str, int] = {}
    for i, side in split.items():
        if side == "train":
            outcome = by_id[i].extraction.get("outcome")
            train_outcomes[outcome] = train_outcomes.get(outcome, 0) + 1
    count = lambda key: {  # noqa: E731
        k: sum(d.extraction.get(key) == k for d in evaluation)
        for k in sorted({d.extraction.get(key) for d in evaluation}, key=str)
    }
    return {
        "name": fold.name,
        "split_date": str(fold.split_date),
        "end_date": str(fold.end_date) if fold.end_date else None,
        "train_decisions": sum(s == "train" for s in split.values()),
        "train_outcomes": train_outcomes,
        "eval_decisions": len(evaluation),
        "eval_case_types": count("case_type"),
        "eval_outcomes": count("outcome"),
    }


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    version = schema_version(pack)
    model = settings.llm_model or "(unset)"
    driver = make_driver(settings)
    try:
        with connect(settings) as conn, recorded_run(conn, "build_folds", ctx.run_id) as stats:
            docs = load_docs(conn, version)
            plan = plan_folds(docs, settings.fold_window, settings.fold_dev_count)
            retriever = HybridRetriever(
                conn, Embedder.from_settings(settings), GraphRetriever(driver, pack), settings
            )
            dates = document_dates(conn)  # also decisions without a valid extraction
            outcomes = {d.doc_id: d.extraction["outcome"] for d in docs}
            cache: dict[str, Prepared] = {}  # training examples shared by the folds
            folds = []
            for fold in plan:
                split = fold_split(docs, fold)
                in_fold = [d for d in docs if d.doc_id in split]
                items = prepare_examples(
                    in_fold,
                    split,
                    fold.split_date,
                    pack,
                    retriever,
                    ctx.limit,
                    cache,
                    outcomes,
                    settings.precedent_rule_min_decisions,
                )
                for item in items:
                    item.doc_dates = dates  # dates of context documents, for the leakage check
                folds.append((fold, split, items, describe_fold(docs, fold, split)))

            wanted = {
                i.example_id: i for _, _, items, _ in folds for i in items if i.split == "train"
            }
            todo = [i for i in wanted.values() if cached_target(conn, i, model) is None]
            est_in = sum(count_tokens(m["content"]) for i in todo for m in i.target_messages)
            est_cost = estimate_cost(
                est_in,
                len(todo) * settings.extraction_output_tokens_estimate,
                settings.llm_price_input_per_mtok,
                settings.llm_price_output_per_mtok,
            )
            summary = {
                "decisions": len(docs),
                "folds": [f[3] for f in folds],
                "train_examples_needed": len(wanted),
                "targets_to_generate": len(todo),
                "est_input_tokens": est_in,
                "est_cost_usd": est_cost,
                "targets": settings.folds_targets,
                "model": model,
            }
            stats.update({k: v for k, v in summary.items() if k != "folds"})
            if ctx.dry_run:
                return summary

            root = settings.folds_out_dir / ctx.run_id[:8]

            def write_all(spent: float) -> list[dict]:
                """Every fold's dataset folder and plan.json, from the targets cached so far."""
                written = []
                for fold, _split, items, described in folds:
                    examples, dropped, missing = collect_examples(
                        conn, items, pack, version, model, fold.split_date
                    )
                    manifest = {
                        "run_id": ctx.run_id,
                        "pack": pack.info.name,
                        "pack_version": pack.info.version,
                        "extraction_version": version,
                        "target_model": model,
                        "split_date": str(fold.split_date),
                        "fold": described,
                        "dropped_for_leakage": dict(dropped),
                        "missing_targets": missing,
                        "cost_usd_this_run": spent,
                    }
                    counts = write_dataset(root / fold.name, examples, manifest)
                    written.append(
                        {
                            **described,
                            "train": counts["train"]["examples"],
                            "missing_targets": missing,
                            "eval": counts["eval"]["examples"],
                            "dropped": dict(dropped),
                        }
                    )
                (root / "plan.json").write_text(json.dumps({"folds": written}, indent=2))
                return written

            spent = 0.0
            generating = settings.folds_targets == "generate" and bool(todo)
            if generating:  # refuse before anything is paid
                ceiling = settings.folds_max_cost_usd
                if ceiling <= 0:
                    raise ConfigError("FOLDS_TARGETS=generate needs FOLDS_MAX_COST_USD (a ceiling)")
                if est_cost is None or est_cost > ceiling:
                    raise ConfigError(
                        f"estimate {est_cost} USD is not within the ceiling {ceiling} USD "
                        "(set LLM_PRICE_INPUT_PER_MTOK and LLM_PRICE_OUTPUT_PER_MTOK)"
                    )
            # Evaluation sets do not depend on targets: write them now, so evaluation can start
            # while the paid targets are still being generated; rewritten when they are done.
            written = write_all(spent)
            if generating:
                spent = _generate_missing(conn, todo, pack, settings, model, ceiling)
                written = write_all(spent)
            return {**summary, "written": str(root), "folds": written, "cost_usd": spent}
    finally:
        driver.close()


if __name__ == "__main__":
    stage_main("build_folds", run)
