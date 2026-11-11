# Agent Instructions

These instructions govern how the AI agent works on the `cles-graph-vector-rag` project.

## Inputs

| File | Purpose |
|------|---------|
| `INSTRUCTIONS_suggested.md` | Draft instructions to be verified |
| `cles-graph-vector-rag.jpg` | Architecture image to be analysed |
| `data` | real data input for the finished product |

## Phase 1: Verify, Analyse, and Agree on INSTRUCTIONS.md

1. Read `INSTRUCTIONS_suggested.md` and verify it for completeness, clarity, consistency, contradictions, and feasibility.
2. Analyse `cles-graph-vector-rag.jpg` (components, data flow, technologies, relationships). Cross-check it against the suggested instructions and note mismatches or gaps.
3. Understand the `data` folder content and Cross-check it against the suggested instructions. 
3. Present your opinion to the user: findings, risks, gaps, and recommended changes.
4. Discuss with the user. Iterate until both sides agree. Ask questions where something is ambiguous.
5. Do NOT write the final `INSTRUCTIONS.md` before explicit user approval of its content. After approval, produce `INSTRUCTIONS.md`.
6. When everything is settled, offer to start the implementation based on `INSTRUCTIONS.md`. Do not start until the user confirms.

## Phase 2: Implementation

- Follow `INSTRUCTIONS.md` and the docs in `docs/` if there is any. 
- Work in small, verifiable steps and keep docs in sync with the code.

## Memory and History

- Store agent memory in a local folder inside this codebase: `.agent/memory/`.
- Keep a step-by-step history file at `.agent/history.md`. Append an entry for every action, containing:
  - Timestamp
  - What was done
  - Files affected
  - Decisions made and their reasons
  - Next steps
- Read memory at the start of every session and update it after each step.

## Documentation (`docs/`)

Generate a `docs/` folder with a separate file for each documentation type, split further into multiple files where useful:

| File | Content |
|------|---------|
| `docs/01-problem.md` | The problem we are solving |
| `docs/02-requirements.md` | Functional and non-functional requirements |
| `docs/03-architecture.md` | Architecture, components, data flow |
| `docs/04-implementation-plan.md` | Phases, tasks, milestones |
| `docs/05-testing-plan.md` | Test strategy, cases, acceptance criteria |

## Diagrams

- Use diagrams whenever they help explain an idea.
- Use Mermaid blocks or draw.io compatible blocks.
- The user prefers rich diagrams (flowcharts, sequence, component, ER, state diagrams).
- Do NOT use ASCII art or plain-line diagrams.

## Git Rules

- NEVER commit on your own initiative.
- Workflow:
  1. Stage the relevant files (`git add`).
  2. Generate a commit message and show it to the user.
  3. Wait for the user's decision:
     - If the user approves the message, commit with exactly that message or the updated message from the user.
     - Otherwise, the user commits themselves.
- Commit messages must follow Conventional Commits: `<type>(<optional scope>): <description>`, with optional body and footer.
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
  - Use `!` or a `BREAKING CHANGE:` footer for breaking changes.
- Ask the user if they want to create a Tag after each commit. if they said yes, suggest to them the tag details and only apply the tag when approved by the user.  
- Never push unless explicitly asked.
