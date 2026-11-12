"""Stage: re-check a written dataset against leakage rules L1 to L5, independently of the
builder. Fails (exit 1) on any violation."""

import json
from datetime import date

from cles.config import get_settings
from cles.domain.pack import load_pack
from cles.stage import StageContext, stage_main
from cles.training.leakage import check_example, check_split


def latest_dataset(root):
    dirs = [d for d in root.iterdir() if (d / "manifest.json").is_file()] if root.is_dir() else []
    if not dirs:
        raise FileNotFoundError(f"no dataset found in {root}")
    return max(dirs, key=lambda d: (d / "manifest.json").stat().st_mtime)


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    folder = settings.dataset_dir or latest_dataset(settings.training_out_dir)
    manifest = json.loads((folder / "manifest.json").read_text())
    split_date = date.fromisoformat(manifest["split_date"])

    examples = []
    for name in ("train", "eval"):
        path = folder / f"{name}.jsonl"
        examples += [json.loads(line) for line in path.read_text().splitlines() if line]
    violations = check_split(examples)
    for example in examples:
        violations += [
            f"{example['example_id']}: {v}" for v in check_example(example, pack, split_date)
        ]
    if violations:
        raise RuntimeError(f"{len(violations)} leakage violations, first: {violations[:3]}")
    return {"dataset": str(folder), "examples": len(examples), "violations": 0}


if __name__ == "__main__":
    stage_main("check_dataset", run)
