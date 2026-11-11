from pathlib import Path

import pytest

from cles.domain.pack import PackError, load_pack

PACKS = Path(__file__).parent.parent / "domain_packs"


def test_legal_pack_loads():
    pack = load_pack(PACKS, "legal_ca_on")
    assert "Case" in pack.graph.nodes
    assert "appeal_allowed" in pack.outcomes
    assert pack.query_templates


def test_missing_pack_folder(tmp_path):
    with pytest.raises(PackError, match="not found"):
        load_pack(tmp_path, "nope")


def _copy_pack(tmp_path: Path) -> Path:
    import shutil

    shutil.copytree(PACKS / "legal_ca_on", tmp_path / "p")
    return tmp_path


def test_template_with_undeclared_label_is_rejected(tmp_path):
    root = _copy_pack(tmp_path)
    (root / "p" / "query_templates.yaml").write_text(
        "templates:\n  bad: |\n    MATCH (x:Ghost) WHERE x.d < $as_of RETURN x\n"
    )
    with pytest.raises(PackError, match="undeclared label"):
        load_pack(root, "p")


def test_template_without_as_of_is_rejected(tmp_path):
    root = _copy_pack(tmp_path)
    (root / "p" / "query_templates.yaml").write_text(
        "templates:\n  bad: |\n    MATCH (c:Case) RETURN c\n"
    )
    with pytest.raises(PackError, match="as_of"):
        load_pack(root, "p")


def test_missing_file_is_reported(tmp_path):
    root = _copy_pack(tmp_path)
    (root / "p" / "outcomes.yaml").unlink()
    with pytest.raises(PackError, match="outcomes.yaml"):
        load_pack(root, "p")
