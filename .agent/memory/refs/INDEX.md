# Reference index

Docs (`docs/*`) and code point here with tags like `[ar.3]`. Each tag has one note file in this folder: `<area>.<n>.md`
(for example `ar.3.md`), holding the detailed reasoning, options and conversation context. Not used in
INSTRUCTIONS.md or AGENTS.md. ADRs keep their own detail and may carry a tag.

## Areas

| Code | Area |
|------|------|
| pr | Product and scope |
| ar | Architecture and components |
| da | Data, schema, ingestion |
| gr | Graph and domain packs |
| rt | Retrieval and inference |
| ml | Training and evaluation |
| ob | Observability and versioning |
| pl | Plan, process, tooling |

## Entries

| Tag | Topic | Used in |
|-----|-------|---------|
| [ar.1] | Dual retrieval stores | ADR 0001 |
| [ar.2] | Flyway migrations | ADR 0004 |
| [da.2] | Docling trial vs PyMuPDF | (side question, no doc) |
| [gr.1] | Domain packs | ADR 0002 |
| [gr.2] | Extraction and graph mapping | ADR 0011, docs/03 |
| [gr.3] | Local LLM (Ollama) trial | docs/03 |
| [gr.4] | OpenAI extraction run (gpt-5.4-mini) | docs/04 |
| [gr.5] | Disposition and remedy split | ADR 0012, docs/03 |
| [rt.3] | Phase 3 build notes | ADR 0013, docs/03 |
| [ml.3] | Training data build | ADR 0014, docs/03 |
| [ml.4] | Stage-aware advice (option B) | ADR 0015, docs/03 |
| [ml.5] | Phase 5 fine-tuning build notes | ADR 0016, docs/06 |
| [ml.1] | Fine-tuning stack | ADR 0003 |
| [ml.2] | Stage cuts and leakage | ADR 0008 |
| [ml.6] | GPU rental for the PoC (RunPod) | docs/06 |
| [pl.1] | Orchestration and flowlit | ADR 0005 |
| [pl.2] | Run playbook and pipeline script | docs/07 |
| [pr.1] | Two goals; PoC on about 100 decisions | docs/06, docs/04 |
| [da.1] | Parser and chunker design | docs/03 |
| [ob.1] | DVC data versioning | ADR 0006 |
| [ob.2] | Observability and judges | ADR 0007 |
| [rt.1] | Citation verification | ADR 0009 |
| [rt.2] | Provider interface and guard | ADR 0010 |

## Rules
- Create the note first, then add the tag to the doc or code, then add a row above.
- Tag numbers are never reused. Update a note in place when a decision changes and say so in it.
