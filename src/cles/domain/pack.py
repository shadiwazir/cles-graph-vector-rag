"""Domain pack loader and validator.

A pack is a folder of config files (see INSTRUCTIONS.md section 5). Generic code reads
labels, relationships and prompts from the pack and never hard-codes a domain.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, model_validator

REQUIRED_FILES = (
    "pack.yaml",
    "graph_schema.yaml",
    "graph_mapping.yaml",
    "extraction_prompt.md",
    "extraction_schema.json",
    "sections.yaml",
    "outcomes.yaml",
    "advice_schema.json",
    "advice_prompt.md",
    "query_templates.yaml",
    "training.yaml",
    "target_prompt.md",
)

# Cypher fragments such as (c:Case) and [r:CITES]
_LABEL_RE = re.compile(r"\(\s*\w*\s*:\s*(\w+)")
_REL_RE = re.compile(r"\[\s*\w*\s*:\s*(\w+)")


class PackError(ValueError):
    """The domain pack is missing files or is inconsistent."""


class LeakCheck(BaseModel):
    """Rejects an extraction whose "known so far" text mentions the decision itself."""

    list_field: str  # extraction field holding the stage list
    text_field: str  # field inside each item that must not leak
    patterns: list[str]  # regexes for phrases that reveal the decision

    @model_validator(mode="after")
    def _compile(self) -> "LeakCheck":
        for pattern in self.patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid leak pattern {pattern!r}: {exc}") from exc
        return self


class PackInfo(BaseModel):
    name: str
    version: str
    language: str = "en"
    description: str = ""
    # Extraction fields the parser already knows exactly: field -> documents column.
    # They override what the model returns (the model must not invent identity fields).
    known_fields: dict[str, Literal["doc_id", "title", "doc_date"]] = Field(default_factory=dict)
    leak_check: LeakCheck | None = None
    disclaimer: str = (
        "Decision support for a qualified professional; not professional advice. Review before use."
    )
    scope: str = ""  # what the corpus covers, shown with every answer
    # Highest likelihood allowed per stage (before a decision exists, results are uncertain).
    likelihood_caps_by_stage: dict[str, Literal["low", "medium", "high"]] = Field(
        default_factory=dict
    )


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class NodeType(BaseModel):
    key: str
    properties: list[str] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list)  # extra single-property indexes


class RelType(BaseModel):
    type: str
    source: str
    target: str
    properties: list[str] = Field(default_factory=list)


class GraphSchema(BaseModel):
    nodes: dict[str, NodeType]
    relationships: list[RelType]

    @model_validator(mode="after")
    def _endpoints_exist(self) -> "GraphSchema":
        # Labels, types and properties are written into Cypher text, so they must be plain names.
        names = [*self.nodes, *(r.type for r in self.relationships)]
        for node in self.nodes.values():
            names += [node.key, *node.properties, *node.indexes]
        for rel in self.relationships:
            names += rel.properties
        for name in names:
            if not _IDENTIFIER.match(name):
                raise ValueError(f"'{name}' is not a valid graph identifier")
        for rel in self.relationships:
            for end in (rel.source, rel.target):
                if end not in self.nodes:
                    raise ValueError(f"relationship {rel.type} uses unknown node label {end}")
        return self


class MetadataConfig(BaseModel):
    title_pattern: str
    date_pattern: str
    date_format: str


class SectionConfig(BaseModel):
    """How to read a document: paragraph markers, noise, headings, metadata."""

    paragraph_marker: str
    noise_lines: list[str] = Field(default_factory=list)
    heading_pattern: str | None = None
    heading_title_pattern: str | None = None
    section_keywords: dict[str, list[str]] = Field(default_factory=dict)
    metadata: MetadataConfig

    @model_validator(mode="after")
    def _patterns_compile(self) -> "SectionConfig":
        patterns = [
            self.paragraph_marker,
            *self.noise_lines,
            self.metadata.title_pattern,
            self.metadata.date_pattern,
        ]
        patterns += [p for p in (self.heading_pattern, self.heading_title_pattern) if p]
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc
        return self


class TrainingConfig(BaseModel):
    """Per-domain settings for building training examples."""

    questions: dict[str, list[str]]  # stage -> questions a user might ask at that stage
    # Before a decision exists, a route is a procedural path, not an appeal result: at these
    # stages the first route's name must not match the patterns.
    early_stages: list[str] = Field(default_factory=list)
    early_route_name_patterns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _not_empty(self) -> "TrainingConfig":
        if not self.questions or any(not qs for qs in self.questions.values()):
            raise ValueError("every stage needs at least one question")
        for pattern in self.early_route_name_patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc
        return self


class RootMapping(BaseModel):
    """The node created for each document (for example the case itself)."""

    label: str
    key: str  # extraction field holding the node key
    properties: dict[str, str] = Field(default_factory=dict)  # graph property -> field
    types: dict[str, Literal["date"]] = Field(default_factory=dict)  # property -> value type
    constants: dict[str, Any] = Field(default_factory=dict)  # always set on the node


class LinkMapping(BaseModel):
    """A list (or single value) in the extraction that becomes nodes plus relationships."""

    field: str
    label: str
    key_field: str | None = None  # object items: field holding the key; None: the item is the key
    key_normalise: bool = True  # case-fold and collapse spaces in the key
    properties: dict[str, str] = Field(default_factory=dict)  # node property -> field ("$self")
    on_create: dict[str, Any] = Field(default_factory=dict)  # constants set only when created
    relationship: str
    direction: Literal["out", "in"] = "out"  # out: root->node, in: node->root
    rel_properties: dict[str, str] = Field(default_factory=dict)


class GraphMapping(BaseModel):
    root: RootMapping
    links: list[LinkMapping]


@dataclass(frozen=True)
class DomainPack:
    path: Path
    info: PackInfo
    graph: GraphSchema
    mapping: GraphMapping
    training: TrainingConfig
    target_prompt: str
    outcomes: list[str]
    remedies: list[str]
    sections: SectionConfig
    query_templates: dict[str, str]
    extraction_schema: dict
    advice_schema: dict
    extraction_prompt: str
    advice_prompt: str


def load_pack(packs_dir: Path, name: str) -> DomainPack:
    """Load and validate `packs_dir/name`. Raises PackError with a clear message."""
    path = packs_dir / name
    if not path.is_dir():
        raise PackError(f"domain pack folder not found: {path}")
    missing = [f for f in REQUIRED_FILES if not (path / f).is_file()]
    if missing:
        raise PackError(f"pack '{name}' is missing files: {', '.join(missing)}")

    try:
        info = PackInfo(**_yaml(path / "pack.yaml"))
        graph = GraphSchema(**_yaml(path / "graph_schema.yaml"))
        sections = SectionConfig(**_yaml(path / "sections.yaml"))
    except ValueError as exc:
        raise PackError(f"pack '{name}': {exc}") from exc

    mapping = _load_mapping(path, graph)
    try:
        training = TrainingConfig(**_yaml(path / "training.yaml"))
    except ValueError as exc:
        raise PackError(f"training.yaml: {exc}") from exc
    outcome_file = _yaml(path / "outcomes.yaml")
    outcomes = outcome_file.get("outcomes", [])
    remedies = outcome_file.get("remedies", [])
    for name, values in (("outcomes", outcomes), ("remedies", remedies)):
        if len(set(values)) != len(values):
            raise PackError(f"outcomes.yaml: {name} must be unique")
    if not outcomes:
        raise PackError("outcomes.yaml must list at least one outcome")

    schemas = {}
    for fname in ("extraction_schema.json", "advice_schema.json"):
        schema = json.loads((path / fname).read_text(encoding="utf-8"))
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            raise PackError(f"{fname} is not a valid JSON Schema: {exc}") from exc
        schemas[fname] = schema

    templates = _yaml(path / "query_templates.yaml").get("templates", {})
    _check_templates(templates, graph)

    return DomainPack(
        path=path,
        info=info,
        graph=graph,
        mapping=mapping,
        training=training,
        target_prompt=(path / "target_prompt.md").read_text(encoding="utf-8"),
        outcomes=outcomes,
        remedies=remedies,
        sections=sections,
        query_templates=templates,
        extraction_schema=schemas["extraction_schema.json"],
        advice_schema=schemas["advice_schema.json"],
        extraction_prompt=(path / "extraction_prompt.md").read_text(encoding="utf-8"),
        advice_prompt=(path / "advice_prompt.md").read_text(encoding="utf-8"),
    )


def _check_templates(templates: dict[str, str], graph: GraphSchema) -> None:
    """Every template may use only declared labels and relationship types, and must
    filter by `$as_of` so retrieval never returns later cases (leakage rule L3)."""
    labels = set(graph.nodes)
    rels = {r.type for r in graph.relationships}
    for name, cypher in templates.items():
        for label in _LABEL_RE.findall(cypher):
            if label not in labels:
                raise PackError(f"template '{name}' uses undeclared label '{label}'")
        for rel in _REL_RE.findall(cypher):
            if rel not in rels:
                raise PackError(f"template '{name}' uses undeclared relationship '{rel}'")
        if "$as_of" not in cypher:
            raise PackError(f"template '{name}' must filter on $as_of")


def _load_mapping(path: Path, graph: GraphSchema) -> GraphMapping:
    """Read graph_mapping.yaml and check it only uses what graph_schema.yaml declares."""
    file = path / "graph_mapping.yaml"
    if not file.is_file():
        raise PackError("pack is missing files: graph_mapping.yaml")
    try:
        mapping = GraphMapping(**_yaml(file))
    except ValueError as exc:
        raise PackError(f"graph_mapping.yaml: {exc}") from exc

    root = mapping.root
    _check_node(graph, root.label, [*root.properties, *root.constants])
    rel_types = {r.type: r for r in graph.relationships}
    for link in mapping.links:
        _check_node(graph, link.label, [*link.properties, *link.on_create])
        rel = rel_types.get(link.relationship)
        if rel is None:
            raise PackError(f"mapping uses undeclared relationship '{link.relationship}'")
        source, target = (
            (root.label, link.label) if link.direction == "out" else (link.label, root.label)
        )
        if (rel.source, rel.target) != (source, target):
            raise PackError(
                f"relationship {rel.type} is declared {rel.source}->{rel.target}, "
                f"mapping uses {source}->{target}"
            )
        unknown = [p for p in link.rel_properties if p not in rel.properties]
        if unknown:
            raise PackError(f"relationship {rel.type} has undeclared properties {unknown}")
    return mapping


def _check_node(graph: GraphSchema, label: str, props: list[str]) -> None:
    node = graph.nodes.get(label)
    if node is None:
        raise PackError(f"mapping uses undeclared label '{label}'")
    unknown = [p for p in props if p not in node.properties and p != node.key]
    if unknown:
        raise PackError(f"label {label} has undeclared properties {unknown}")


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
