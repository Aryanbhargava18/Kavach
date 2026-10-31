"use strict";
/* Case story: one real case end to end, built live from the engine's step log. */
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
const T2N = { read_screenshot: "customer", lookup_transaction: "switch", get_payment_status: "switch", find_duplicate_payments: "switch", check_sale_pattern: "switch",
    get_merchant_ledger: "ledger", get_refund_status: "refund", get_settlement_status: "payout", get_bank_signal: "payout", get_incident_policy: "policy",
    get_own_payment_declines: "switch", get_risk_signals: "policy", get_disputes: "refund", paytm_order_status: "switch",
    route_sop: "policy", get_sop_clocks: "policy", ask_sop: "policy", read_document: "policy", parse_notice: "policy" };
const A2N = { reconcile_payment: "ledger", initiate_refund: "refund", request_settlement_hold: "payout", change_settlement_account: "payout",
    send_customer_update_simulated: "customer", issue_verified_receipt: "customer", request_payment: "customer", generate_evidence_pack: "policy",
    create_support_case: "policy", record_case_event: "policy", draft_escalation: "policy", draft_lien_request: "policy", prepare_pa_upload: "payout", issue_live_pack: "policy", submit_dispute_response: "refund", accept_chargeback: "refund", validate_settlement_account: "payout", release_settlement_hold: "payout", escalate_to_human: "policy", replay_soundbox: null };
const TVERB = { read_screenshot: "Reading the customer's screenshot", lookup_transaction: "Finding the payment at the UPI switch",
    get_payment_status: "Asking the UPI switch what really happened", get_merchant_ledger: "Checking Meena's billing app",
    get_refund_status: "Checking for refunds on this payment", get_settlement_status: "Checking when it reaches Meena's bank",
    get_soundbox_log: "Checking what the Soundbox announced", get_incident_policy: "Loading the rules for this kind of problem",
    find_duplicate_payments: "Looking for a double charge", get_bank_signal: "Checking what Paytm can see of her bank",
    read_document: "Reading the bank notice", parse_notice: "Pulling the facts out of the notice", route_sop: "Finding the right step in the cyber-fraud SOP",
    get_sop_clocks: "Working out the deadlines", ask_sop: "Looking it up in the SOP", check_sale_pattern: "Comparing with her usual sales",
    get_own_payment_declines: "Checking her own payments through the Paytm app", get_disputes: "Reading the dispute desk", paytm_order_status: "Asking Paytm's real Transaction Status API", get_risk_signals: "Checking with Paytm Risk before saying anything" };

