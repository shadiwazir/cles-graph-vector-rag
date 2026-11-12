"""Generic graph writer: extraction JSON -> nodes and relationships, driven by the pack mapping.

Labels, relationship types and property names are written into the Cypher text, but only after
`load_pack` has checked them against the declared schema (plain identifiers only). Every value
goes through parameters.
"""

from datetime import date
from typing import Any

from neo4j import Driver, ManagedTransaction

from cles.domain.pack import DomainPack, LinkMapping

SELF = "$self"


def normalise_key(value: str) -> str:
    return " ".join(value.split()).casefold()


class GraphWriter:
    def __init__(self, driver: Driver, pack: DomainPack):
        self._driver = driver
        self._pack = pack

    def write(self, extraction: dict) -> None:
        """Write one document. Re-running with the same input leaves the graph unchanged;
        with changed input, the relationships of this document are replaced."""
        with self._driver.session() as session:
            session.execute_write(self._write_tx, extraction)

    def _write_tx(self, tx: ManagedTransaction, extraction: dict) -> None:
        root = self._pack.mapping.root
        node = self._pack.graph.nodes[root.label]
        key_value = extraction[root.key]
        props = _mapped(extraction, root.properties) | root.constants
        for prop, kind in root.types.items():
            if prop in props:
                props[prop] = _convert(props[prop], kind)
        tx.run(
            f"MERGE (r:`{root.label}` {{`{node.key}`: $key}}) SET r += $props",
            key=key_value,
            props=props,
        )
        for link in self._pack.mapping.links:
            self._write_link(tx, root.label, node.key, key_value, link, extraction)

    def _write_link(
        self, tx, root_label: str, root_key: str, root_value: str, link: LinkMapping, extraction
    ) -> None:
        target_key = self._pack.graph.nodes[link.label].key
        rel = f"[x:`{link.relationship}`]"
        pattern = f"(r)-{rel}->(n)" if link.direction == "out" else f"(n)-{rel}->(r)"
        match_root = f"MATCH (r:`{root_label}` {{`{root_key}`: $root}})"

        # Replace this document's relationships of this type, so a changed extraction
        # does not leave stale edges behind.
        tx.run(f"{match_root} MATCH {pattern} DELETE x", root=root_value)

        items = _build_items(extraction.get(link.field), link)
        if not items:
            return
        # ON CREATE: constants such as in_corpus=false apply only to nodes created here, so a
        # case that is already in the graph (in_corpus=true) is not overwritten.
        tx.run(
            f"{match_root} UNWIND $items AS item "
            f"MERGE (n:`{link.label}` {{`{target_key}`: item.key}}) "
            f"ON CREATE SET n += $on_create "
            f"SET n += item.props "
            f"MERGE {pattern} SET x += item.rel_props",
            root=root_value,
            items=items,
            on_create=link.on_create,
        )


def _build_items(value: Any, link: LinkMapping) -> list[dict]:
    """Turn a field value (None, a scalar or a list) into rows for the UNWIND query."""
    if value in (None, "", []):
        return []
    raw = value if isinstance(value, list) else [value]
    items, seen = [], set()
    for entry in raw:
        if isinstance(entry, dict):
            if not entry.get(link.key_field or ""):
                continue
            key_source = str(entry[link.key_field])
        else:
            key_source = str(entry)
        key = normalise_key(key_source) if link.key_normalise else key_source.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "key": key,
                "props": _item_props(entry, link.properties),
                "rel_props": _item_props(entry, link.rel_properties),
            }
        )
    return items


def _item_props(entry: Any, mapping: dict[str, str]) -> dict:
    out = {}
    for prop, source in mapping.items():
        val = entry if source == SELF else (entry.get(source) if isinstance(entry, dict) else None)
        if val is not None:
            out[prop] = val
    return out


def _mapped(extraction: dict, mapping: dict[str, str]) -> dict:
    return {p: extraction[f] for p, f in mapping.items() if extraction.get(f) is not None}


def _convert(value: Any, kind: str) -> Any:
    if kind == "date":
        return date.fromisoformat(value)
    raise ValueError(f"unknown type {kind}")
