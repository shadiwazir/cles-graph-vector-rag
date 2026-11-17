"""Mapping logic is tested without Neo4j; the writer test needs the Compose Neo4j."""

import json
import os
from pathlib import Path

import pytest

from cles.config import get_settings
from cles.domain.pack import load_pack
from cles.graph.writer import GraphWriter, _build_items, normalise_key

ROOT = Path(__file__).parent.parent
PACK = load_pack(ROOT / "domain_packs", "legal_ca_on")
EXTRACTION = json.loads((ROOT / "tests/fixtures/extraction_2026_ONCA_724.json").read_text())


def link(field):
    return next(item for item in PACK.mapping.links if item.field == field)


def test_normalise_key():
    assert normalise_key("  Favreau   J.A. ") == "favreau j.a."


def test_build_items_for_scalars_and_objects():
    judges = _build_items(EXTRACTION["judges"], link("judges"))
    assert [i["key"] for i in judges] == ["favreau", "madsen", "osborne"]
    assert judges[0]["props"] == {"name": "Favreau"}
    lawyers = _build_items(EXTRACTION["lawyers"], link("lawyers"))
    assert lawyers[0]["rel_props"] == {"side": "respondent"}
    cites = _build_items(EXTRACTION["citations"], link("citations"))
    assert cites[0]["key"] == "2015 ONCA 733" and cites[0]["rel_props"]["treatment"] == "applied"


def test_empty_and_duplicate_values_are_skipped():
    assert _build_items(None, link("judges")) == []
    assert len(_build_items(["A", "a ", "A"], link("judges"))) == 1


@pytest.fixture
def driver():
    from neo4j import GraphDatabase

    from cles.graph.client import ensure_schema

    settings = get_settings()
    try:
        drv = GraphDatabase.driver(settings.neo4j_uri, auth=settings.neo4j_auth())
        drv.verify_connectivity()
    except Exception:
        pytest.skip("Neo4j not available")
    with drv.session() as s:
        nodes = s.run("MATCH (n) RETURN count(n)").single()[0]
    if nodes and os.environ.get("TEST_NEO4J_WIPE") != "1":
        # These tests empty the graph. On the project's own Neo4j that would destroy the loaded
        # decisions (it happened once), so they run only on an empty or throwaway instance.
        drv.close()
        pytest.skip(f"Neo4j holds {nodes} nodes; set TEST_NEO4J_WIPE=1 to let the tests wipe it")
    ensure_schema(drv, PACK.graph)
    yield drv
    with drv.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    drv.close()


def count(driver, cypher):
    with driver.session() as s:
        return s.run(cypher).single()[0]


def test_writer_builds_graph_and_is_idempotent(driver):
    writer = GraphWriter(driver, PACK)
    writer.write(EXTRACTION)
    first = (
        count(driver, "MATCH (n) RETURN count(n)"),
        count(driver, "MATCH ()-[r]->() RETURN count(r)"),
    )
    writer.write(EXTRACTION)
    second = (
        count(driver, "MATCH (n) RETURN count(n)"),
        count(driver, "MATCH ()-[r]->() RETURN count(r)"),
    )
    assert first == second and first[0] > 5

    assert (
        count(driver, "MATCH (c:Case {case_id:'2026 ONCA 724'})-[:SAT_ON]->(j) RETURN count(j)")
        == 3
    )
    assert (
        count(
            driver,
            "MATCH (:Case {case_id:'2026 ONCA 724'})-[:RESULTED_IN]->"
            "(o:Outcome {label:'appeal_dismissed'}) RETURN count(o)",
        )
        == 1
    )
    # a cited case outside the corpus exists only as a stub
    assert count(driver, "MATCH (c:Case {case_id:'2015 ONCA 733'}) RETURN c.in_corpus") is False
    assert count(driver, "MATCH (c:Case {case_id:'2026 ONCA 724'}) RETURN c.in_corpus") is True


def test_changed_extraction_replaces_relationships(driver):
    writer = GraphWriter(driver, PACK)
    writer.write(EXTRACTION)
    changed = {**EXTRACTION, "judges": ["Favreau"]}
    writer.write(changed)
    assert (
        count(driver, "MATCH (:Case {case_id:'2026 ONCA 724'})-[:SAT_ON]->(j) RETURN count(j)") == 1
    )


def test_cited_stub_keeps_in_corpus_true_when_already_present(driver):
    writer = GraphWriter(driver, PACK)
    cited = {**EXTRACTION, "case_id": "2015 ONCA 733", "title": "Scaduto", "citations": []}
    writer.write(cited)
    writer.write(EXTRACTION)
    assert count(driver, "MATCH (c:Case {case_id:'2015 ONCA 733'}) RETURN c.in_corpus") is True


def test_remedies_become_remedy_nodes(driver):
    writer = GraphWriter(driver, PACK)
    writer.write({**EXTRACTION, "outcome": "appeal_allowed", "remedies": ["sentence_increased"]})
    assert (
        count(
            driver,
            "MATCH (:Case {case_id:'2026 ONCA 724'})-[:ORDERED]->"
            "(m:Remedy {label:'sentence_increased'})"
            " RETURN count(m)",
        )
        == 1
    )
