"use strict";
/* Kavach workspace: inbox · agent thread · payment intelligence. Everything rendered here comes from
   the engine's step stream (real tool calls, policy decisions, actions, verifications). Nothing is scripted client-side. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const rs = (n) => (n == null || n === "" ? "—" : "₹" + Number(n).toLocaleString("en-IN"));
const tm = (iso, sec = false) => { if (!iso) return ""; const d = new Date(iso); return d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", ...(sec ? { second: "2-digit" } : {}), hour12: true }); };
const dayTm = (iso) => { const d = new Date(iso); return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", hour12: true }); };
const post = (url, body) => fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}) }).then((r) => r.json());
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

const S = { incidents: {}, steps: {}, sel: null, follow: true, filter: "all", as: "customer", draft: null, sound: true, world: null,
  running: {}, actionRows: {}, followups: [], nextDoc: null, lastShot: null, intg: null, view: "stage" };

const STATUS = { investigating: "Investigating", watching: "Watching", waiting_approval: "Needs your OK", waiting_merchant: "Waiting for Meena",
  waiting_customer: "Waiting for customer", with_human: "With a human", resolved: "Resolved", refused: "Refused" };
const KIND = { payment_claim: "Payment claim", duplicate: "Charged twice", settlement: "Missing payout", freeze: "Account hold · high risk",
  scam: "Scam call", account_change: "Payout account", question: "SOP question", chargeback: "Chargeback", live_check: "Live Paytm order", unknown: "Message" };
const APPROVER = { merchant: "Meena", paytm_ops: "Paytm Risk" };
const ACTION_NAMES = { create_support_case: "Opened a support case", reconcile_payment: "Repaired the shop's ledger", replay_soundbox: "Replayed it on the Soundbox",
  initiate_refund: "Refunded the duplicate", schedule_followup: "Scheduled a follow-up", request_settlement_hold: "Held payouts with Paytm",
  change_settlement_account: "Change payout account", generate_evidence_pack: "Built a signed evidence pack", escalate_to_human: "Handed to a human",
  resolve_incident: "Closed the case", draft_escalation: "Escalation letter (Meena signed)", draft_lien_request: "Lien-limiting request (Meena signed)", prepare_pa_upload: "Paytm's SOP 9.5(ii) upload, drafted", issue_live_pack: "Signed pack from Paytm's live response", validate_settlement_account: "₹1 validation credit", release_settlement_hold: "Released held payouts to her account", submit_dispute_response: "Chargeback reply filed (Meena approved)", accept_chargeback: "Chargeback accepted (Meena's word)", record_case_event: "Started the bank's 7-day clock",
  issue_verified_receipt: "Verified receipt", request_payment: "QR for the exact amount due", send_customer_update_simulated: "Customer update", notify_merchant: "Told Meena" };
const DENY_NAMES = { request_payment: "asking the customer to pay again", issue_verified_receipt: "issuing a receipt", reconcile_payment: "recording this payment in the ledger",
  initiate_refund: "refunding", change_settlement_account: "sending payouts to another account", generate_evidence_pack: "building an evidence pack",
  file_grievance: "filing on Meena's behalf", send_customer_update_simulated: "that customer message", resolve_incident: "closing the case",
  request_settlement_hold: "holding payouts", submit_dispute_response: "that chargeback reply", notify_merchant: "telling the merchant case details", schedule_followup: "another follow-up", replay_soundbox: "replaying the Soundbox" };
const VERB = { release_settlement_hold: "release the held payouts", submit_dispute_response: "reply to the chargeback in Meena's name", draft_escalation: "send a letter in Meena's name", draft_lien_request: "send a request in Meena's name", request_settlement_hold: "hold payouts with Paytm", initiate_refund: "refund the duplicate", change_settlement_account: "change the payout account" };
const MSG_ACTIONS = new Set(["notify_merchant", "send_customer_update_simulated", "issue_verified_receipt", "request_payment"]);
const ICON = {
  switch: "M4 8h15l-3-3M20 16H5l3 3", ledger: "M5 3h11l3 3v15H5zM8 9h8M8 13h8M8 17h5", refund: "M4 12a8 8 0 1 0 3-6M4 4v4h4",
  payout: "M12 3v11M7 9l5 5 5-5M4 17v3h16v-3", eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  doc: "M6 3h9l3 3v15H6zM9 10h6M9 14h6", speaker: "M5 9h4l5-4v14l-5-4H5z", policy: "M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z",
  case: "M4 7h16v12H4zM9 7V4h6v3", sop: "M12 4v16M5 8h14M5 8l-3 6h6zM19 8l-3 6h6z", spin: "M12 3a9 9 0 1 1-9 9",
};
const TOOL_ICON = { read_screenshot: "eye", parse_notice: "doc", read_document: "doc", lookup_transaction: "switch", get_payment_status: "switch",
  find_duplicate_payments: "switch", check_sale_pattern: "switch", get_merchant_ledger: "ledger", get_refund_status: "refund", get_settlement_status: "payout",
  get_bank_signal: "payout", get_soundbox_log: "speaker", get_incident_policy: "policy", route_sop: "sop", get_sop_clocks: "sop", ask_sop: "sop" };
const TOOL_COL = { read_screenshot: "claim", parse_notice: "claim", get_payment_status: "switch", lookup_transaction: "switch", get_merchant_ledger: "ledger",
  get_refund_status: "refund", get_settlement_status: "settlement", find_duplicate_payments: "pay1" };
const svgI = (k) => `<svg viewBox="0 0 24 24"><path d="${ICON[k] || ICON.switch}"/></svg>`;

// ===================================================================== boot + stream
async function boot() {
  const st = await fetch("/api/state").then((r) => r.json());
  S.world = st.world; S.followups = st.followups || [];
  for (const inc of st.incidents) S.incidents[inc.id] = inc;
  for (const s of st.steps) (S.steps[s.incident] ||= []).push(s);
  setClock(st.world.now);
  fetch("/api/integrations").then((r) => r.json()).then(renderIntegrations);
  const last = st.incidents[st.incidents.length - 1];
  renderInbox();
  if (last) select(last.id); else showEmpty();
  if (window.stageBoot) stageBoot();
  const es = new EventSource("/api/stream");
  es.onmessage = (m) => handle(JSON.parse(m.data));
  setInterval(refreshWorld, 2000);
  setInterval(() => { if (S.sel) renderHead(); }, 1300);
}

function handle(ev) {
  if (window.stageOn) { try { stageOn(ev); } catch (e) { console.error(e); } }
  switch (ev.type) {
    case "tool_start": {
      S.running[ev.incident] = ev; (S.busy ||= {})[ev.incident] = Date.now();
      if (ev.incident === S.sel) { appendRunning(ev); markLoading(ev.tool); setStage(stageOfTool(ev.tool)); }
      break;
    }
    case "step": {
      const s = ev.step;
      (S.steps[s.incident] ||= []).push(s); (S.busy ||= {})[s.incident] = Date.now();
      if (S.follow && S.sel !== s.incident && s.kind === "intake") { select(s.incident); live(s); break; }
      if (s.incident === S.sel) { appendStep(s); live(s); }
      break;
    }
    case "incident": {
      const isNew = !S.incidents[ev.incident.id];
      S.incidents[ev.incident.id] = ev.incident;
      if (isNew && S.follow) select(ev.incident.id);
      else if (ev.incident.id === S.sel) { renderHead(); renderIntel(); }
      renderInbox(); renderSuggest();
      break;
    }
    case "world_event": if (ev.event.kind === "soundbox") soundbox(ev.event); refreshWorld(); break;
    case "clock": setClock(ev.now); break;
    case "draft": setDraft(ev.draft); break;
    case "world": S.world = ev.world; renderSimbar(); break;
    case "automation": refreshAutomation(); break;
    case "desk": onDesk(ev); break;
    case "reset": location.reload(); break;
  }
}

function live(s) {   // side effects only for steps that arrive live (not on replay)
  if (s.kind === "action" && s.action === "notify_merchant" && s.args && s.args.speak) say(s.args.speak);
  if ((s.kind === "action" && s.action === "schedule_followup") || s.kind === "followup" || (s.kind === "action" && s.action === "resolve_incident")) {
    refreshFollowups(); setTimeout(refreshFollowups, 600);
  }
}

async function refreshFollowups() { try { S.followups = await fetch("/api/followups").then((r) => r.json()); renderIntel(); } catch (_) {} }
async function refreshWorld() { try { S.world = await fetch("/api/world").then((r) => r.json()); setClock(S.world.now); renderSimbar(); if (!$("#drawer").hidden) renderSystems(); } catch (_) {} }
function setClock(iso) { $("#clock").textContent = tm(iso, true); }

function renderIntegrations(i) {
  S.intg = i;
  const chip = (name, on, title, always) => (on || always) ? `<span class="ichip ${on ? "on" : ""}" title="${esc(title)}">${name}</span>` : "";   // off integrations stay out of the way
  $("#intg").innerHTML = chip("Paytm " + (i.paytm_env === "production" ? "prod" : "staging"), i.paytm, i.paytm ? "live: Paytm Transaction Status API on your MID" : "offline: set PAYTM_MID and PAYTM_MERCHANT_KEY", true) + chip("Sarvam", i.sarvam, i.sarvam ? `live: ${i.models.chat}, ${i.models.stt}, ${i.models.tts}` : "offline: set SARVAM_API_KEY")
    + chip("n8n", i.n8n, i.n8n ? "events posted to your n8n webhook" : "offline: events kept in a local log")
    + chip("Cognee", i.cognee, i.cognee ? "SOP retrieval via Cognee" : "offline: local SOP retrieval")
    + chip("OCR", i.ocr, i.ocr ? "Tesseract reads images" : "install tesseract")
    + `<span class="ichip on" title="Planner">${i.planner === "offline" ? "rules planner" : i.planner + " planner"}</span>`;
}

// ===================================================================== inbox
function bucket(i) {
  if (i.status === "resolved" || i.status === "refused") return "closed";
  if (["waiting_approval", "waiting_merchant"].includes(i.status) || (i.pending && i.pending.approvers && i.pending.approvers.length)) return "needs";
  return "working";
}
function lastLine(i) {
  const st = S.steps[i.id] || [];
  const m = [...st].reverse().find((s) => s.kind === "intake" || (s.kind === "action" && MSG_ACTIONS.has(s.action) && s.args && s.args.text));
  return i.headline || (m ? (m.text || m.args.text) : i.title);
}
function renderInbox() {
  const all = Object.values(S.incidents).sort((a, b) => (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at));
  const counts = { all: all.length, needs: 0, working: 0, closed: 0 };
  all.forEach((i) => counts[bucket(i)]++);
  $$("#filters button").forEach((b) => { const f = b.dataset.f; b.innerHTML = `${b.textContent.replace(/\d+$/, "").trim()}${counts[f] ? ` <em>${counts[f]}</em>` : ""}`; });
  $("#inbox-count").textContent = all.length ? `${counts.working + counts.needs} open` : "";
  const list = all.filter((i) => S.filter === "all" || bucket(i) === S.filter);
  $("#inc-list").innerHTML = list.length ? list.map((i) => {
    const merchant = i.channel !== "whatsapp";
    const name = merchant ? "Meena · shop owner" : (i.customer.name || "Customer");
    const amt = (i.recon && i.recon.claim && i.recon.claim.amount) || (i.facts && (i.facts.claimed || i.facts.amount));
    return `<li><button class="inc-item ${i.id === S.sel ? "on" : ""}" data-inc="${i.id}">
      <i class="av ${merchant ? "merchant" : ""}">${esc(merchant ? "M" : name[0])}<span class="ch"></span></i>
      <div><div class="t1"><b>${esc(name)}</b><time>${tm(i.updated_at || i.created_at)}</time></div>
      <div class="t2">${esc(lastLine(i))}</div>
      <div class="t3">${amt ? `<span class="amt">${rs(amt)}</span>` : ""}<span class="pill ${i.kind === "freeze" && i.status !== "resolved" ? "high" : i.status}">${esc(i.kind === "freeze" && i.status !== "resolved" ? "High risk · " + (STATUS[i.status] || i.status) : STATUS[i.status] || i.status)}</span></div></div>
    </button></li>`;
  }).join("") : `<li class="inbox-empty">${all.length ? "Nothing here." : "No incidents yet. When a customer or Meena reports a problem, it lands here and Kavach picks it up."}</li>`;
  $$("#inc-list [data-inc]").forEach((b) => b.onclick = () => { S.follow = false; select(b.dataset.inc); });
}
$$("#filters button").forEach((b) => b.onclick = () => { S.filter = b.dataset.f; $$("#filters button").forEach((x) => x.classList.toggle("on", x === b)); renderInbox(); });

// ===================================================================== workspace
function showEmpty() { $("#empty").hidden = false; $("#ws").hidden = true; renderIntel(); }

function select(id) {
  S.sel = id; S.actionRows = {};
  $("#empty").hidden = true; $("#ws").hidden = false;
  const inc = S.incidents[id];
  if (inc) { S.as = inc.channel === "whatsapp" ? "customer" : "merchant"; syncAs(); }
  renderInbox(); renderHead();
  const th = $("#thread"); th.innerHTML = "";
  (S.steps[id] || []).forEach((s) => appendStep(s, true));
  th.scrollTop = 1e9;
  renderIntel(); renderSuggest();
  if (window.stageSelect) stageSelect(id);
}

function renderHead() {
  const i = S.incidents[S.sel]; if (!i) return;
  const merchant = i.channel !== "whatsapp";
  const av = $("#who-av"); av.className = merchant ? "merchant" : ""; av.textContent = merchant ? "M" : (i.customer.name || "C")[0];
  $("#who-name").textContent = merchant ? "Meena Sharma · shop owner" : (i.customer.name || "Customer");
  $("#who-meta").textContent = [merchant ? "Paytm for Business app" : `WhatsApp ${i.customer.wa || ""} (simulated)`, KIND[i.kind] || i.kind,
    i.facts && i.facts.case_id ? `case ${i.facts.case_id}` : null, i.id].filter(Boolean).join(" · ");
  const busy = i.status !== "resolved" && Date.now() - ((S.busy || {})[i.id] || 0) < 2600;
  const p = $("#ws-pill"); p.className = `pill ${busy ? "investigating" : i.status}`; p.textContent = busy ? "Working…" : STATUS[i.status] || i.status;
  $("#ws-owner").textContent = `Owner · Kavach${i.planner && i.planner !== "offline" ? ` (${i.planner} planner)` : ""}`;
  const steps = S.steps[i.id] || [];
  const seen = new Set(steps.map(stageOf).filter(Boolean));
  const cur = i.status === "resolved" ? null : stageOf([...steps].reverse().find((s) => stageOf(s)) || {});
  $$("#rail li").forEach((li) => { li.classList.toggle("seen", seen.has(li.dataset.stage)); li.classList.toggle("now", li.dataset.stage === cur); });
}
function setStage(st) { $$("#rail li").forEach((li) => { if (li.dataset.stage === st) li.classList.add("now", "seen"); else li.classList.remove("now"); }); }
function stageOfTool(t) {
  if (["get_incident_policy"].includes(t)) return "plan";
  if (["get_merchant_ledger", "check_sale_pattern", "route_sop", "find_duplicate_payments"].includes(t)) return "reconcile";
  return "investigate";
}
function stageOf(s) {
  switch (s.kind) {
    case "intake": return "understand";
    case "think": return "plan";
    case "tool": return stageOfTool(s.tool);
    case "evidence": return "reconcile";
    case "policy": case "approval": case "approval_result": return "policy";
    case "action": return ["schedule_followup", "escalate_to_human", "resolve_incident"].includes(s.action) ? "follow" : s.action === "create_support_case" ? "plan" : "act";
    case "verify": return "verify";
    case "followup": return "follow";
  }
  return null;
}

function appendRunning(ev) {
  const th = $("#thread");
  const row = el("div", "tool running", `<span class="ic">${svgI("spin")}</span><span class="nm">${esc(ev.tool)}</span><span class="sm">${esc(argLine(ev.args))}</span><span class="ms"></span>`);
  row.dataset.run = `${ev.incident}:${ev.n}`;
  actBlock().appendChild(row); scroll();
}
function argLine(a) { return Object.entries(a || {}).filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) => `${k}=${typeof v === "string" && v.length > 14 ? "…" + v.slice(-6) : v}`).join(" "); }
function actBlock() {
  const th = $("#thread"); const last = th.lastElementChild;
  if (last && last.classList.contains("act")) return last;
  const b = el("div", "act"); th.appendChild(b); return b;
}
function scroll() { if (S.follow || true) $("#thread").scrollTop = 1e9; }

function appendStep(s, replay = false) {
  const th = $("#thread");
  const inc = S.incidents[s.incident] || {};
  const merchantCh = inc.channel !== "whatsapp";
  const key = `${s.incident}:${s.action}`;
  const t = `<time>${tm(s.at)}</time>`;
  switch (s.kind) {
    case "intake": {
      const cust = s.sender === "customer";
      const m = el("div", `m ${cust ? "cust" : "meena"}`, `<span class="by">${cust ? `${esc(inc.customer && inc.customer.name || "Customer")} · WhatsApp` : "Meena · to Kavach"}</span>${esc(s.text)}`);
      const shot = s.shot_id || (S.pendingAttach && S.pendingAttach[s.text]);
      th.appendChild(m);
      attachMedia(m, s, inc);
      m.insertAdjacentHTML("beforeend", t);
      break;
    }
    case "tool": {
      const run = $(`[data-run="${s.incident}:${s.n}"]`);
      const row = el("div", "tool", `<span class="ic">${svgI(TOOL_ICON[s.tool])}</span><span class="nm">${esc(s.tool)}</span><span class="sm">${esc(s.summary)}</span><span class="ms">${s.ms != null ? s.ms + " ms" : ""}</span><pre hidden>${esc(JSON.stringify({ args: s.args, result: s.result }, null, 1))}</pre>`);
      row.title = "Click to see the exact arguments and result"; row.onclick = (e) => { if (e.target.tagName !== "PRE") row.querySelector("pre").hidden = !row.querySelector("pre").hidden; };
      if (run) run.replaceWith(row); else actBlock().appendChild(row);
      if (!replay) { unmarkLoading(); renderIntel(); }
      break;
    }
    case "think": actBlock().appendChild(el("div", `think ${s.tone || ""}`, esc(s.text))); break;
    case "evidence": {
      th.appendChild(el("div", `finding ${s.tone}`, `<small>${esc(s.title)}</small><p>${esc(s.verdict)}</p>${s.stamp ? `<span class="stamp">${esc(s.stamp)}</span>` : ""}`));
      break;
    }
    case "policy": {
      if (s.verdict === "DENY") {
        th.appendChild(el("div", "deny", `<b>Kavach stopped itself from ${esc(DENY_NAMES[s.action] || s.action.replace(/_/g, " "))}</b><span class="reason">${esc(s.reason)}</span><span class="rule">Policy ${esc(s.rule)} · ${esc(s.rule_text)}</span><span class="stamp">Blocked</span>`));
      } else if (s.verdict === "ALLOW" && !MSG_ACTIONS.has(s.action)) {
        const r = el("div", `arow ${s.action === "reconcile_payment" ? "repair" : ""}`, `<span class="ic">${s.action === "reconcile_payment" ? "✓" : "→"}</span><div><b>${esc(ACTION_NAMES[s.action] || s.action)}</b> <span class="sum"></span> <span class="chips"><em class="chip ok" title="${esc(s.reason)}">policy ${esc(s.rule || "✓")}</em></span></div>`);
        actBlock().appendChild(r); S.actionRows[key] = r;
      } else if (s.verdict === "ALLOW") S.actionRows[key] = { msgRule: s.rule || "✓", reason: s.reason };
      break;
    }
    case "action": {
      if (MSG_ACTIONS.has(s.action)) { const b = msgBubble(s, inc, merchantCh); th.appendChild(b); S.actionRows[key] = b; break; }
      if (s.action === "resolve_incident") { th.appendChild(el("div", "closed", `<span>✓</span><div>Case closed<small>${esc(s.args.outcome)}</small></div>`)); break; }
      const row = S.actionRows[key];
      if (row && row.querySelector) row.querySelector(".sum").textContent = actionSummary(s);
      else actBlock().appendChild(el("div", "arow", `<span class="ic">→</span><div><b>${esc(ACTION_NAMES[s.action] || s.action)}</b> <span class="sum">${esc(actionSummary(s))}</span></div>`));
      break;
    }
    case "verify": {
      const row = S.actionRows[key];
      if (row && row.querySelector && s.action !== "final re-check") {
        const chips = row.querySelector(".chips");
        if (chips) chips.insertAdjacentHTML("beforeend", `<em class="chip ${s.ok ? "ok" : "bad"}" title="${esc(s.check)}">${s.ok ? (MSG_ACTIONS.has(s.action) ? "delivered ✓✓" : "verified") : "not verified"}</em>`);
        if (s.action === "reconcile_payment") row.insertAdjacentHTML("beforeend", `<div class="sum" style="grid-column:2;margin-top:3px">${esc(s.check)}</div>`);
        delete S.actionRows[key];
        break;
      }
      if (s.action === "final re-check") actBlock().appendChild(el("div", "arow final", `<span class="ic">✓</span><div><b>Re-checked the source of truth</b> <span class="sum">${esc(s.check)}</span></div>`));
      break;
    }
    case "approval": {
      const pend = inc.pending || {};
      const card = el("div", "appr", `<b>Needs approval to ${esc(VERB[s.action] || s.action.replace(/_/g, " "))}</b><p>${esc(s.reason)}</p><div class="btns"></div>`);
      card.dataset.appr = `${s.incident}:${s.action}`;
      const btns = card.querySelector(".btns");
      (s.approvers || []).forEach((a) => {
        if (a === "merchant") {
          const y = el("button", "yes", "Approve as Meena"), n = el("button", "no", "Decline");
          y.onclick = () => { btns.innerHTML = "<span class='done'>Sending…</span>"; post("/api/approve", { incident_id: s.incident, approver: "merchant", yes: true }); };
          n.onclick = () => { btns.innerHTML = ""; post("/api/approve", { incident_id: s.incident, approver: "merchant", yes: false }); };
          btns.append(y, n);
        } else {
          const r = el("button", "risk", "Approve as Paytm Risk");
          r.onclick = () => { r.remove(); post("/api/approve", { incident_id: s.incident, approver: "paytm_ops", yes: true }); };
          btns.append(r);
        }
      });
      th.appendChild(card);
      break;
    }
    case "approval_result": {
      const card = $(`[data-appr^="${s.incident}:"]:last-of-type`) || [...$$(`[data-appr^="${s.incident}:"]`)].pop();
      if (card) {
        card.querySelectorAll(s.approver === "merchant" ? ".yes,.no" : ".risk").forEach((b) => b.remove());
        card.querySelector(".btns").insertAdjacentHTML("beforeend", `<div class="done">${s.approved ? "✓" : "✕"} ${esc(APPROVER[s.approver] || s.approver)} ${s.approved ? "approved" : "declined"}</div>`);
      }
      break;
    }
    case "followup": actBlock().appendChild(el("div", "fu", `↻ Came back on its own (${esc(s.via || "scheduled")}): ${esc(s.purpose)}`)); break;
  }
  if (!replay) { renderHead(); scroll(); }
}

function attachMedia(m, s, inc) {
  const steps = S.steps[s.incident] || [];
  const shotStep = steps.find((x) => x.kind === "tool" && x.tool === "read_screenshot" && x.n > s.n && x.n < s.n + 8);
  const docStep = steps.find((x) => x.kind === "tool" && x.tool === "read_document" && x.n > s.n && x.n < s.n + 4);
  const shotId = s.shot_id || (shotStep && shotStep.args.shot_id);
  const docId = s.doc_id || (docStep && docStep.args.doc_id);
  if (shotId) { const img = new Image(); img.src = `/api/shot/${shotId}.png`; img.className = "shot"; img.alt = "Payment screenshot"; img.onclick = () => openImg(img.src); m.appendChild(img); }
  if (docId) { const d = el("div", "doc", `<img src="/api/doc/${docId}.png" alt=""><span>📎 Bank SMS + police notice</span>`); d.onclick = () => openImg(`/api/doc/${docId}.png`); m.appendChild(d); }
}

function msgBubble(s, inc, merchantCh) {
  const r = s.result || {};
  const rule = S.actionRows[`${s.incident}:${s.action}`];
  const chips = `<div class="chips">${rule && rule.msgRule ? `<em class="chip ok" title="${esc(rule.reason)}">policy ${esc(rule.msgRule)}</em>` : ""}</div>`;
  if (s.action === "notify_merchant") {
    const cls = merchantCh ? "k2m" : "note";
    const by = merchantCh ? "Kavach → Meena · Paytm for Business" : "Private note to Meena";
    const extra = s.args.extra && s.args.extra.pack ? `<div class="links"><a href="/pack/${s.args.extra.pack}.pdf" target="_blank" rel="noopener">Open signed pack</a><a href="/verify/${s.args.extra.pack}" target="_blank" rel="noopener">Verify it</a></div>` : "";
    const cites = s.args.extra && s.args.extra.citations ? `<div class="chips">${s.args.extra.citations.map((c) => `<em class="chip" title="${esc(c.text)}">SOP ${esc(c.id)}${c.page ? " · p." + c.page : ""}</em>`).join("")}</div>` : "";
    return el("div", `m ${cls}`, `<span class="by">${by}</span>${esc(s.args.text)}${extra}${cites}${chips}<time>${tm(s.at)}</time>`);
  }
  const wa = !merchantCh;
  const by = wa ? `Kavach → ${esc(inc.customer && inc.customer.name || "customer")} · WhatsApp (simulated)` : "Card for the customer · shown on Meena's phone";
  let body = "";
  if (s.action === "send_customer_update_simulated") body = esc(s.args.text);
  if (s.action === "issue_verified_receipt") body = `<div class="rcpt"><b>✓ Verified with the UPI switch</b><br>${esc((r.summary || "").replace("Verified receipt shown", "Receipt"))}</div>`;
  if (s.action === "request_payment") body = `Pay ${rs(s.args.amount)} to Meena Kirana Store${r.upi_uri ? `<img class="qr" src="/api/qr?data=${encodeURIComponent(r.upi_uri)}" alt="UPI QR for ${rs(s.args.amount)}">` : ""}`;
  return el("div", `m k2c`, `<span class="by">${by}</span>${body}${chips}<time>${tm(s.at)}${wa ? "<span class='tick2'>✓✓</span>" : ""}</time>`);
}

function actionSummary(s) {
  const r = s.result || {};
  if (s.action === "generate_evidence_pack") return `token ${r.token}, SHA-256 ${String(r.pdf_sha256 || "").slice(0, 12)}…`;
  return r.summary || "";
}

// ===================================================================== payment intelligence
const COL_ORDER = ["claim", "switch", "ledger", "refund", "settlement", "bank", "pay1", "pay2"];
const EMPTY_COLS = { claim: ["Customer's screenshot", "Claim"], switch: ["UPI switch", "T1"], ledger: ["Shop's ledger", "T1"], settlement: ["Payout", "T1"] };

function tone(key, c, rec) {
  const sw = rec.switch;
  if (!c || c.status == null) return "";
  if (key === "claim") {
    if (rec.ledger && /USED ON/.test(rec.ledger.status || "")) return "bad";
    if (rec.refund && rec.refund.status) return "warn";
    if (!sw) return "";
    if (sw.status === "NOT FOUND" || (sw.amount != null && c.amount != null && sw.amount !== c.amount) || (sw.status && sw.status !== "SUCCESS")) return "bad";
    return "ok";
  }
  if (key === "switch") return c.status === "SUCCESS" ? "ok" : c.status === "PENDING" ? "warn" : "bad";
  if (key === "ledger") return /USED ON/.test(c.status) ? "bad" : /MISSING|NOT APPLIED|PARTIAL|UNPAID|NO ENTRY/.test(c.status) ? "warn" : /PAID|RECORDED/.test(c.status) ? "ok" : "";
  if (key === "bank") return /RETURNED/.test(c.status) ? "bad" : "warn";
  if (key === "refund") return c.status === "SUCCESS" ? "ok" : "warn";
  if (key === "settlement") return c.status === "SETTLED" ? "ok" : c.status === "NOT YET" ? "" : c.status === "HELD" ? "warn" : "bad";
  return c.status === "SUCCESS" ? "ok" : "";
}

function renderIntel() {
  const i = S.incidents[S.sel];
  const rec = (i && i.recon) || {};
  $("#intel-case").textContent = i ? `${i.facts && i.facts.case_id ? i.facts.case_id + " · " : ""}${i.id}` : "";
  // verdict
  const ev = i && [...(S.steps[i.id] || [])].reverse().find((s) => s.kind === "evidence");
  const vs = $("#verdict .vstamp");
  if (ev) { vs.hidden = false; vs.className = `vstamp ${ev.tone}`; vs.textContent = ev.stamp || ""; if (!ev.stamp) vs.hidden = true; }
  else vs.hidden = true;
  const idle = i && (i.pending && i.pending.approvers && i.pending.approvers.length ? "Waiting for an approval before acting." : i.status === "investigating" ? "Investigating…" : i.headline || STATUS[i.status]);
  $("#verdict .vtext").textContent = ev ? ev.verdict : i ? idle : "Each row below is a different system's version of the same payment.";
  $("#verdict .vsub").textContent = i && i.decisive ? i.decisive.text : i ? "" : "Kavach acts on the T1 rows (Paytm's own records), never on the claim.";
  // rows
  const keys = COL_ORDER.filter((k) => rec[k]);
  const show = keys.length ? keys : (i && i.kind === "freeze" ? [] : Object.keys(EMPTY_COLS));
  const loadingCol = S.loadingCol;
  $("#rows").innerHTML = show.map((k) => {
    const c = rec[k] || { label: EMPTY_COLS[k][0], tier: EMPTY_COLS[k][1] };
    const empty = c.status == null;
    const tn = tone(k, c, rec);
    const x = k === "claim" && rec.switch && rec.switch.amount != null && c.amount != null && rec.switch.amount !== c.amount;
    const ref = c.ref ? `<span class="mono">${esc(String(c.ref).length > 10 ? "…" + String(c.ref).slice(-6) : c.ref)}</span>` : "";
    return `<li class="rrow ${k === "claim" ? "claim" : ""} ${tn} ${empty ? "is-empty" : ""} ${loadingCol === k ? "loading" : ""} ${c.repaired ? "is-repaired" : ""}" data-col="${k}">
      <span class="r-lbl"><span class="tier ${c.tier === "Claim" ? "claim" : ""}">${esc(c.tier || "")}</span>${esc(c.label || k)}</span>
      <span class="r-amt ${x ? "x" : ""}">${empty ? "" : rs(c.amount)}</span>
      <span class="r-st">${empty ? "not checked yet" : esc(c.status)}</span>
      <span class="r-note">${ref}${c.when ? `<span>${esc(c.when)}</span>` : ""}${c.note ? `<span>${esc(c.note)}</span>` : ""}</span>
      ${c.repaired ? `<span class="fixed">REPAIRED</span>` : ""}
    </li>`;
  }).join("");
  // repaired animation once
  const lr = $('#rows [data-col="ledger"].is-repaired');
  if (lr && !(S.animated || {})[i.id]) { (S.animated ||= {})[i.id] = true; lr.classList.add("repaired"); }
  // money
  const m = $("#money");
  if (i && i.money && i.money.amount) { m.hidden = false; m.querySelector("b").textContent = rs(i.money.amount); m.querySelector("span").textContent = i.money.label; } else m.hidden = true;
  renderNext(i); renderChecks(i); renderClocks(i); renderSimbar();
}
function markLoading(tool) { S.loadingCol = TOOL_COL[tool]; const r = $(`#rows [data-col="${S.loadingCol}"]`); if (r) r.classList.add("loading"); }
function unmarkLoading() { S.loadingCol = null; }

function renderNext(i) {
  const n = $("#next");
  if (!i) { n.innerHTML = ""; return; }
  n.className = "next";
  if (i.status === "resolved") { n.classList.add("done"); n.innerHTML = `<b>Outcome</b><div class="big">✓ ${esc(i.outcome || "Closed")}</div><div>${i.outcome_verified ? "Re-verified against the source of truth before closing." : ""}</div>`; return; }
  if (i.pending && i.pending.approvers && i.pending.approvers.length) {
    n.innerHTML = `<b>Waiting on</b><div class="big">${i.pending.approvers.map((a) => APPROVER[a] || a).join(" + ")} to ${esc(VERB[i.pending.action] || i.pending.action.replace(/_/g, " "))}</div><div>${esc(i.pending.ask)}</div>`; return;
  }
  const fu = S.followups.filter((f) => f.incident === i.id && !f.fired).sort((a, b) => a.due.localeCompare(b.due))[0];
  if (fu) { n.innerHTML = `<b>Next, on its own</b><div class="big">${esc(fu.purpose)}</div><div class="due">due ${dayTm(fu.due)} · or sooner if a status callback arrives</div>`; return; }
  n.innerHTML = i.status === "investigating" ? `<b>Now</b><div class="big">Investigating with tools…</div>` : `<b>Status</b><div class="big">${esc(STATUS[i.status] || i.status)}</div><div>${esc(i.headline || "")}</div>`;
}

function renderChecks(i) {
  const w = $("#checks-wrap"), ol = $("#checks");
  if (!i) { w.hidden = true; return; }
  const steps = S.steps[i.id] || [];
  const items = [];
  steps.forEach((s, idx) => {
    if (s.kind !== "action" || ["notify_merchant", "resolve_incident", "create_support_case"].includes(s.action)) return;
    const v = steps.slice(idx + 1).find((x) => x.kind === "verify" && x.action === s.action);
    items.push(`<li class="${v && !v.ok ? "no" : ""}"><i>${v ? (v.ok ? "✓" : "✕") : "…"}</i><span><b>${esc(ACTION_NAMES[s.action] || s.action)}</b>${v ? ` · ${esc(v.check)}` : ""}</span></li>`);
  });
  const denies = steps.filter((s) => s.kind === "policy" && s.verdict === "DENY").map((s) => `<li class="no"><i>⦸</i><span><b>Refused: ${esc(DENY_NAMES[s.action] || s.action)}</b> · ${esc(s.rule)}</span></li>`);
  const all = items.concat(denies);
  w.hidden = !all.length; ol.innerHTML = all.slice(-9).join("");
}

function renderClocks(i) {
  const box = $("#clocks");
  const clocks = i && i.facts && i.facts.clocks;
  const pack = i && i.facts && i.facts.pack;
  if (!clocks && !pack) { box.hidden = true; return; }
  box.hidden = false;
  const now = S.world ? new Date(S.world.now) : new Date();
  let h = "";
  if (pack) h += `<h3>Signed evidence pack <small>Ed25519 · SHA-256 bound</small></h3><div class="next"><div class="big">${esc(pack.token)}</div><div><a href="/verify/${esc(pack.token)}" target="_blank" rel="noopener" style="color:var(--chalk)">Verify it</a> · <a href="/pack/${esc(pack.token)}.pdf" target="_blank" rel="noopener" style="color:var(--chalk)">Open PDF</a></div></div>`;
  if (clocks) h += `<h3 style="margin-top:12px">SOP clocks <small>only dated events start them</small></h3>` + clocks.map((c) => {
    let pct = 0, left = "";
    if (c.start && c.due) { const a = new Date(c.start), b = new Date(c.due); pct = Math.max(0, Math.min(100, 100 * (now - a) / (b - a))); left = `${Math.max(0, Math.ceil((b - now) / 864e5))} days left`; }
    const tag = c.state === "running" ? (pct >= 100 ? "due" : left) : c.state === "ambiguous_anchor" ? "two possible anchors" : "needs a dated event";
    return `<div class="ck ${pct >= 100 ? "late" : ""}"><div class="ck-top"><b>${esc(c.clock)}</b><span>${esc(tag)}</span></div><div class="bar"><i style="width:${pct}%"></i></div><small>${c.start ? `${esc(c.start)} → ${esc(c.due || "?")}` : esc(c.starts_on)}</small></div>`;
  }).join("");
  box.innerHTML = h;
}

function renderSimbar() {
  const bar = $("#simbar"); if (!bar) return;
  const btns = simActions();
  if (window.stageActions) stageActions(btns);
  const sig = btns.map((b) => b[0]).join("|");
  if (sig === bar.dataset.sig) return;   // don't rebuild under the user's cursor
  bar.dataset.sig = sig;
  if (!btns.length) { bar.hidden = true; return; }
  bar.hidden = false;
  bar.innerHTML = `<p>Simulator · make the world move</p><div class="btns"></div>`;
  btns.forEach(([label, fn, go]) => { const b = el("button", go ? "go" : "", esc(label)); b.onclick = () => { b.disabled = true; fn(); }; bar.querySelector(".btns").appendChild(b); });
}
function simActions() {
  const i = S.incidents[S.sel];
  const w = S.world;
  const btns = [];
  const pend = (w && w.transactions || []).filter((t) => t.status === "PENDING");
  pend.slice(0, 1).forEach((t) => {
    btns.push([`Bank confirms ${rs(t.amount)}`, () => post("/api/world/force", { txn_id: t.txn_id, status: "SUCCESS" }), true]);
    btns.push(["Bank fails it", () => post("/api/world/force", { txn_id: t.txn_id, status: "FAILED" })]);
  });
  const opsWait = Object.values(S.incidents).find((x) => x.pending && x.pending.approvers.includes("paytm_ops") && !x.pending.approvers.includes("merchant"));
  if (opsWait) btns.push(["Approve as Paytm Risk", () => post("/api/approve", { incident_id: opsWait.id, approver: "paytm_ops", yes: true }), true]);
  const fus = S.followups.filter((f) => !f.fired && S.incidents[f.incident] && S.incidents[f.incident].status !== "resolved");
  if (fus.some((f) => /payout/.test(f.purpose))) btns.push(["Skip to tomorrow's 9:00 payout", () => post("/api/clock/skip-to-payout"), true]);
  const pendRef = ((w && w.refunds) || []).filter((r) => r.status === "PENDING" && r.resolve_at);
  if (fus.some((f) => /refund/i.test(f.purpose)) && pendRef.length) {
    const secs = Math.round(Math.max(30, (Math.max(...pendRef.map((r) => new Date(r.resolve_at))) - new Date(w.now)) / 1000 + 15));
    btns.push([`Skip ${Math.ceil(secs / 60)} min: refund service credits the customer`, () => post("/api/clock/advance", { seconds: secs })]);
  }
  const mine = fus.filter((f) => i && f.incident === i.id);
  if (mine.some((f) => /^Day 5/.test(f.purpose))) btns.push(["Skip to day 5", () => post("/api/clock/advance", { seconds: Math.round(Math.max(60, (new Date(mine.find((f) => /^Day 5/.test(f.purpose)).due) - new Date(S.world.now)) / 1000 + 60)) }), true]);
  else if (mine.some((f) => /^Day 7/.test(f.purpose))) btns.push(["Skip to day 7", () => post("/api/clock/advance", { seconds: Math.round(Math.max(60, (new Date(mine.find((f) => /^Day 7/.test(f.purpose)).due) - new Date(S.world.now)) / 1000 + 60)) }), true]);
  return btns;
}

// ===================================================================== composer
function syncAs() {
  $$(".as button").forEach((b) => b.classList.toggle("on", b.dataset.as === S.as));
  $("#text").placeholder = S.as === "customer" ? "Type as the customer (WhatsApp)…" : "Meena ji, likhiye ya boliye…";
}
$$(".as button").forEach((b) => b.onclick = () => { S.as = b.dataset.as; syncAs(); renderSuggest(); });

function setDraft(d) {
  S.draft = d;
  if (d.as) { S.as = d.as; syncAs(); }
  else if (d.next_doc || d.doc_id) { S.as = "merchant"; syncAs(); }
  $("#text").value = d.text || "";
  const a = $("#attach");
  if (d.shot_id) { S.lastShot = d.shot_id; a.hidden = false; a.innerHTML = `<img src="/api/shot/${d.shot_id}.png" alt=""> Screenshot attached <button type="button" aria-label="Remove">✕</button>`; }
  else if (d.doc_id) { a.hidden = false; a.innerHTML = `<img src="/api/doc/${d.doc_id}.png" alt=""> Bank SMS + police notice <button type="button" aria-label="Remove">✕</button>`; }
  else { a.hidden = true; a.innerHTML = ""; }
  a.querySelector("button")?.addEventListener("click", () => { S.draft = { text: $("#text").value }; a.hidden = true; });
  if (d.next_doc) S.nextDoc = d.next_doc;
  if (d.auto) $("#composer").requestSubmit();
  renderSuggest();
}

function renderSuggest() {
  const opts = suggestOpts();
  const box = $("#suggest"); box.innerHTML = "";
  opts.forEach((o) => { const b = el("button", o.cls || "", esc(o.label)); b.type = "button"; b.onclick = () => { S.as = o.as; syncAs(); setDraft(o.draft); }; box.appendChild(b); });
  if (window.stageSuggest) stageSuggest(opts);
}
function suggestOpts() {
  const i = S.incidents[S.sel];
  const opts = [];
  if (S.nextDoc && !(S.draft && S.draft.doc_id)) opts.push({ cls: "doc", label: "📎 Meena forwards the bank notice", as: "merchant", draft: { text: "Bank ka SMS aur police ka notice yeh hai. Account mein 3.1 lakh atak gaye.", doc_id: S.nextDoc } });
  if (i && i.status !== "resolved") {
    if (i.kind === "payment_claim" && i.status === "watching" && i.facts.txn_id && i.recon.switch && i.recon.switch.status === "PENDING") opts.push({ cls: "as-m", label: "Dobara pay karwa do", as: "merchant", draft: { text: "Customer se dobara pay karwa do" } });
    if (i.channel === "whatsapp") opts.push({ cls: "as-c", label: "Any update?", as: "customer", draft: { text: "Any update on my payment?" } });
    if (i.kind === "freeze" && !(i.decisive && i.decisive.label === "Why Kavach held back")) {
      const f = i.facts || {};
      if (f.pack && !(f.case_events || {}).bank_complaint) opts.push({ cls: "doc", label: "Bank ne complaint le li ✓", as: "merchant", draft: { text: "Bank ne complaint le li, acknowledgement mil gaya." } });
      opts.push({ cls: "as-m", label: "Bank ko kitne din milte hain?", as: "merchant", draft: { text: "Bank ko meri shikayat aage bhejne ke liye kitne din milte hain?" } });
      opts.push({ cls: "as-m", label: "Caller wants ₹20,000", as: "merchant", draft: { text: "Ek aadmi phone karke 20 hazaar maang raha hai complaint wapas lene ke liye" } });
      opts.push({ cls: "as-m", label: "Payout doosre account mein", as: "merchant", draft: { text: "Settlement doosre account mein bhej do" } });
    }
  }
  return opts;
}

$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#text").value.trim(); if (!text) return;
  const d = S.draft || {};
  if (d.doc_id) S.nextDoc = null;
  const i = S.incidents[S.sel];
  if (S.as === "customer") post("/api/customer/message", { text, shot_id: d.shot_id || null, customer: i && i.channel === "whatsapp" ? i.customer : null });
  else post("/api/merchant/message", { text, shot_id: d.shot_id || null, doc_id: d.doc_id || null });
  S.draft = null; $("#text").value = ""; $("#attach").hidden = true; S.follow = true; unlockAudio();
});

$("#clip").onclick = () => { $("#clip-menu").hidden = !$("#clip-menu").hidden; };
$$("#clip-menu [data-up]").forEach((b) => b.onclick = () => { S.upKind = b.dataset.up; $("#clip-menu").hidden = true; $("#file").click(); });
$("#file").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("kind", S.upKind || "screenshot"); fd.append("file", f);
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  if (r.ok) { const d = await r.json(); if (S.upKind === "screenshot") { d.as = S.as; d.text = S.as === "customer" ? "I paid. Screenshot attached." : d.text; } setDraft(d); }
  e.target.value = "";
};

(() => {   // voice in: Sarvam Saaras when configured, else the browser's recogniser
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mic = $("#mic");
  const tgt = () => (document.body.classList.contains("view-stage") ? $("#m-text") : $("#text"));
  const onState = (on) => { mic.classList.toggle("on", on); $("#m-mic") && $("#m-mic").classList.toggle("on", on); window.stageListening && stageListening(on); };
  let rec = null, mr = null, chunks = [];
  if ($("#m-mic")) $("#m-mic").onclick = () => mic.onclick();
  mic.onclick = async () => {
    if (S.intg && S.intg.sarvam && navigator.mediaDevices && window.MediaRecorder) {
      if (mr) { mr.stop(); return; }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mr = new MediaRecorder(stream); chunks = [];
        mr.ondataavailable = (e) => chunks.push(e.data);
        mr.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop()); onState(false); mr = null;
          tgt().value = "Sarvam is listening…";
          const fd = new FormData(); fd.append("file", new Blob(chunks, { type: "audio/webm" }), "voice.webm");
          const r = await fetch("/api/voice", { method: "POST", body: fd });
          const j = await r.json().catch(() => ({}));
          tgt().value = r.ok ? j.transcript : "";
        };
        mr.start(); onState(true);
        setTimeout(() => mr && mr.state === "recording" && mr.stop(), 28000);
      } catch (_) { onState(false); mr = null; }
      return;
    }
    if (!SR) { mic.title = "Voice input needs Chrome or a Sarvam key. Typing always works."; return; }
    if (rec) { rec.stop(); return; }
    rec = new SR(); rec.lang = "hi-IN"; rec.interimResults = true; onState(true);
    rec.onresult = (e) => { tgt().value = [...e.results].map((r) => r[0].transcript).join(" "); };
    rec.onend = rec.onerror = () => { onState(false); rec = null; };
    rec.start();
  };
})();

// ===================================================================== voice out + soundbox
let voices = [];
if ("speechSynthesis" in window) { voices = speechSynthesis.getVoices(); speechSynthesis.onvoiceschanged = () => { voices = speechSynthesis.getVoices(); }; }
const audioQ = []; let audioBusy = false;
function playNext() {
  if (audioBusy || !audioQ.length) return;
  audioBusy = true;
  const item = audioQ.shift();
  const a = new Audio(item.src);
  if (window.stageVoice) stageVoice.audio(a, item.text, item.voice);
  a.onended = a.onerror = () => { audioBusy = false; window.stageVoice && stageVoice.end(); playNext(); };
  a.play().catch(() => { audioBusy = false; window.stageVoice && stageVoice.end(); playNext(); });
}
function say(text, voice = "kavach") {
  if (!text) return;
  if (!S.sound) { window.stageVoice && stageVoice.silent(text, voice); return; }
  if (window.stageVoice) stageVoice.pending(text, voice);
  if (window.stageSpeak && voice === "kavach") stageSpeak(text);
  if (S.intg && S.intg.sarvam) { audioQ.push({ src: `/api/tts?voice=${voice}&text=${encodeURIComponent(text)}`, text, voice }); playNext(); return; }
  if (!("speechSynthesis" in window)) { window.stageVoice && stageVoice.silent(text, voice); return; }
  const u = new SpeechSynthesisUtterance(text);
  if (window.stageVoice) {
    u.onstart = () => stageVoice.synth(text, voice);
    u.onboundary = (e) => stageVoice.word(e.charIndex);
    u.onend = u.onerror = () => stageVoice.end();
  }
  const v = voices.find((x) => x.lang === "hi-IN") || voices.find((x) => x.lang.startsWith("hi"));
  if (v) u.voice = v; u.lang = "hi-IN";
  speechSynthesis.speak(u);
}
function unlockAudio() { if ("speechSynthesis" in window && !S.unlocked) { S.unlocked = true; speechSynthesis.speak(new SpeechSynthesisUtterance("")); } }
function soundbox(ev) {
  const sb = $("#soundbox");
  $("#sb-line").textContent = ev.text;
  sb.classList.add("speaking"); clearTimeout(sb._t); sb._t = setTimeout(() => sb.classList.remove("speaking"), 3200);
  say(`पेटीएम पर ${Number(ev.amount).toLocaleString("en-IN")} रुपये प्राप्त हुए`, "soundbox");
}

// ===================================================================== simulate menu
const simMenu = $("#sim-menu");
$("#sim-open").onclick = (e) => { e.stopPropagation(); simMenu.hidden = !simMenu.hidden; };
$("#empty-sim").onclick = (e) => { e.stopPropagation(); simMenu.hidden = false; };
document.addEventListener("click", (e) => { if (!simMenu.contains(e.target) && e.target.id !== "sim-open") simMenu.hidden = true; if (!$("#clip-menu").contains(e.target) && e.target.closest("#clip") == null) $("#clip-menu").hidden = true; });
async function scenario(ds) {
  simMenu.hidden = true; S.follow = true; unlockAudio();
  if (ds.scn === "live_check") { const oid = prompt("Paytm order ID (a real order on your staging MID):"); if (oid) await post("/api/live/check", { order_id: oid }); return; }
  if (ds.scn === "skip_days") { await post("/api/clock/skip-days", { days: Number(ds.days || 13) }); return; }
  const body = {};
  if (ds.mode) body.mode = ds.mode;
  if (ds.notice) body.notice_amount = Number(ds.notice);
  if (ds.record === "false") body.paytm_record = false;
  if (ds.genuine === "false") body.genuine = false;
  if (ds.ftype) body.freeze_type = ds.ftype;
  if (ds.mule === "true") body.mule = true;
  if (ds.shown) body.shown_amount = Number(ds.shown);
  if (ds.amount) body.amount = Math.max(20, Math.round(Number(ds.amount)) || 4200);
  const d = await post(`/api/scenario/${ds.scn}`, body);
  if (d && d.text) { setDraft({ ...d, auto: true }); }
  else if (d && d.next_doc) { S.nextDoc = d.next_doc; renderSuggest(); }   // proactive: nobody types; Meena can forward the notice later
}
$$("[data-scn]").forEach((b) => b.onclick = () => scenario({ ...b.dataset }));
$("#own-go").onclick = () => scenario({ scn: "customer_claim", mode: "fake_amount", amount: $("#own-amt").value });   // bill + screenshot show your number; the bank shows what was really paid

// ===================================================================== desk
const SIGNAL_SHORT = { repeat_reports: "Repeat reports", fan_in: "Fan-in", round_amounts: "Round sums", shared_settlement_account: "Shared account", new_account: "New merchant", no_counter_activity: "No Soundbox" };
$$(".seg button").forEach((b) => b.onclick = () => {
  S.view = b.dataset.view;
  $$(".seg button").forEach((x) => x.classList.toggle("on", x === b));
  document.body.classList.toggle("view-stage", S.view === "stage");
  $("#app").classList.toggle("desk-view", S.view === "desk");
  $("#desk").hidden = S.view !== "desk";
  if (S.view === "desk") loadDesk();
});
async function loadDesk() { renderDesk(await fetch("/api/desk").then((r) => r.json())); }
function renderDesk(v) {
  S.desk = v;
  $("#desk-grid").innerHTML = v.rows.map(deskCard).join("");
  bindAssign();
  const s = v.summary;
  $("#desk-sum").innerHTML = Object.values(s).some(Boolean) ? `<b class="g">${s["Consistent"]}</b> consistent · <b class="a">${s["Insufficient"]}</b> need records · <b class="r">${s["Escalate for EDD"]}</b> escalated for EDD` : "";
  $("#desk-run").disabled = v.running;
}
function bindAssign() { $$("#desk-grid [data-assign]").forEach((b) => b.onclick = async () => renderDesk(await post("/api/desk/assign", { mid: b.dataset.assign }))); }
function deskCard(m) {
  const r = m.result, o = r ? r.outcome : null;
  const cls = !r ? "" : o === "Consistent" ? "good" : o === "Insufficient" ? "warn" : "bad";
  const sigs = r ? r.signals.map((s) => `<li class="${s.hit ? (s.strong ? "hit" : "weak") : ""}" title="${esc(s.value)}"><i></i>${esc(SIGNAL_SHORT[s.id] || s.id)}<span>${esc(s.value)}</span></li>`).join("") : "";
  return `<article class="dcard ${cls}" id="d-${m.mid}">
    <header><div><b>${esc(m.name)}</b><small>${esc(m.city)} · ${m.months_on_paytm} months on Paytm · ${esc(m.mid)}</small></div>${r ? `<span class="dstamp ${cls}">${esc(o === "Escalate for EDD" ? "EDD" : o)}</span>` : ""}</header>
    <p class="dmoney">${rs(m.frozen_amount)} frozen over ${rs(m.disputed_amount)} disputed <small>(${m.disputed_count} credit${m.disputed_count > 1 ? "s" : ""})</small></p>
    ${r ? `<ul class="sigs">${sigs}</ul><p class="dact">${esc(r.action)}</p>` : `<p class="dwait">Not checked yet</p>`}
    ${m.pack ? `<p class="dpack">Signed pack ${esc(m.pack.token)}: <b>${esc(m.pack.verify)}</b> <a href="/verify/${esc(m.pack.token)}" target="_blank" rel="noopener">verify</a></p>` : ""}
    ${r && o === "Escalate for EDD" ? (m.assigned ? `<p class="dassigned">With an EDD reviewer</p>` : `<button class="dbtn" data-assign="${esc(m.mid)}">Assign to an EDD reviewer</button>`) : ""}
  </article>`;
}
function onDesk(ev) {
  if (ev.phase === "finished") { renderDesk(ev.view); return; }
  if (S.view !== "desk" || !S.desk) return;
  const card = $(`#d-${ev.mid}`); if (!card) return;
  if (ev.phase === "checking") { card.classList.add("checking"); card.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" }); }
  if (ev.phase === "done") { const row = S.desk.rows.find((x) => x.mid === ev.mid); row.result = ev.result; card.outerHTML = deskCard(row); bindAssign(); }
}
$("#desk-run").onclick = async () => { $("#desk-run").disabled = true; $$(".dcard").forEach((c) => { c.className = "dcard"; }); await post("/api/desk/run"); };

// ===================================================================== drawer: systems + automations
function openDrawer(tab) { $("#drawer").hidden = false; $$(".dtabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab)); $$(".dpane").forEach((p) => p.hidden = p.dataset.pane !== tab); if (tab === "systems") renderSystems(); else refreshAutomation(); }
$$(".dtabs button").forEach((b) => b.onclick = () => openDrawer(b.dataset.tab));
$("#open-sys").onclick = () => openDrawer("systems");
$("#close-drawer").onclick = () => { $("#drawer").hidden = true; };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { $("#drawer").hidden = true; simMenu.hidden = true; } });
function renderSystems() {
  const w = S.world; if (!w) return;
  const tx = w.transactions.slice(0, 10).map((t) => `<tr><td class="muted">${tm(t.created_at)}</td><td class="amt">${rs(t.amount)}</td><td><span class="tp ${t.status}">${t.status}</span></td><td class="muted mono">…${t.utr.slice(-6)}</td></tr>`).join("");
  const bills = (w.bills || []).map((b) => `<tr><td>${esc(b.bill_id)}</td><td class="amt">${rs(b.amount)}</td><td><span class="tp ${b.status}">${b.status}</span></td><td class="muted">${esc(b.customer || "walk-in")} · paid ${rs(b.paid_amount)}</td></tr>`).join("");
  const wh = (w.webhooks_failed || []).map((x) => `<tr><td class="mono">${esc(x.txn_id)}</td><td>${x.attempts.map((a) => a.http).join(", ")}</td><td><span class="tp FAILED">FAILED</span></td></tr>`).join("");
  const st = w.settlements.slice(0, 4).map((s) => `<tr><td class="muted">${s.business_date}</td><td class="amt">${rs(s.amount)}</td><td><span class="tp ${s.status}">${s.status}</span></td></tr>`).join("");
  const ob = w.outbox.slice(0, 8).map((m) => `<li><b>${m.to === "customer" ? (m.channel === "whatsapp" ? "WhatsApp to customer" : "Card for customer") : "Message to Meena"}</b> · ${esc(m.text.slice(0, 110))}${m.text.length > 110 ? "…" : ""}</li>`).join("");
  const ops = w.ops_queue.slice(0, 6).map((o) => `<tr><td>${esc(o.ticket_id)}</td><td>${esc(o.title)}</td><td><span class="tp ${o.status}">${o.status.replace("_", " ").toLowerCase()}</span></td></tr>`).join("");
  $("#sys").innerHTML = `<h3>UPI switch <small>payments to Meena, latest first</small></h3><table class="tbl">${tx}</table>
    <h3>Shop's billing app (POS ledger) <small>synthetic</small></h3><table class="tbl">${bills}</table>
    <h3>POS webhook failures</h3>${wh ? `<table class="tbl">${wh}</table>` : "<p class='dnote'>None.</p>"}
    <h3>Payouts to her bank <small>next run ${dayTm(w.next_settlement)}</small></h3><table class="tbl">${st}</table>
    ${w.settlement_config.paused ? `<div class="held">Payouts held in Meena's Paytm settlement balance. Nothing moved to another account.</div>` : ""}
    <h3>Messages <small>simulated delivery</small></h3>${ob ? `<ul class="outbox">${ob}</ul>` : "<p class='dnote'>None yet.</p>"}
    <h3>Paytm Ops queue <small>humans</small></h3>${ops ? `<table class="tbl">${ops}</table>` : "<p class='dnote'>Empty.</p>"}`;
}
async function refreshAutomation() {
  try {
    const a = await fetch("/api/automation").then((r) => r.json());
    $("#auto-note").textContent = a.n8n ? "Events are POSTed to your n8n workflow (N8N_WEBHOOK_URL)." : "N8N_WEBHOOK_URL is not set, so events stay in this local log. Import integrations/n8n/kavach-followups.json into n8n to deliver them.";
    $("#autolog").innerHTML = a.log.map((r) => `<li><b>${esc(r.event.replace(/_/g, " "))}</b> <span class="t">${tm(r.at)}</span><br><small>${esc(r.payload.purpose || r.payload.summary || r.payload.reason || r.payload.merchant || "")}</small> <em>${esc(r.delivery)}</em></li>`).join("") || "<li>No events yet.</li>";
  } catch (_) {}
}

// ===================================================================== misc
function openImg(src) { const d = $("#img-dialog"); d.querySelector("img").src = src; d.showModal(); }
$("#reset").onclick = () => post("/api/reset");
$("#sound").onclick = (e) => { S.sound = !S.sound; e.target.textContent = S.sound ? "🔊" : "🔇"; e.target.setAttribute("aria-pressed", S.sound); if (!S.sound && "speechSynthesis" in window) speechSynthesis.cancel(); };
$("#open-eval").onclick = async () => {
  const r = await fetch("/api/eval").then((x) => x.json());
  const body = $("#eval-body");
  const fw = r.freeze_watch;
  const FAM = { total_freeze_bounce: "Total freeze: next payout bounces", debit_freeze_own_payment: "Debit freeze: her own payment declined (YE)",
    debit_freeze_no_signal: "Debit freeze, no signal reaches Paytm (expect silence)", healthy_account: "Healthy account (expect silence)",
    mule_flagged: "Risk holds 2 signals (expect details withheld)", notice_agrees: "Notice agrees with the record (expect pack + request)",
    notice_conflicts: "Notice contradicts the record (expect refusal)", chargeback_handed_over: "Chargeback, Meena handed over the goods (expect reply in time)",
    chargeback_not_handed_over: "Chargeback, she didn't (expect honest accept)", chargeback_no_answer: "Chargeback, no answer (expect reminders, nothing filed)" };
  const freezeHtml = fw ? `<h2>Money clocks (freezes and chargebacks): ${fw.passed} of ${fw.scenarios} scenarios behave as expected.</h2>
      <p class="sub">Separate generator (eval/freeze_gen.py), scored by checks written in the runner, not borrowed from Kavach's policy.</p>
      <table><thead><tr><th>Family</th><th>Passed</th></tr></thead><tbody>${Object.entries(fw.by_family).map(([f, v]) => `<tr><td>${esc(FAM[f] || f)}</td><td class="k">${v.passed}/${v.n}</td></tr>`).join("")}</tbody></table>
      <table><tbody><tr><td>Caught when Paytm has a signal</td><td class="k">${esc(fw.detected_when_paytm_has_a_signal)}</td></tr>
      <tr><td>False alarms (healthy or blind accounts)</td><td class="k">${fw.false_alarms_on_healthy_or_blind}</td></tr>
      <tr><td>Case details leaked to a flagged merchant</td><td class="k">${fw.tipping_off_leaks}</td></tr>
      <tr><td>Payouts re-routed during a freeze</td><td class="k">${fw.reroutes}</td></tr>
      <tr><td>Chargeback replies filed without Meena</td><td class="k">${fw.chargeback_replies_without_meena ?? "—"}</td></tr>
      <tr><td>Delivery proof invented</td><td class="k">${fw.invented_delivery_proof ?? "—"}</td></tr></tbody></table>
      <h3>Does this test have teeth? We broke the guard on purpose.</h3>
      <table><thead><tr><th>Variant</th><th>Leaks</th><th>Failed</th></tr></thead><tbody>${(fw.mutation_check || []).map((m) => `<tr><td>${esc(m.variant)}</td><td class="${m.leaks ? "b" : "k"}">${m.leaks}/${m.n}</td><td class="${m.failed ? "b" : "k"}">${m.failed}/${m.n}</td></tr>`).join("")}</tbody></table>
      <p class="caveat">${esc(fw.label)} ${esc(fw.honest_limit)}</p><hr>` : "";
  if (r.error) body.innerHTML = `<h2>No test run yet</h2><p class="sub">${esc(r.error)}</p>`;
  else body.innerHTML = freezeHtml + `<h2>Everyday incidents: ${r.n} generated. Kavach vs a bot that trusts what it's shown.</h2>
      <p class="sub">Scenarios and expected outcomes come from a separate generator (eval/generate.py) that never imports Kavach's decision code. Run ${esc(r.ran_at)}.</p>
      <table><thead><tr><th>What we measured</th><th>Kavach</th><th>Naive approach</th></tr></thead><tbody>
      ${r.metrics.map((m) => `<tr><td>${esc(m.label)}</td><td class="k">${esc(m.kavach)}</td><td class="b">${esc(m.baseline)}</td></tr>`).join("")}</tbody></table>
      <p class="caveat">${esc(r.caveat)}</p>`;
  $("#eval-dialog").showModal();
  requestAnimationFrame(() => { $("#eval-dialog").scrollTop = 0; body.scrollTop = 0; body.firstElementChild && body.firstElementChild.scrollIntoView({ block: "start" }); });
};

boot();

// ===================================================================== judge's phone
$("#open-phone").onclick = async () => {
  const x = await fetch("/api/integrations").then((r) => r.json()).catch(() => ({}));
  const url = (x.public_url || location.origin).replace(/\/$/, "") + "/m";
  $("#phone-qr").src = `/api/qr?data=${encodeURIComponent(url)}`;
  $("#phone-url").textContent = url;
  $("#phone-dialog").showModal();
};

// ===================================================================== business case (judge-facing)
$("#open-biz").onclick = async () => {
  const b = await fetch("/api/business").then((r) => r.json());
  const F = { high: "k", medium: "", "low (near term)": "b" };
  $("#biz-body").innerHTML = `<h2>This problem exists today</h2>
    <table><tbody>${b.evidence.map((x) => `<tr><td>${esc(x.claim)}<br><small class="dim">${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.source)}</a>` : esc(x.source)}</small></td></tr>`).join("")}</tbody></table>
    <h2 style="margin-top:22px">Why Paytm would ship this</h2>
    <p class="sub">${esc(b.pricing.model)}. ${esc(b.pricing.unit)}. Merchants pay ${esc(b.pricing.merchant_price)}.</p>
    <h3>Measured in this repo</h3><table><tbody>${b.measured.map((m) => `<tr><td>${esc(m.label)}<br><small class="dim">${esc(m.note)}</small></td><td class="k">${esc(m.value ?? "—")}</td></tr>`).join("")}</tbody></table>
    <h3>What Paytm already has, and what it would take</h3><table><thead><tr><th>Part</th><th>Paytm has</th><th>Needs</th><th>Feasibility</th></tr></thead><tbody>
    ${b.components.map((c) => `<tr><td><b>${esc(c.part)}</b><br><small class="dim">${esc(c.signal)}</small></td><td>${esc(c.paytm_has)}</td><td>${esc(c.needs)}</td><td class="${F[c.feasibility] || ""}">${esc(c.feasibility)}<br><small class="dim">${esc(c.demo || "")}</small></td></tr>`).join("")}</tbody></table>
    <h3>Rollout, safest first</h3><table><thead><tr><th>Phase</th><th>What</th><th>Proves</th><th>Risk</th></tr></thead><tbody>
    ${b.rollout.map((r) => `<tr><td><b>${esc(r.phase)}</b></td><td>${esc(r.what)}</td><td>${esc(r.proves)}</td><td>${esc(r.risk)}</td></tr>`).join("")}</tbody></table>
    <h3>Numbers only Paytm has (we won't invent them)</h3><ul class="biz-list">${b.paytm_only_inputs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <p class="caveat">${esc(b.label)}</p>`;
  $("#biz-dialog").showModal();
  requestAnimationFrame(() => { $("#biz-dialog").scrollTop = 0; $("#biz-body").firstElementChild.scrollIntoView({ block: "start" }); });
};
