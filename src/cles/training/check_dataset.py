"""Stage: re-check a written dataset against leakage rules L1 to L5, independently of the
builder. Fails (exit 1) on any violation. Also reports how well the split measures what it
should (training/evaluation outcome shift, case families across the split); these are
warnings in the summary, not failures (see training/diagnostics.py)."""

import json
from datetime import date

from cles.config import get_settings
from cles.domain.pack import load_pack
from cles.extraction.export import EXPORT_FILE
from cles.stage import StageContext, stage_main
from cles.training.diagnostics import family_candidates, outcome_shift, party_keys
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
    summary = {"dataset": str(folder), "examples": len(examples), "violations": 0}
    shift = outcome_shift(examples)
    summary |= {"outcome_shift": shift["distance"], "decisions": shift["decisions"]}
    summary["outcome_share"] = shift["share"]
    summary["family_candidates"] = _family_candidates(pack, manifest, examples)
    return summary


def _family_candidates(pack, manifest: dict, examples: list[dict]) -> list[dict] | str:
    """Decisions that share a party across the split, from the versioned extraction export."""
    if not EXPORT_FILE.is_file():
        return f"not checked: {EXPORT_FILE} does not exist"
    split_by_doc = {e["doc_id"]: e["split"] for e in examples}
    parties: dict[str, set[str]] = {}
    for line in EXPORT_FILE.read_text().splitlines():
        row = json.loads(line)
        if row["status"] != "ok" or row["doc_id"] not in split_by_doc:
            continue
        if row["schema_version"] != manifest.get("extraction_version"):
            continue
        parties[row["doc_id"]] = party_keys(
            row["result"].get("parties", []),
            pack.training.family_ignore_party_kinds,
            pack.training.family_ignore_name_patterns,
        )
    return family_candidates(parties, split_by_doc)


if __name__ == "__main__":
    stage_main("check_dataset", run)
