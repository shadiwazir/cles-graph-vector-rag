# AGENTS.md

Rules for any AI agent working in this repository. The product definition, architecture and plan are in
[INSTRUCTIONS.md](INSTRUCTIONS.md). Read both at the start of every session.

## 1. Session start

1. Read `.agent/memory/` and the tail of `.agent/history.md`.
2. Read `INSTRUCTIONS.md` and the relevant file(s) in `docs/`.
3. `INSTRUCTIONS_suggested.md` and `Agent.md` are historical inputs. Do not use them as a source of truth.

## 2. Way of working

- Work in small, verifiable steps. Run the tests or the code after each step and report the real result, including failures.
- Keep `docs/` in sync with the code in the same step that changes the code.
- Prefer simple, explicit, readable code over clever code (see `INSTRUCTIONS.md`, section 12).
- If something is ambiguous or a decision is the user's to make, ask. Do not guess on scope, cost, or anything hard to reverse.
- Do not start a new phase of `INSTRUCTIONS.md` until the user confirms.
- Never write real secrets into any file. Secrets live only in `.env`, which is git-ignored.

## 3. Memory and history

- Memory lives in `.agent/memory/` (one small file per topic: decisions, user preferences, environment facts). Update it after each step.
- `.agent/history.md` is an append-only log. For every action add an entry with:
  - Timestamp
  - What was done
  - Files affected
  - Decisions made and why
  - Next steps

## 4. Documentation (`docs/`)

| File | Content |
|------|---------|
| `docs/01-problem.md` | The problem we are solving |
| `docs/02-requirements.md` | Functional and non-functional requirements |
| `docs/03-architecture.md` | Architecture, components, data flow |
| `docs/04-implementation-plan.md` | Phases, tasks, milestones |
| `docs/05-testing-plan.md` | Test strategy, cases, acceptance criteria |

Record each significant architectural decision as a short ADR in `docs/adr/NNNN-title.md` (context, options considered, decision, consequences). The project owner is an architect and needs the reasoning, not only the code.

Split a file into several where that helps. Add more files (for example `docs/06-domain-packs.md`, `docs/07-runbook.md`) when needed.

## 5. Diagrams

- Use Mermaid (or draw.io compatible) blocks. Prefer rich diagrams: flowchart, sequence, component, ER, state.
- Never use ASCII art or plain-line diagrams.

## 6. Git rules

- NEVER commit on your own initiative. Never push unless explicitly asked.
- Workflow:
  1. Stage the relevant files (`git add`).
  2. Generate a commit message and show it to the user.
  3. Wait for the decision. If the user approves, commit with exactly that message (or the user's edited version). Otherwise the user commits.
- Commit messages follow Conventional Commits: `<type>(<optional scope>): <description>`, with optional body and footer.
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
  - Use `!` or a `BREAKING CHANGE:` footer for breaking changes.
- After each commit, ask whether the user wants a tag. If yes, propose the tag details and apply the tag only after approval.
- The directory is not yet a git repository. Ask before running `git init`.

## 6a. Hard rules for this project

- The training and retrieval data must never leak a case's outcome into that case's own input (see `INSTRUCTIONS.md`, section 9).
- No legal claim in a generated answer may be shown to the user without a verified citation (see `INSTRUCTIONS.md`, section 10).
- The domain is swappable: no legal-specific names in generic code. Legal specifics belong only in a domain pack.
- Every call to a paid external API must go through the cache and support a dry-run mode.
- Instrument with OpenTelemetry only, never a vendor SDK, and never export case text unless `TELEMETRY_CAPTURE_CONTENT=full` is set on a development machine.
- Never send lawyer-supplied case text to a third-party service. External generators run only on public or synthetic cases.
- Explain the reasoning behind design choices to the user, who is an architect and platform engineer, and write an ADR for each significant one.
