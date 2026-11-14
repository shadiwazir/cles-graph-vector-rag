# 0020. One web console as the landing page of the system [pr.2]

**Status:** accepted (user request, 2026-11-14)

**Context.** The system had three separate faces: the conversation page (port 8000), the results explorer (port 8001) and the tools (MLflow, Grafana, Phoenix, Prometheus on their own ports). The user wants one landing page, shaped like a finished product for imaginary clients: ask the expert system, and from the same page reach the explorer and every sub-system.

**Decision.**
1. **One app, one port.** `cles.console.app` extends the advisor app (`/advise`, `/feedback`) with the explorer routes (`/explorer`, `/api/data`, `/api/label`), `/api/info` (model, corpus, pack, latest quality numbers), `/api/status` (health of every tool, Postgres and the model endpoint) and the static console. Start with `scripts/pipeline.sh console`.
2. **Home = the product.** Hero, example scenarios, a case-context box, a conversation (earlier turns sent with each question, ADR 0018), answers as cards (routes with a likelihood meter, verified authorities, risks, next steps, missing information), an aside with the model, the knowledge base and the latest quality checks. The disclaimer and the limits stay visible.
3. **Navigation.** Tabs Ask, Results explorer, Platform, About, with hash routing. Explorer and tools open inside the console (iframes) or in a new tab. For that, MLflow runs with `--x-frame-options NONE` and Grafana with embedding and read-only anonymous viewing; all tool ports are bound to 127.0.0.1.
4. **Honesty built in.** The model badge shows which model answers; when it is an external service the page says so and asks for public or synthetic cases only (the confidentiality guard still decides). The quality card shows the real measured numbers of the latest evaluation and states their sample size. The About tab says that outcome prediction was not clearly better than a general model with retrieval.

**Options considered.** A separate front-end project (React): more tooling than a PoC needs, and a build step. A reverse proxy for all tools under one origin: needs sub-path configuration of each tool; iframes with relaxed frame headers are enough on a local machine. Streamlit or a notebook: not a landing page.

**Consequences.** The home page answers with whichever model `LLM_BASE_URL` points to. The fine-tuned model needs a GPU machine, a vLLM server and an SSH tunnel (docs/06); until then the console runs on the OpenAI baseline and says so. Grafana viewing without login is acceptable only because the ports are local. The page was exercised with a DOM stub on real responses, not in a real browser.
