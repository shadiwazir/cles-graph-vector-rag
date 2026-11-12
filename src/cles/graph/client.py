"""Neo4j driver and schema setup (constraints and indexes come from the domain pack)."""

from neo4j import Driver, GraphDatabase

from cles.config import Settings
from cles.domain.pack import GraphSchema


def make_driver(settings: Settings) -> Driver:
    return GraphDatabase.driver(settings.neo4j_uri, auth=settings.neo4j_auth())


def ensure_schema(driver: Driver, graph: GraphSchema) -> None:
    """Create a uniqueness constraint per node key and the extra indexes. Idempotent.

    Names are interpolated into Cypher, which is safe because `GraphSchema` only accepts
    plain identifiers.
    """
    with driver.session() as session:
        for label, node in graph.nodes.items():
            session.run(
                f"CREATE CONSTRAINT {label}_{node.key}_unique IF NOT EXISTS "
                f"FOR (n:`{label}`) REQUIRE n.`{node.key}` IS UNIQUE"
            )
            for prop in node.indexes:
                session.run(
                    f"CREATE INDEX {label}_{prop}_idx IF NOT EXISTS "
                    f"FOR (n:`{label}`) ON (n.`{prop}`)"
                )
