# 0018. Conversation support: earlier turns folded into the case text [rt.4]

**Status:** accepted (user approved option A on 2026-11-14)

**Context.** The lawyer-facing interface should be conversational: each new question is sent together with all earlier questions and answers. The advisor model was fine-tuned on single-turn prompts (case description, one question, retrieved passages, one advice JSON), never on multi-turn chats.

**Options considered.**
- A. Fold earlier turns into the case description: a compact transcript (question and the key points of the advice: stage, position, routes with likelihood, next steps) appended to the case text. The prompt keeps the trained shape.
- B. Real chat turns, with earlier advice as assistant messages. More natural, but outside the training distribution: quality unknown, and full earlier answers (about 1,000 tokens each) would use the prompt budget quickly.

**Decision.** A. `cles.inference.conversation.fold_history` builds the text; `POST /advise` takes an optional `history` (list of question and advice, oldest first). The API stays stateless: the client holds the conversation and sends it back (nothing is stored server-side, and the audit table keeps no question text by default). Details:
1. Budget: `CONVERSATION_HISTORY_TOKENS` (default 1500, estimated tokens). The oldest turns are dropped first; the case text is never cut. The response reports `extra.history` (turns sent, turns dropped) and the page shows it.
2. Retrieval query: `search_text` uses the question and the first 2000 characters of the case text, and the transcript is appended after the case, so earlier turns do not steer retrieval.
3. Page: one static HTML file served at `/` (no build step, no new dependency). It builds the DOM from text nodes only, because model output is untrusted. Conversation state lives in the page; nothing is written to browser storage (case text is confidential).
4. Live model: the page and the API run on the laptop (they need the database and the graph); the fine-tuned model runs on a GPU machine behind an SSH tunnel, so the endpoint is `localhost` for the confidentiality guard and no port is exposed publicly.

**Consequences.** Long conversations lose their oldest turns; a turn's earlier advice is reduced to its key points, so details are not remembered. The fine-tune has not seen the transcript section, so the quality of follow-up answers must be judged in the live test rather than assumed. Typed cases stay on machines we control; a comparison against a third-party model would be opt-in and for public or synthetic cases only.
