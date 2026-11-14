"use strict";
// CLES console. Everything user-visible is built from text nodes (model output is untrusted).
// The conversation lives only in this page: nothing is stored in the browser or on the server.

const $ = (id) => document.getElementById(id);
const history = [];
let INFO = null;

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") node.className = v;
    else if (k === "onclick") node.addEventListener("click", v);
    else node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}
const tag = (text, kind) => el("span", { class: "tag " + (kind || "") }, text);
const list = (items) => el("ul", {}, ...items.map((t) => el("li", {}, t)));
const pct = (x) => Math.round(x * 100) + "%";

/* ---------- tabs (hash routing, iframes load on first visit) ---------- */
const TABS = ["ask", "explorer", "platform", "about"];
function showTab() {
  const name = TABS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "ask";
  for (const t of TABS) $("tab-" + t).classList.toggle("active", t === name);
  for (const a of document.querySelectorAll("#tabs a")) a.classList.toggle("active", a.dataset.tab === name);
  if (name === "explorer") {
    const frame = document.querySelector("#tab-explorer iframe");
    if (!frame.src) frame.src = frame.dataset.src;
  }
  if (name === "platform") loadStatus();
}
window.addEventListener("hashchange", showTab);

/* ---------- system information ---------- */
async function loadInfo() {
  try {
    INFO = await (await fetch("/api/info")).json();
  } catch (err) {
    $("modelName").textContent = "unavailable";
    return;
  }
  const m = INFO.model, c = INFO.corpus, q = INFO.quality;
  $("modelName").textContent = m.name;
  $("modelInfo").replaceChildren(
    el("div", { class: "stat" }, "Model", el("b", {}, m.name)),
    el("p", { class: "small" }, m.external
      ? "An external service writes the answers. Use public or synthetic cases only."
      : "Runs on infrastructure we control. Case text stays with us."));
  $("corpusInfo").replaceChildren(
    ...(c.decisions
      ? [el("div", { class: "stat" }, "Decisions", el("b", {}, c.decisions)),
         el("div", { class: "stat" }, "Passages", el("b", {}, c.passages)),
         el("div", { class: "stat" }, "Dated", el("b", {}, `${c.from} to ${c.to}`)),
         el("p", { class: "small" }, INFO.pack.scope)]
      : ["Not available"]));
  const quality = q
    ? [el("div", { class: "stat" }, "Answers in the required format", el("b", {}, pct(q.schema_valid))),
       el("div", { class: "stat" }, "Case stage identified", el("b", {}, pct(q.stage_correct))),
       el("div", { class: "stat" }, "Citations failing verification", el("b", {}, pct(q.citation_failure_rate))),
       el("p", { class: "small" }, `Latest offline evaluation on ${q.examples} held-out examples. See the results explorer.`)]
    : ["No evaluation has been run yet."];
  $("qualityInfo").replaceChildren(...quality);
  $("aboutQuality").replaceChildren(...quality);
  $("disclaimer").textContent = INFO.pack.disclaimer;
  $("privacy").textContent = m.external
    ? "This build sends case text to an external model service. Use public or synthetic cases only. Retrieval, verification and the audit trail run on this machine, and the audit trail stores no case text."
    : "Case text is processed on infrastructure we control. The audit trail stores metadata only, never the case text.";
}

/* ---------- examples ---------- */
const EXAMPLES = [
  {
    label: "Sentence appeal",
    ctx: "The accused pleaded guilty to child luring and sexual interference involving a 14-year-old. The sentencing judge imposed a sentence below what the Crown requested, and the Crown is considering an appeal of the sentence.",
    q: "What are the Crown's prospects on a sentence appeal, and what are the main risks?",
  },
  {
    label: "Conviction appeal",
    ctx: "The accused was convicted of sexual assault after trial. The conviction rested partly on an edited transcript of a recorded conversation that the defence objected to at trial. An appeal is being prepared.",
    q: "What routes are open to the appellant and how likely is each?",
  },
  {
    label: "Extradition",
    ctx: "Two people sought by the United States on fraud charges were committed for extradition. The Minister ordered surrender. They argue the voice identification evidence in the record of the case was unreliable.",
    q: "How strong is a challenge to the committal, and what should we prepare first?",
  },
];
function loadExamples() {
  $("examples").replaceChildren(...EXAMPLES.map((e) => {
    const b = el("button", { class: "chip-btn" }, e.label);
    b.addEventListener("click", () => { $("ctx").value = e.ctx; $("q").value = e.q; $("q").focus(); });
    return b;
  }));
}

