"""Stage: compare the LLM judge with lawyer labels (INSTRUCTIONS 19.2 item 3).

Reads artifacts/eval/<system>/judge.jsonl and the labels saved by the results explorer
(eval/labels/labels.jsonl, faithfulness 1 to 5). Reports agreement as quadratic-weighted Cohen's
kappa and Spearman correlation. The judge counts as calibrated only with at least MIN_LABELS
labelled answers and kappa >= KAPPA_OK; until then judge scores are a rough trend signal only.
Re-run whenever the judge model or the judge prompt changes.
"""

import json
from pathlib import Path

from cles.config import get_settings
from cles.evaluation.generate import read_done
from cles.evaluation.judge import judged_systems
from cles.stage import StageContext, stage_main

MIN_LABELS = 30
KAPPA_OK = 0.6


def read_labels(path: Path) -> dict[tuple[str, str], dict]:
    """Latest label per (example_id, system)."""
    if not path.is_file():
        return {}
    labels = {}
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            labels[(row["example_id"], row["system"])] = row
    return labels


def weighted_kappa(a: list[int], b: list[int], levels: int = 5) -> float | None:
    """Quadratic-weighted Cohen's kappa for ratings 1..levels; None when undefined."""
    n = len(a)
    if n == 0:
        return None
    observed = [[0.0] * levels for _ in range(levels)]
    for x, y in zip(a, b, strict=True):
        observed[x - 1][y - 1] += 1
    row = [sum(r) for r in observed]
    col = [sum(observed[i][j] for i in range(levels)) for j in range(levels)]
    num = den = 0.0
    for i in range(levels):
        for j in range(levels):
            weight = (i - j) ** 2 / (levels - 1) ** 2
            num += weight * observed[i][j]
            den += weight * row[i] * col[j] / n
    return None if den == 0 else 1 - num / den


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1  # ties share the mean rank
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2:
        return None
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    var = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return None if var == 0 else cov / var


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    labels = read_labels(settings.eval_labels_file)
    human, judge = [], []
    for system in judged_systems(settings):
        for example_id, row in read_done(settings.eval_out_dir / system / "judge.jsonl").items():
            label = labels.get((example_id, system))
            if row.get("judgement") and label and label.get("faithfulness"):
                human.append(int(label["faithfulness"]))
                judge.append(int(row["judgement"]["faithfulness"]))
    kappa, rho = weighted_kappa(human, judge), spearman(human, judge)
    within_one = (
        sum(abs(h - j) <= 1 for h, j in zip(human, judge, strict=True)) / len(human)
        if human
        else None
    )
    calibrated = len(human) >= MIN_LABELS and kappa is not None and kappa >= KAPPA_OK
    result = {
        "labelled_answers": len(human),
        "labels_total": len(labels),
        "kappa_weighted": kappa,
        "spearman": rho,
        "within_one_point": within_one,
        "calibrated": calibrated,
        "note": (
            "calibrated"
            if calibrated
            else f"not calibrated: needs {MIN_LABELS}+ labelled answers and kappa >= {KAPPA_OK}"
        ),
    }
    if not ctx.dry_run:
        out = settings.eval_out_dir / "judge_calibration.json"
        out.write_text(json.dumps(result, indent=1) + "\n")
    return result


if __name__ == "__main__":
    stage_main("judge_calibrate", run)
