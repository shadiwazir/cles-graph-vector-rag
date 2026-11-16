# Project state (CLES graph+vector RAG)
- Phase 1 in progress: reviewing INSTRUCTIONS_suggested.md, image, data. INSTRUCTIONS.md NOT yet written (needs explicit user approval).
- Data: 15 Ontario Court of Appeal (ONCA) decisions, text-based PDFs (4-41 pages), ~280K chars; 9 criminal, 4 civil, 1 judicial review/other mix; 14 from 2026, 1 from 2018.
- Env: WSL2, Docker 29.7, GPU GTX 1050 3GB (cannot QLoRA 8B locally). No pdftotext; pypdf venv lives in scratchpad.
- Git: not a repo; never commit without user approval (see Agent.md).
- User decisions (2026-10-22): see history.md round 2. Final deliverables AGENTS.md (from Agent.md rules) + INSTRUCTIONS.md + docs/. Never go back to INSTRUCTIONS_suggested.md after INSTRUCTIONS.md exists. User wants simple, readable, best-practice code to learn from; project is software to be re-run on real data (10k+ cases) later.
- 2026-10-22: AGENTS.md + INSTRUCTIONS.md drafted on disk, awaiting user approval. Product = lawyer-facing advisory copilot (any-stage case input -> routes/risks/next steps with verified citations). Stack decisions: Unsloth+TRL, domain packs, OpenAI default via provider interface, pgvector+Neo4j, vLLM serving.
- HINT (keep OUT of INSTRUCTIONS.md/AGENTS.md per user): a second aspect of this project is that the user/team will use the code for learning/teaching. Write readable code, explain the why, write ADRs.
- Doc style (user, 2026-10-22): docs/* and code comments concise, dev-to-dev; AI-side detail in .agent/memory/refs/ linked by [area.n] tags (see refs/INDEX.md). NOT for INSTRUCTIONS.md/AGENTS.md (leave as is). ADRs keep full detail.

- 2026-11-12: Scope = goal 1 (PoC on ~100 PDFs in data/criminal_and_civil, 93 files); goal 2 (production, 10k+) later. See refs pr.1, pl.2, docs/07, scripts/pipeline.sh.
- 2026-11-15: Serving of the fine-tuned adapter verified on a RunPod L40S (vLLM 0.33.0, SSH tunnel, console). Volume now 75 GB (was 60 GB, filled by the uv cache; `uv cache clean`). Pod stopped by the user. Next GPU session: run the 48 eval examples against the served 16-bit model (4-bit vs 16-bit check); user tells me when the pod is up. Acceptance verdict still "rejected (provisional)" on high_is_reliable.
