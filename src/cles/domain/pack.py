"""Domain pack loader and validator.

A pack is a folder of config files (see INSTRUCTIONS.md section 5). Generic code reads
labels, relationships and prompts from the pack and never hard-codes a domain.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, model_validator

REQUIRED_FILES = (
    "pack.yaml",
    "graph_schema.yaml",
    "extraction_prompt.md",
    "extraction_schema.json",
    "sections.yaml",
    "outcomes.yaml",
    "advice_schema.json",
    "advice_prompt.md",
    "query_templates.yaml",
)

# Cypher fragments such as (c:Case) and [r:CITES]
_LABEL_RE = re.compile(r"\(\s*\w*\s*:\s*(\w+)")
_REL_RE = re.compile(r"\[\s*\w*\s*:\s*(\w+)")


class PackError(ValueError):
    """The domain pack is missing files or is inconsistent."""


class PackInfo(BaseModel):
    name: str
    version: str
    language: str = "en"
    description: str = ""


class NodeType(BaseModel):
    key: str
    properties: list[str] = Field(default_factory=list)


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


@dataclass(frozen=True)
class DomainPack:
    path: Path
    info: PackInfo
    graph: GraphSchema
    outcomes: list[str]
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

    outcomes = _yaml(path / "outcomes.yaml").get("outcomes", [])
    if not outcomes or len(set(outcomes)) != len(outcomes):
        raise PackError("outcomes.yaml must list unique, non-empty outcomes")

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
        outcomes=outcomes,
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


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