/* ---------- rendering an answer ---------- */
function meter(level) {
  return el("span", { class: "meter " + level, title: "likelihood: " + level }, el("i"), el("i"), el("i"), " " + level);
}
function route(r, i) {
  const head = el("div", { class: "route-head" }, el("b", {}, `${i + 1}. ${r.name || "Route"}`), meter(r.likelihood || "low"));
  if (r.expected_outcome) head.append(tag(r.expected_outcome.replaceAll("_", " ")));
  for (const rem of r.expected_remedies || []) head.append(tag(rem.replaceAll("_", " ")));
  const node = el("div", { class: "route" }, head);
  if (r.description) node.append(el("p", {}, r.description));
  if (r.next_event) node.append(el("p", {}, el("b", {}, "What happens next: "), r.next_event));
  if (r.reasoning) node.append(el("details", {}, el("summary", {}, "Why"), el("p", {}, r.reasoning)));
  for (const a of r.authorities || []) {
    node.append(el("div", {}, el("b", {}, `${a.case_id}, para ${a.para} `), a.verified ? tag("verified", "ok") : tag("not verified", "bad"),
      (a.overruled_by || []).length ? tag("overruled by " + a.overruled_by.join(", "), "bad") : ""),
      el("div", { class: "quote" }, a.quote));
  }
  return node;
}
function feedbackBar(requestId) {
  const status = el("span", { class: "muted" }, "");
  const bar = el("div", { class: "feedback" }, el("span", { class: "muted" }, "Was this useful?"));
  for (const [verdict, label] of [["accept", "Yes"], ["edit", "Needs changes"], ["reject", "No"]]) {
    const b = el("button", {}, label);
    b.addEventListener("click", async () => {
      try {
        const res = await fetch("/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_id: requestId, feedback: verdict }) });
        status.textContent = res.ok ? "Thank you" : "Could not save";
      } catch (e) { status.textContent = "Could not save"; }
    });
    bar.append(b);
  }
  bar.append(status);
  return bar;
}
function answer(data) {
  const card = el("div", { class: "a" });
  const a = data.advice;
  const strength = data.evidence_strength;
  const tags = el("div", { class: "tags" }, tag("evidence: " + strength, { strong: "ok", moderate: "warn", weak: "bad" }[strength]));
  if (a && a.stage) tags.append(tag("stage: " + a.stage.replaceAll("_", " ")));
  tags.append(tag(`citations verified: ${data.citations_total - data.citations_failed}/${data.citations_total}`, data.citations_failed ? "warn" : "ok"));
  card.append(tags);
  if (data.error) card.append(el("p", { class: "err" }, "The model did not produce usable advice: " + data.error));
  if (a) {
    if (a.case_position) card.append(el("h4", {}, "Where the case stands"), el("p", {}, a.case_position));
    card.append(el("h4", {}, "Routes"), ...(a.routes || []).map(route));
    if ((a.risks || []).length) card.append(el("h4", {}, "Risks"), list(a.risks));
    if ((a.recommended_next_steps || []).length) card.append(el("h4", {}, "Recommended next steps"), list(a.recommended_next_steps));
    if ((a.missing_information || []).length) card.append(el("h4", {}, "What would sharpen this advice"), list(a.missing_information));
  }
  if ((data.warnings || []).length) card.append(el("h4", {}, "Notes"), list(data.warnings));
  if ((data.sources || []).length) {
    card.append(el("details", {}, el("summary", {}, `Sources retrieved (${data.sources.length})`),
      list(data.sources.map((s) => `${s.label}: ${s.title}`))));
  }
  const h = (data.extra || {}).history || {};
  card.append(el("div", { class: "meta" }, `${(data.latency_ms / 1000).toFixed(1)} s. Earlier turns used: ${h.turns_sent || 0}, trimmed: ${h.turns_dropped || 0}. ${data.scope} ${data.disclaimer}`));
  card.append(feedbackBar(data.request_id));
  return card;
}

/* ---------- asking ---------- */
const STEPS = ["Reading the case", "Searching decisions", "Reasoning about routes", "Verifying citations"];
async function send() {
  const question = $("q").value.trim(), caseText = $("ctx").value.trim();
  if (caseText.length < 20 || question.length < 5) {
    $("status").textContent = "Describe the case (20+ characters) and ask a question (5+).";
    return;
  }
  $("send").disabled = true; $("status").textContent = "";
  $("empty").hidden = true;
  $("log").append(el("div", { class: "q" }, question));
  const wait = el("div", { class: "thinking" }, el("i"), el("i"), el("i"), el("span", {}, STEPS[0]));
  $("log").append(wait);
  let step = 0;
  const timer = setInterval(() => { step = Math.min(step + 1, STEPS.length - 1); wait.lastChild.textContent = STEPS[step]; }, 4000);
  wait.scrollIntoView({ block: "nearest" });
  try {
    const res = await fetch("/advise", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_text: caseText, question, history }) });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    const data = await res.json();
    wait.replaceWith(answer(data));
    history.push({ question, advice: data.advice });
    $("q").value = "";
  } catch (err) {
    wait.replaceWith(el("div", { class: "a err" }, "Something went wrong: " + err.message));
  } finally {
    clearInterval(timer);
    $("send").disabled = false;
    $("log").lastElementChild.scrollIntoView({ block: "nearest" });
  }
}
$("send").addEventListener("click", send);
$("q").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send(); });
$("reset").addEventListener("click", () => { history.length = 0; $("log").replaceChildren($("empty")); $("empty").hidden = false; $("status").textContent = ""; });