// ---------------------------------------------------------------- state
const S = { incidents: {}, steps: {}, world: null, followups: [], sel: null, sound: true, mlang: "en", intg: {}, tab: "activity", live: false, q: [], qBusy: false, spoken: new Set() };
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const rs = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");
const tm = (iso) => { try { return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }); } catch (_) { return ""; } };
const dayTm = (iso) => { try { const d = new Date(iso); return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }) + ", " + tm(iso); } catch (_) { return ""; } };
const post = (url, body) => fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}) }).then((r) => r.json()).catch(() => ({}));
const icons = () => window.lucide && lucide.createIcons({ attrs: { "stroke-width": 1.9 } });
const first = (t, n = 160) => { const s = String(t || "").replace(/^[^\w₹"“]+/u, "").split(/(?<=[.!?])\s/)[0]; return s.length > n ? s.slice(0, n - 1) + "…" : s; };
const secs = (a, b) => Math.max(0, Math.round((new Date(b) - new Date(a)) / 1000));
const dur = (s) => s < 60 ? `${s} s` : s < 3600 ? `${Math.round(s / 60)} min` : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} days`;
const SOURCE = { switch: "UPI switch", ledger: "Billing app", refund: "Refunds", payout: "Payouts", policy: "Rules & SOP", customer: "Customer" };
const KIND = { payment_claim: "Payment claim", duplicate: "Charged twice", settlement: "Missing payout", freeze: "Bank freeze", scam: "Scam call", account_change: "Payout account",
  question: "Question", chargeback: "Chargeback", live_check: "Live Paytm order", unknown: "Message" };

// ---------------------------------------------------------------- one plain-language line per real engine step
function line(s, inc) {
  const who = (inc.customer && inc.customer.name) || "A customer";
  switch (s.kind) {
    case "intake":
      if (s.engine === "dispute-monitor") return { i: "timer", t: "warn", h: "A chargeback clock just started. Nobody was watching it.", d: s.text, src: "Dispute desk" };
      if (s.engine === "psp-monitor") return { i: "ban", t: "warn", h: "Meena's bank refused her own payment.", d: s.text, src: "Her UPI payments" };
      if (s.engine === "payout-monitor") return { i: "undo-2", t: "warn", h: "Meena's bank sent her payout back.", d: s.text, src: "Payouts" };
      if (s.sender === "monitor") return { i: "radar", t: "warn", h: "Paytm's message never reached the billing app.", d: s.text, src: "Billing app" };
      if (s.sender === "customer") return { i: "message-circle", t: "", h: `${who}: “${first(s.text, 110)}”`, d: "", src: "WhatsApp" };
      return { i: "message-circle", t: "", h: `Meena: “${first(s.text, 110)}”`, d: "", src: "Her app" };
    case "think": return { i: "sparkles", t: "muted", h: first(s.text), d: "" };
    case "tool": return { i: "search", t: "muted", h: TVERB[s.tool] || s.tool.replace(/_/g, " "), d: s.summary || "", src: SOURCE[T2N[s.tool]] || "" , live: /LIVE/i.test(s.summary || "") };
    case "evidence": return { i: "scale", t: s.tone === "bad" ? "bad" : s.tone === "good" ? "ok" : "warn", h: s.verdict, d: inc.decisive ? inc.decisive.text : "" };
    case "policy": return s.verdict === "DENY" ? { i: "shield-x", t: "bad", h: `Stopped itself from ${DENY_NAMES[s.action] || s.action.replace(/_/g, " ")}.`, d: s.reason, src: "Rules & SOP" } : null;
    case "approval": return { i: "key-round", t: "warn", h: `Asked ${s.approvers.map((a) => APPROVER[a] || a).join(" and ")} before it ${VERB[s.action] ? "can " + VERB[s.action] : s.action.replace(/_/g, " ")}.`, d: s.reason };
    case "action": {
      if (s.action === "notify_merchant") return { i: "bell-ring", t: "", h: "Told Meena: " + first((s.args.text || "").replace(/:?\s*Payment T\d{8,}/, "").replace(/\s*\(UPI Ref \d+\)/, ""), 130), d: s.args.speak ? "Also spoken aloud on her Soundbox" : "", src: "Her app" };
      if (s.action === "resolve_incident") return { i: "circle-check-big", t: "ok", h: "Case closed.", d: s.args.outcome };
      if (s.action === "schedule_followup") return { i: "alarm-clock", t: "muted", h: "Will come back to this on its own.", d: (s.result || {}).summary || s.args.purpose };
      return { i: "zap", t: "ok", h: ACTION_NAMES[s.action] || s.action.replace(/_/g, " "), d: (s.result || {}).summary || "", src: SOURCE[A2N[s.action]] || "" };
    }
    case "verify": return s.ok ? { i: "badge-check", t: "ok", h: "Checked again at the source. It worked.", d: s.check } : { i: "triangle-alert", t: "bad", h: "Re-check failed.", d: s.check };
    case "followup": return { i: "alarm-clock", t: "", h: "Back on its own.", d: s.purpose + (s.via ? ` (${s.via})` : "") };
  }
  return null;
}
const TONE = { ok: "bg-ok-50 text-ok", warn: "bg-warn-50 text-warn", bad: "bg-bad-50 text-bad", muted: "bg-page text-ink-3", "": "bg-sky-50 text-navy-2" };


// ---------------------------------------------------------------- the case story: one real case, end to end, from the engine's step log
const SYS = {
  get_settlement_status: "Settlement engine", get_money_position: "Settlement engine", get_bank_signal: "Settlement engine", get_risk_signals: "Paytm Risk",
  get_disputes: "Dispute desk", lookup_transaction: "UPI switch", get_payment_status: "UPI switch", find_duplicate_payments: "UPI switch", check_sale_pattern: "UPI switch",
  paytm_order_status: "Paytm PG API (live)", get_merchant_ledger: "Billing app", get_refund_status: "Refund service", get_own_payment_declines: "Her UPI payments (PSP)",
  read_document: "Document reader", parse_notice: "Document reader", read_screenshot: "Document reader", route_sop: "Government SOP", get_sop_clocks: "Government SOP", ask_sop: "Government SOP",
  get_incident_policy: "Policy engine", get_soundbox_log: "Soundbox",
  notify_merchant: "Merchant app + Soundbox", request_settlement_hold: "Settlement engine", release_settlement_hold: "Settlement engine", validate_settlement_account: "Settlement engine",
  change_settlement_account: "Settlement engine", generate_evidence_pack: "Evidence signer", issue_live_pack: "Evidence signer", draft_lien_request: "Letters", draft_escalation: "Letters",
  prepare_pa_upload: "Nodal queue", create_support_case: "Support CRM", record_case_event: "Case record", resolve_incident: "Case record", schedule_followup: "Scheduler",
  submit_dispute_response: "Dispute desk", accept_chargeback: "Dispute desk", reconcile_payment: "Billing app", initiate_refund: "Refund service",
  send_customer_update_simulated: "WhatsApp", issue_verified_receipt: "WhatsApp", request_payment: "WhatsApp", escalate_to_human: "Human queue", replay_soundbox: "Soundbox",
};
const PHASE = {
  notice: ["Noticed", "radar", "bg-sky-50 text-navy-2"], understand: ["Understood", "search", "bg-page text-ink-2"], decide: ["Decided", "scale", "bg-vi-50 text-vi"],
  blocked: ["Stopped itself", "shield-x", "bg-bad-50 text-bad"], act: ["Acted", "zap", "bg-ok-50 text-ok"], verify: ["Verified", "badge-check", "bg-ok-50 text-ok"],
  human: ["Human", "user-check", "bg-warn-50 text-warn"], escalate: ["Escalated", "life-buoy", "bg-bad-50 text-bad"], follow: ["Follow-up", "alarm-clock", "bg-sky-50 text-navy-2"],
};
const C = { id: null, inc: null, steps: [], filter: "all", list: [] };

function phaseOf(s) {
  if (s.kind === "intake") return s.sender === "merchant" || s.sender === "customer" ? "notice" : "notice";
  if (s.kind === "tool") return "understand";
  if (s.kind === "think" || s.kind === "evidence") return "decide";
  if (s.kind === "policy") return s.verdict === "DENY" ? "blocked" : "decide";
  if (s.kind === "approval" || s.kind === "approval_result") return "human";
  if (s.kind === "action") return s.action === "escalate_to_human" ? "escalate" : "act";
  if (s.kind === "verify") return "verify";
  if (s.kind === "followup") return "follow";
  return "understand";
}
function actorOf(s) {
  if (s.kind === "approval_result") return s.approver === "merchant" ? ["Meena", "bg-navy-2 text-white"] : ["Paytm Risk", "bg-warn text-white"];
  if (s.kind === "intake" && s.sender === "merchant") return ["Meena", "bg-navy-2 text-white"];
  if (s.kind === "intake" && s.sender === "customer") return [(C.inc.customer && C.inc.customer.name) || "Customer", "bg-ink-2 text-white"];
  if (s.kind === "intake" && s.sender && !["monitor", "merchant", "customer"].includes(s.sender)) return [s.sender.charAt(0).toUpperCase() + s.sender.slice(1) + " (sim)", "bg-ink-3 text-white"];
  return ["Kavach", "bg-sky text-white"];
}
function rowText(s) {
  if (s.kind === "policy") return s.verdict === "DENY" ? { h: `Stopped itself from ${DENY_NAMES[s.action] || s.action.replace(/_/g, " ")}.`, d: `${s.rule || ""} ${s.reason || ""}`.trim() }
    : { h: `Rule check passed: ${ACTION_NAMES[s.action] || s.action.replace(/_/g, " ")}`, d: `${s.rule ? s.rule + ": " : ""}${s.reason || ""}${s.approvers && s.approvers.length ? ` · needs ${s.approvers.map((a) => APPROVER[a] || a).join(" + ")}` : ""}` };
  if (s.kind === "approval_result") return { h: `${s.approver === "merchant" ? "Meena" : "Paytm Risk"} ${s.approved ? "approved" : "declined"}.`, d: "" };
  const r = line(s, C.inc); return r ? { h: r.h, d: r.d } : null;
}
function systemOf(s) {
  if (s.kind === "tool") return SYS[s.tool] || "";
  if (s.kind === "action" || s.kind === "verify") return SYS[s.action] || "";
  if (s.kind === "intake") return { "payout-monitor": "Settlement engine", "psp-monitor": "Her UPI payments (PSP)", "dispute-monitor": "Dispute desk" }[s.engine] || (s.sender === "monitor" ? "Billing app" : "Merchant app");
  if (s.kind === "approval_result") return s.approver === "merchant" ? "Merchant app" : "Risk desk";
  if (s.kind === "approval") return "Risk desk";
  return "";
}

function metrics() {
  const st = C.steps, inc = C.inc;
  const intake = st.find((s) => s.kind === "intake"), told = st.find((s) => s.kind === "action" && s.action === "notify_merchant");
  const actions = st.filter((s) => s.kind === "action" && !["notify_merchant", "resolve_incident", "schedule_followup"].includes(s.action));
  const asks = st.filter((s) => s.kind === "approval").length;
  const sys = new Set(st.map(systemOf).filter((x) => x && !/Merchant app|Risk desk/.test(x)));
  const denies = st.filter((s) => s.kind === "policy" && s.verdict === "DENY").length;
  const verified = st.filter((s) => s.kind === "verify" && s.ok).length;
  const humanAt = st.filter((s) => s.kind === "approval_result").length;
  const end = inc.status === "resolved" ? inc.updated_at : (st[st.length - 1] || {}).at;
  const span = intake && end ? secs(intake.at, end) : 0;
  const tile = (k, v, sub, tone = "") => `<div class="card p-4"><p class="text-[11.5px] text-ink-3 leading-tight">${k}</p><p class="mt-1.5 num text-[21px] font-semibold leading-none ${tone}">${v}</p>${sub ? `<p class="mt-1 text-[11px] text-ink-3 leading-tight line-clamp-2">${sub}</p>` : ""}</div>`;
  $("#metrics").innerHTML = [
    tile("Found", intake ? tm(intake.at) : "—", intake && intake.sender === "monitor" ? "by Kavach, before anyone asked" : "reported by the merchant"),
    tile("Merchant told in", told && intake ? dur(secs(intake.at, told.at)) : "—", "in her language", "text-ok"),
    tile(inc.status === "resolved" ? "Resolved in" : inc.facts && inc.facts.released ? "Money back in" : "Open for", span ? dur(span) : "—", inc.status === "resolved" ? "verified at the source" : inc.facts && inc.facts.released ? "bank and officer simulated" : "Kavach still on it"),
    tile("Systems used", String(sys.size), "read and written"),
    tile("Actions taken", String(actions.length), `${verified} re-checked at the source`),
    tile("Needed a human", String(asks), asks ? `${humanAt} decision${humanAt === 1 ? "" : "s"} made` : "handled alone", asks ? "text-warn" : ""),
    tile("Unsafe steps blocked", String(denies), "by its own rules", denies ? "text-bad" : ""),
    tile(inc.money && inc.money.amount ? "Money protected" : "Amount", inc.money && inc.money.amount ? rs(inc.money.amount) : "—", inc.money ? esc(String(inc.money.label || "").split(/[;·]/)[0]) : ""),
  ].join("");
}
function sidebar() {
  const st = C.steps;
  const counts = {};
  st.forEach((s) => { const x = systemOf(s); if (x) counts[x] = (counts[x] || 0) + 1; });
  $("#systems").innerHTML = Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<div class="flex items-center justify-between text-[13.5px] py-1"><span class="flex items-center gap-2 ${/live/.test(k) ? "text-ok font-medium" : "text-ink-2"}"><span class="size-1.5 rounded-full ${/live/.test(k) ? "bg-ok" : "bg-navy-2/40"}"></span>${esc(k)}</span><span class="num text-ink-3 text-[12px]">${n}</span></div>`).join("") || `<p class="text-ink-3 text-[13px]">—</p>`;
  const hum = [];
  st.forEach((s) => {
    if (s.kind === "approval") hum.push(`<div class="text-[13px]"><p class="font-medium">Asked ${esc(s.approvers.map((a) => APPROVER[a] || a).join(" + "))}</p><p class="text-ink-3">${esc(VERB[s.action] || s.action.replace(/_/g, " "))} · ${tm(s.at)}</p></div>`);
    if (s.kind === "approval_result") hum.push(`<div class="text-[13px] flex items-center gap-2"><span class="size-5 rounded-full grid place-items-center ${s.approved ? "bg-ok-50 text-ok" : "bg-bad-50 text-bad"}"><i data-lucide="${s.approved ? "check" : "x"}" class="size-3"></i></span><span><b class="font-medium">${s.approver === "merchant" ? "Meena" : "Paytm Risk"}</b> ${s.approved ? "approved" : "declined"} · ${tm(s.at)}</span></div>`);
  });
  $("#humans").innerHTML = hum.join("") || `<p class="text-[13px] text-ink-2">No human needed. Nothing in this case moved money.</p>`;
  const esc2 = st.filter((s) => s.kind === "action" && s.action === "escalate_to_human");
  $("#esc").innerHTML = esc2.length ? esc2.map((s) => `<p class="text-[13.5px]"><b class="font-medium text-bad">Yes.</b> ${esc(((s.args || {}).queue) || "Human queue")}: ${esc(((s.args || {}).summary) || "")}</p>`).join("")
    : `<p class="text-[13.5px] text-ink-2"><b class="font-medium text-ok">No.</b> Kavach handled it, asking people only for decisions that move money.</p>`;
}
function timeline() {
  const ol = $("#tl"); let day = "";
  const rows = C.steps.map((s) => ({ s, ph: phaseOf(s) })).filter(({ ph }) => C.filter === "all" || C.filter === ph);
  ol.innerHTML = rows.map(({ s, ph }) => {
    const t = rowText(s); if (!t) return "";
    const d = new Date(s.at).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    const head = d !== day ? `<li class="pt-3 pb-1 first:pt-0"><span class="label">${(day = d)}</span></li>` : "";
    const [pl, pi, pc] = PHASE[ph]; const [an, ac] = actorOf(s); const sys = systemOf(s);
    return head + `<li class="row-in grid grid-cols-[52px_118px_1fr] gap-3 py-2.5 border-t border-line/70 first:border-0">
      <span class="font-mono text-[11.5px] text-ink-3 num pt-1">${tm(s.at)}</span>
      <span class="pt-0.5"><span class="inline-flex items-center gap-1.5 h-6 px-2 rounded-lg text-[11.5px] font-semibold ${pc}"><i data-lucide="${pi}" class="size-3.5"></i>${pl}</span></span>
      <div class="min-w-0"><div class="flex items-start gap-2"><span class="shrink-0 mt-0.5 h-5 px-1.5 rounded-md text-[10.5px] font-semibold grid place-items-center ${ac}">${esc(an)}</span><p class="text-[14px] leading-snug ${ph === "understand" ? "text-ink-2" : "font-medium"}">${esc(t.h)}</p></div>
        ${t.d ? `<p class="mt-0.5 ml-0 text-[12.5px] text-ink-3 leading-snug line-clamp-2">${esc(t.d)}</p>` : ""}${sys ? `<p class="mt-1 text-[10.5px] font-semibold uppercase tracking-[0.08em] ${/live/.test(sys) ? "text-ok" : "text-ink-3/90"}">${esc(sys)}</p>` : ""}</div></li>`;
  }).join("");
  $("#count").textContent = `${C.steps.length} steps`;
}
function filters() {
  const n = {}; C.steps.forEach((s) => { const p = phaseOf(s); n[p] = (n[p] || 0) + 1; });
  $("#filters").innerHTML = [`<button class="flt ${C.filter === "all" ? "on" : ""}" data-f="all">All ${C.steps.length}</button>`].concat(Object.keys(PHASE).filter((p) => n[p]).map((p) => `<button class="flt ${C.filter === p ? "on" : ""}" data-f="${p}">${PHASE[p][0]} ${n[p]}</button>`)).join("");
  $$("[data-f]").forEach((b) => b.onclick = () => { C.filter = b.dataset.f; render(); });
}
function render() {
  if (!C.inc) { $("#empty").hidden = false; $("#wrap").hidden = true; return; }
  $("#empty").hidden = true; $("#wrap").hidden = false;
  const inc = C.inc;
  $("#meta").textContent = `${KIND[inc.kind] || inc.kind} · ${inc.id} · Meena Kirana Store, Lucknow`;
  $("#title").textContent = inc.headline || inc.title;
  $("#sub").textContent = inc.outcome || (inc.plan && inc.plan.length ? "Plan: " + inc.plan.map((p) => (p.state === "done" ? "✓ " : "") + (p.text || p.step || p)).join("  →  ") : "");
  const resolved = inc.status === "resolved", waiting = inc.pending && inc.pending.approvers && inc.pending.approvers.length;
  const st = $("#status"); st.className = "inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-[12.5px] font-semibold " + (resolved ? "bg-ok-50 text-ok" : waiting ? "bg-warn-50 text-warn" : "bg-sky-50 text-navy-2");
  st.textContent = resolved ? "Resolved" : waiting ? "Waiting for " + inc.pending.approvers.map((a) => APPROVER[a] || a).join(" + ")
    : inc.status === "watching" ? "Watching the deadlines" : inc.status === "waiting_merchant" ? "Waiting for Meena" : inc.status === "with_human" ? "With a person" : "Kavach working";
  metrics(); sidebar(); filters(); timeline();
  if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.9 } });
}
async function load() {
  const st = await fetch("/api/state").then((r) => r.json());
  C.list = st.incidents.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  const want = location.pathname.split("/")[2];
  C.id = want && C.list.some((i) => i.id === want) ? want : C.id && C.list.some((i) => i.id === C.id) ? C.id : (C.list.find((i) => i.kind === "freeze") || C.list[0] || {}).id;
  C.inc = C.list.find((i) => i.id === C.id) || null;
  C.steps = st.steps.filter((s) => s.incident === C.id);
  $("#pick").innerHTML = C.list.map((i) => `<option value="${esc(i.id)}" ${i.id === C.id ? "selected" : ""}>${esc(i.id)} · ${esc(KIND[i.kind] || i.kind)}</option>`).join("");
  render();
}
$("#pick").onchange = (e) => { history.replaceState(null, "", "/case/" + e.target.value); C.id = e.target.value; load(); };
let lt = null;
const es = new EventSource("/api/stream");
es.onmessage = (m) => { const ev = JSON.parse(m.data); if (["step", "incident", "reset"].includes(ev.type)) { clearTimeout(lt); lt = setTimeout(load, 300); } };
load();
