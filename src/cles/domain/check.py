"""Stage: validate the configured domain pack."""

from cles.config import get_settings
from cles.domain.pack import load_pack
from cles.stage import StageContext, stage_main


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    return {
        "pack": pack.info.name,
        "version": pack.info.version,
        "node_labels": len(pack.graph.nodes),
        "relationship_types": len(pack.graph.relationships),
        "outcomes": len(pack.outcomes),
        "remedies": len(pack.remedies),
        "query_templates": len(pack.query_templates),
    }


if __name__ == "__main__":
    stage_main("validate_pack", run)
