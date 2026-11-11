# 01. Problem

Lawyers need to judge where a case is heading and what to do next. Relevant experience is spread
across thousands of court decisions, and the connections that matter (statute, issue, judge,
treatment of earlier cases, outcome) are several hops apart. Keyword search misses them, and a
general LLM answers fluently but can cite law that does not exist.

CLES is a decision-support copilot. Given a case description at any stage and a question, it returns:

- the position of the case
- possible routes, each with expected outcome and likelihood
- risks and recommended next steps
- supporting authorities, each verified against the corpus

Scope: the first corpus is about 10,000 Court of Appeal for Ontario decisions (`ONCA`). The output
supports a qualified lawyer; it is not legal advice.

## Approach in one paragraph

Two retrieval stores (pgvector for passages, Neo4j for structure) supply facts. A small fine-tuned
model supplies reasoning and format. A deterministic verifier checks every citation before the answer
is shown. The legal domain lives in a swappable domain pack.