/* ---------- platform ---------- */
async function loadStatus() {
  let data;
  try { data = await (await fetch("/api/status")).json(); } catch (e) { $("health").textContent = "status unavailable"; return; }
  const down = data.tools.filter((t) => !t.ok);
  $("health").replaceChildren(el("i", { class: "dot " + (down.length ? "bad" : "ok") }), " ",
    down.length ? `${down.length} service(s) not responding` : "All services responding");
  const tools = data.tools.filter((t) => t.url);
  $("toolGrid").replaceChildren(...tools.map((t) => {
    const open = el("button", {}, "Open here");
    open.addEventListener("click", () => view(t));
    return el("div", { class: "card tool" },
      el("div", { class: "head" }, el("i", { class: "dot " + (t.ok ? "ok" : "bad") }), t.name),
      el("p", {}, t.purpose),
      el("div", { class: "detail" }, t.ok ? "Responding" : "Not responding: " + t.detail),
      el("div", { class: "actions" }, open, el("a", { href: t.url, target: "_blank", rel: "noopener" }, "New tab")));
  }));
  $("coreList").replaceChildren(...data.tools.filter((t) => !t.url).map((t) =>
    el("div", {}, el("i", { class: "dot " + (t.ok ? "ok" : "bad") }), el("span", {}, t.name), el("span", { class: "muted" }, " " + t.detail))));
}
function view(t) {
  $("viewerTitle").textContent = t.name;
  $("viewerOpen").href = t.url;
  $("viewerFrame").src = t.embed;
  $("viewer").hidden = false;
  $("viewer").scrollIntoView({ behavior: "smooth", block: "start" });
}
$("viewerClose").addEventListener("click", () => { $("viewer").hidden = true; $("viewerFrame").src = "about:blank"; });
setInterval(() => { if (location.hash === "#platform") loadStatus(); }, 30000);

loadExamples();
loadInfo();
showTab();
