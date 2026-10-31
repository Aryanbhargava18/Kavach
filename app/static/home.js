"use strict";
const ONLY = { "/desk": "only-desk", "/soundbox": "only-sound" }[location.pathname];
if (ONLY) document.documentElement.classList.add(ONLY);
/* Kavach home: the three real surfaces (Meena's app, her Soundbox, Paytm's Risk & Ops desk) on one live engine. Demo controls live in a separate dock. */
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

function srcRow(name, c, live) {
  if (!c || c.status == null) return "";
  const v = c.amount != null ? `${String(c.status).toLowerCase()} · ${rs(c.amount)}` : String(c.status).toLowerCase();
  const tone = /fail|return|missing|unpaid|frozen|declin/i.test(c.status) ? "text-bad" : /success|paid|settled|credited/i.test(c.status) ? "text-ok" : "text-ink-2";
  return `<div class="flex items-center justify-between gap-3 py-2.5 border-t first:border-0 border-line"><span class="text-[13.5px] text-ink-2">${esc(name)}</span><span class="text-[13.5px] font-medium ${tone}">${esc(v)}</span><span class="text-[10px] font-semibold tracking-[0.1em] uppercase ${live ? "text-ok" : "text-ink-3"}">${live ? "Live" : "Simulated"}</span></div>`;
}
function factCard(title, value, body, tone = "") {
  const ring = { ok: "ring-ok/25 bg-ok-50/50", warn: "ring-warn/25 bg-warn-50/60", bad: "ring-bad/20 bg-bad-50/60", "": "ring-line bg-white" }[tone];
  return `<div class="rounded-2xl ring-1 ${ring} p-4"><div class="flex items-baseline justify-between gap-3"><b class="text-[14px] font-semibold">${title}</b>${value ? `<span class="num text-[20px] font-semibold tracking-tight">${value}</span>` : ""}</div>${body ? `<div class="mt-1.5 text-[13px] text-ink-2 leading-relaxed">${body}</div>` : ""}</div>`;
}
// ---------------------------------------------------------------- voice: the Soundbox speaks Meena's language
let voices = []; if ("speechSynthesis" in window) { const lv = () => { voices = speechSynthesis.getVoices(); }; lv(); speechSynthesis.onvoiceschanged = lv; }
function speak(s, override) {
  if (!S.sound || !S.live || S.spoken.has(s.incident + ":" + s.n)) return;
  S.spoken.add(s.incident + ":" + s.n);
  const hi = S.mlang === "hi", text = override || (hi ? s.args.speak : (s.args.speak_en || s.args.speak));
  if (!text) return;
  if (S.intg.sarvam) { new Audio(`/api/tts?voice=kavach&lang=${hi ? "hi-IN" : "en-IN"}&text=${encodeURIComponent(text)}`).play().catch(() => {}); return; }
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  const v = hi ? voices.find((x) => x.lang.startsWith("hi")) : (voices.find((x) => x.lang === "en-IN") || voices.find((x) => x.lang.startsWith("en")));
  if (v) u.voice = v; u.lang = hi ? "hi-IN" : "en-IN";
  speechSynthesis.speak(u);
}

// ---------------------------------------------------------------- Paytm's desk: the case as Paytm's people would work it
function render() {
  const list = Object.values(S.incidents).sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  const inc = S.incidents[S.sel];
  $("#empty").hidden = !!inc; $("#case").hidden = !inc;
  const q = $("#queue"); q.hidden = list.length < 2;
  q.innerHTML = list.map((i) => `<button data-sel="${esc(i.id)}" class="shrink-0 h-8 px-3 rounded-lg text-[12.5px] font-medium flex items-center gap-2 transition ${i.id === S.sel ? "bg-navy-2 text-white" : "text-ink-2 hover:bg-page"}">
    <span class="size-1.5 rounded-full ${i.status === "resolved" ? "bg-ok" : i.pending ? "bg-warn" : "bg-sky"}"></span>${esc(KIND[i.kind] || i.kind)}</button>`).join("");
  $$("[data-sel]", q).forEach((b) => b.onclick = () => { S.sel = b.dataset.sel; $("#case").dataset.inc = ""; render(); });
  renderDock(inc);
  if (inc) renderCase(inc);
  icons();
}
function statusOf(inc) {
  if (inc.pending && inc.pending.approvers && inc.pending.approvers.length) return ["Needs approval", "bg-warn-50 text-warn", "bg-warn"];
  if (inc.status === "resolved") return ["Resolved", "bg-ok-50 text-ok", "bg-ok"];
  if (inc.status === "refused") return ["Stopped", "bg-bad-50 text-bad", "bg-bad"];
  if ((S.followups || []).some((f) => f.incident === inc.id && !f.fired && !f.cancelled) && inc.status !== "investigating") return ["Monitoring", "bg-sky-50 text-navy-2", "bg-sky"];
  return ["Kavach working", "bg-sky-50 text-navy-2", "bg-sky"];
}
function sla(inc, st) {
  const intake = st.find((s) => s.kind === "intake"), told = st.find((s) => s.kind === "action" && s.action === "notify_merchant");
  const cells = [
    [intake && intake.sender === "monitor" ? "Found by Kavach" : "Reported", intake ? tm(intake.at) : "—"],
    ["Merchant informed", told && intake ? `+${dur(secs(intake.at, told.at))}` : "—"],
    [inc.kind === "freeze" && (inc.facts || {}).disputed_txn ? "Disputed" : "Amount", inc.money && inc.money.amount ? rs(inc.money.amount) : "—"],
    ["Checked at source", String(st.filter((s) => s.kind === "tool").length)],
  ];
  const blocked = st.filter((s) => s.kind === "policy" && s.verdict === "DENY").length;
  if (blocked) cells.push(["Unsafe steps blocked", String(blocked)]);
  return `<dl class="grid ${cells.length === 5 ? "grid-cols-5" : "grid-cols-4"} border-y border-line divide-x divide-line">${cells.map(([k, v]) => `<div class="px-4 py-3"><dt class="text-[11px] text-ink-3">${esc(k)}</dt><dd class="mt-0.5 text-[14px] font-semibold num truncate">${esc(v)}</dd></div>`).join("")}</dl>`;
}
function decision(inc) {
  const p = inc.pending;
  if (!p || !p.approvers || !p.approvers.length) return "";
  const verb = VERB[p.action] || p.action.replace(/_/g, " ");
  if (p.approvers.includes("merchant"))
    return `<div class="mx-6 mt-5 rounded-2xl bg-page p-4 flex items-center gap-3"><span class="size-9 rounded-xl bg-white text-ink-2 grid place-items-center ring-1 ring-line"><i data-lucide="smartphone" class="size-4"></i></span>
      <p class="text-[14px] text-ink-2"><b class="text-ink font-semibold">Waiting for Meena</b> to approve in her app before Kavach can ${esc(verb)}.${p.approvers.includes("paytm_ops") ? " Then it comes to you." : ""}</p></div>`;
  return `<div class="mx-6 mt-5 rounded-2xl ring-1 ring-warn/30 bg-warn-50/70 p-5">
    <p class="text-[11px] font-semibold uppercase tracking-[0.14em] text-warn">Your approval</p>
    <p class="mt-1.5 text-[17px] font-semibold tracking-tight">Kavach wants to ${esc(verb)}.</p>
    <p class="mt-1 text-[13.5px] text-ink-2 leading-relaxed">${esc(p.ask || "")}${p.approved && p.approved.length ? ` Meena has already approved.` : ""}</p>
    <div class="mt-4 flex gap-2"><button data-approve="yes" class="h-10 px-5 rounded-xl bg-navy-2 text-white text-[14px] font-semibold hover:bg-navy active:scale-[.98] transition flex items-center gap-2"><i data-lucide="check" class="size-4"></i>Approve</button>
    <button data-approve="no" class="h-10 px-5 rounded-xl bg-white ring-1 ring-line text-[14px] font-semibold text-ink-2 hover:ring-ink-3 transition">Decline</button></div></div>`;
}
function evidence(inc) {
  const f = inc.facts || {}, rec = inc.recon || {}, parts = [];
  if (inc.status === "resolved" && inc.outcome) parts.push(factCard("Outcome", "", esc(inc.outcome), "ok"));
  if (f.released) parts.push(factCard("Money released to her account", rs(f.released.released), `After the officer's decision, a ₹1 check on her account and your approval. Only the disputed amount stays held.`, "ok"));
  const back = rec.settlement && rec.settlement.status === "RETURNED" ? rec.settlement : null;
  if (back && !f.released) parts.push(factCard(`Payout ${esc(back.ref || "")} returned by her bank`, rs(back.amount), `${f.proactive ? "Found by Kavach before anyone complained. " : ""}${S.world && S.world.settlement_config && S.world.settlement_config.paused ? "New payouts held in Paytm's settlement balance. Nothing went to another account." : "Back in Paytm's settlement balance."}`, "bad"));
  if (rec.own) parts.push(factCard(`Her payment to ${esc(rec.own.note || "a supplier")} declined`, rs(rec.own.amount), `Bank code ${esc(rec.own.ref || "YE")}: credits land, but she can't pay out.`, "bad"));
  if (inc.decisive && inc.decisive.label === "Why Kavach held back") parts.push(factCard("Risk signals: details withheld from merchant", "", `${esc(inc.decisive.text)}. She got only a neutral message. Your EDD decides; this is not a verdict on her.`, "warn"));
  const disputed = f.disputed_txn && rec.switch && rec.switch.amount, locked = f.locked_stated;
  if (disputed && locked && locked > disputed) {
    const pct = Math.max(1.5, Math.min(100, (disputed / locked) * 100));
    parts.push(factCard("Disputed vs frozen", `${Math.round(locked / disputed)}×`, `<div class="h-2 rounded-full bg-warn/15 overflow-hidden my-2"><i class="block h-full rounded-full bg-navy-2" style="width:${pct}%"></i></div><b class="text-ink">${rs(disputed)}</b> disputed in Paytm's record; <b class="text-ink">${rs(locked)}</b> frozen. Kavach drafted a request to hold only the disputed amount.`, "warn"));
  }
  if (f.lien_request) parts.push(factCard("Request to limit the hold, signed by Meena", esc(f.lien_request.disputed_text || ""), `Hold only the disputed amount; tell her the reason, officer and removal process. Cites ${f.lien_request.basis.length} rules.`));
  if (f.pa_upload) parts.push(factCard("Your SOP 9.5(ii) row, drafted", "", `UTR …${esc(String(f.pa_upload.row.reported_utr).slice(-4))} is in the nodal queue (${esc(f.pa_upload.ticket_id)}) for an officer. Kavach never uploads.`));
  if (f.pack) parts.push(factCard("Signed evidence pack", "", `Change one digit and verification fails. <span class="mt-2 flex gap-3"><a class="font-semibold text-navy-2 hover:underline" href="/pack/${esc(f.pack.token)}.pdf" target="_blank" rel="noopener">Open PDF</a><a class="font-semibold text-navy-2 hover:underline" href="/verify/${esc(f.pack.token)}" target="_blank" rel="noopener">Verify</a></span>`));
  const srcs = srcRow("UPI switch", rec.switch, rec.switch && rec.switch.live) + srcRow("Billing app", rec.ledger) + srcRow("Refunds", rec.refund) + srcRow("Payouts", rec.settlement || rec.bank) + srcRow(/notice/i.test((rec.claim || {}).label || "") ? "Police notice says" : "Screenshot says", rec.claim);
  if (srcs) parts.push(`<div class="rounded-2xl ring-1 ring-line px-4 pt-3 pb-1"><p class="label mb-1">Source of truth</p>${srcs}</div>`);
  const fu = (S.followups || []).filter((x) => x.incident === inc.id && !x.fired && !x.cancelled);
  if (fu.length) parts.push(`<div class="rounded-2xl ring-1 ring-line p-4 pt-3"><p class="label mb-2">Kavach comes back on its own</p>${fu.slice(0, 4).map((x) => `<div class="flex justify-between gap-3 py-1 text-[13.5px]"><span class="text-ink-2">${esc(x.purpose)}</span><span class="font-mono text-[12px] text-ink-3 shrink-0">${dayTm(x.due)}</span></div>`).join("")}</div>`);
  return parts.join("");
}
function logRows(inc, from) {
  return (S.steps[inc.id] || []).slice(from).map((s) => {
    const r = line(s, inc); if (!r) return "";
    return `<li class="row-in flex gap-3 py-2"><span class="mt-0.5 size-7 shrink-0 rounded-lg grid place-items-center ${TONE[r.t] || TONE[""]}"><i data-lucide="${r.i}" class="size-3.5"></i></span>
      <div class="min-w-0 flex-1"><p class="text-[13.5px] leading-snug ${r.t === "muted" ? "text-ink-2" : "text-ink font-medium"}">${esc(r.h)}</p>${r.d ? `<p class="text-[12.5px] text-ink-3 leading-snug line-clamp-2">${esc(r.d)}</p>` : ""}</div>
      <span class="shrink-0 font-mono text-[11px] text-ink-3 num pt-0.5">${tm(s.at)}${r.src ? `<br><span class="font-sans font-semibold uppercase tracking-[0.06em] text-[9.5px] ${r.live ? "text-ok" : ""}">${esc(r.src)}${r.live ? " · live" : ""}</span>` : ""}</span></li>`;
  }).join("");
}
function renderCase(inc) {
  const box = $("#case"), st = S.steps[inc.id] || [];
  const [stxt, scls, sdot] = statusOf(inc);
  const top = `<div class="px-6 pt-5 pb-4"><div class="flex items-center gap-2"><span class="text-[12px] font-medium text-ink-3">${esc(KIND[inc.kind] || inc.kind)} · ${esc(inc.id)}</span><span class="ml-auto inline-flex items-center gap-1.5 h-6 px-2.5 rounded-full text-[11.5px] font-semibold ${scls}"><i class="size-1.5 rounded-full ${sdot}"></i>${stxt}</span></div>
    <h2 class="mt-1.5 text-[21px] leading-tight font-semibold tracking-[-0.02em]">${esc(inc.headline || inc.title || "")}</h2><a href="/case/${esc(inc.id)}" target="_blank" rel="noopener" class="mt-2 inline-flex items-center gap-1 text-[13px] font-semibold text-navy-2 hover:underline">Open the full case story<i data-lucide="arrow-up-right" class="size-3.5"></i></a><p class="mt-1 text-[13.5px] text-ink-2">Meena Kirana Store · MEENAKIRANA0417 · Lucknow</p></div>`;
  const sig = [inc.id, stxt, inc.headline, JSON.stringify(inc.pending), JSON.stringify(inc.facts), JSON.stringify(inc.recon), (S.followups || []).length, S.world && S.world.settlement_config && S.world.settlement_config.paused].join("|");
  if (box.dataset.sig !== sig) {
    box.dataset.sig = sig;
    const open = box.querySelector("details") ? box.querySelector("details").open : true;
    box.innerHTML = top + sla(inc, st) + decision(inc) + `<div class="px-6 py-5 grid gap-3">${evidence(inc)}</div>`
      + `<details class="px-6 pb-6" ${open ? "open" : ""}><summary class="label cursor-pointer select-none py-2">Kavach's log · <span id="logn">${st.length}</span> steps</summary><ol id="log" class="mt-1">${logRows(inc, 0)}</ol></details>`;
    box.dataset.n = String(st.length);
    $$("[data-approve]", box).forEach((b) => b.onclick = () => { $$("[data-approve]", box).forEach((x) => x.disabled = true); post("/api/approve", { incident_id: inc.id, approver: "paytm_ops", yes: b.dataset.approve === "yes" }); });
  } else if (Number(box.dataset.n) < st.length) {
    $("#log").insertAdjacentHTML("beforeend", logRows(inc, Number(box.dataset.n)));
    $("#logn").textContent = st.length; box.dataset.n = String(st.length);
    const dl = box.querySelector("dl"); if (dl) dl.outerHTML = sla(inc, st);
  }
}

// ---------------------------------------------------------------- presenter dock: time controls only appear when time is the next thing
function skipAction(inc) {
  const w = S.world;
  const pend = ((w && w.transactions) || []).find((t) => t.status === "PENDING");
  if (pend) return [`Bank confirms ${rs(pend.amount)}`, () => post("/api/world/force", { txn_id: pend.txn_id, status: "SUCCESS" })];
  if (Object.values(S.incidents).some((x) => x.pending)) return null;
  const fus = (S.followups || []).filter((f) => !f.fired && !f.cancelled && S.incidents[f.incident] && S.incidents[f.incident].status !== "resolved");
  if (inc && inc.kind === "freeze" && !(inc.facts || {}).released && (S.steps[inc.id] || []).some((s) => s.kind === "action" && s.action === "record_case_event"))
    return ["12 days later", () => post("/api/clock/skip-days", { days: 13 })];
  if (fus.some((f) => /payout/i.test(f.purpose))) return ["Next morning's payout", () => post("/api/clock/skip-to-payout")];
  const mine = inc ? fus.filter((f) => f.incident === inc.id) : [];
  const d = mine.find((f) => /^Day [57]/.test(f.purpose));
  if (d && w) return [d.purpose.slice(0, 5), () => post("/api/clock/advance", { seconds: Math.round(Math.max(60, (new Date(d.due) - new Date(w.now)) / 1000 + 60)) })];
  return null;
}
function renderDock(inc) {
  const a = skipAction(inc), b = $("#skip");
  b.hidden = !a; S.skip = a && a[1];
  if (a) { $("#skip-t").textContent = a[0]; b.disabled = false; }
}

// ---------------------------------------------------------------- the Soundbox
function lcd(text, alert, ms) {
  const l = $("#lcd"); l.textContent = text; l.classList.toggle("alert", !!alert);
  clearTimeout(S.lt); if (ms) S.lt = setTimeout(idleLcd, ms);
}
function idleLcd() {   // a real Soundbox shows the last payment it announced
  const ok = ((S.world && S.world.transactions) || []).filter((t) => t.status === "SUCCESS").sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))[0];
  lcd(ok ? "+₹ " + Number(ok.amount).toLocaleString("en-IN") : "READY");
}
function heard(text, hi) {
  const li = document.createElement("li");
  li.className = "row-in rounded-2xl bg-white ring-1 ring-black/[0.05] px-3.5 py-2.5 text-[13px] leading-snug text-ink shadow-sm";
  li.lang = hi ? "hi" : "en"; li.textContent = "“" + text + "”";
  const ol = $("#heard"); ol.prepend(li); while (ol.children.length > 3) ol.lastChild.remove();
  $("#heard-t").hidden = false;
}
// The Soundbox is a loudspeaker on the shop counter: customers hear it. Private trouble (a freeze, a dispute, a Risk review)
// is never announced there; the counter says only that a message is waiting, and the details stay on her phone.
const PRIVATE = new Set(["freeze", "chargeback", "scam", "account_change"]);
const DISCREET = { en: "Meena ji, an important message from Paytm is waiting in your app.", hi: "मीना जी, पेटीएम का एक ज़रूरी संदेश आपके ऐप में है।" };
function soundbox(s) {
  const hi = S.mlang === "hi", inc = S.incidents[s.incident] || {};
  const priv = PRIVATE.has(inc.kind);
  const text = priv ? DISCREET[hi ? "hi" : "en"] : (hi ? s.args.speak : (s.args.speak_en || s.args.speak));
  if (!text) return;
  if (priv && S.lastPrivate === s.incident && Date.now() - (S.lastPrivateAt || 0) < 20000) { speak(s, " "); return; }   // one discreet chime per burst, not one per message
  if (priv) { S.lastPrivate = s.incident; S.lastPrivateAt = Date.now(); }
  heard(text, hi);
  const sb = $("#sbx"); sb.classList.add("speaking"); lcd(priv ? "CHECK APP" : "KAVACH", true);
  clearTimeout(S.st); S.st = setTimeout(() => { sb.classList.remove("speaking"); idleLcd(); }, Math.min(9000, 1800 + text.length * 55));
  speak(s, text);
}

// ---------------------------------------------------------------- events
function handle(ev) {
  switch (ev.type) {
    case "step": {
      const s = ev.step;
      (S.steps[s.incident] ||= []).push(s);
      if (s.kind === "intake" && (!S.sel || !S.incidents[S.sel] || S.incidents[S.sel].status === "resolved" || s.sender === "monitor")) S.sel = s.incident;
      if (!S.sel) S.sel = s.incident;
      render();
      if (s.kind === "action" && s.action === "notify_merchant" && S.live && !S.spoken.has(s.incident + ":" + s.n)) soundbox(s);
      break;
    }
    case "incident": S.incidents[ev.incident.id] = ev.incident; if (!S.sel) S.sel = ev.incident.id; render(); clearTimeout(S.rt); S.rt = setTimeout(() => { refresh(); refreshFollowups().then(render); }, 250); break;
    case "world": S.world = ev.world; $("#clock").textContent = tm(ev.world.now); refreshFollowups().then(render); if (!$("#sbx").classList.contains("speaking")) idleLcd(); break;
    case "world_event":
      if (ev.event.kind === "soundbox" && ev.event.amount) { lcd("+₹ " + Number(ev.event.amount).toLocaleString("en-IN"), false, 3500); }
      refresh(); break;
    case "clock": $("#clock").textContent = tm(ev.now); break;
    case "lang": S.mlang = ev.lang; break;
    case "reset": location.reload(); break;
  }
}
async function refreshFollowups() { try { S.followups = await fetch("/api/followups").then((r) => r.json()); } catch (_) {} }
async function refresh() { try { S.world = await fetch("/api/world").then((r) => r.json()); $("#clock").textContent = tm(S.world.now); render(); } catch (_) {} }

async function boot() {
  const st = await fetch("/api/state").then((r) => r.json());
  S.world = st.world; S.mlang = st.merchant_lang || "en";
  st.incidents.forEach((i) => { S.incidents[i.id] = i; });
  st.steps.forEach((s) => { (S.steps[s.incident] ||= []).push(s); S.spoken.add(s.incident + ":" + s.n); });
  const latest = Object.values(S.incidents).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))[0];
  S.sel = latest ? latest.id : null;
  await refreshFollowups();
  $("#clock").textContent = tm(S.world.now); idleLcd();
  render();
  fetch("/api/integrations").then((r) => r.json()).then((i) => { S.intg = i; }).catch(() => {});
  const es = new EventSource("/api/stream");
  es.onmessage = (m) => { try { handle(JSON.parse(m.data)); } catch (e) { console.error(e); } };
  setTimeout(() => { S.live = true; }, 300);
}

// ---------------------------------------------------------------- controls
async function scenario(ds) {
  $("#menu").hidden = true;
  if ("speechSynthesis" in window) speechSynthesis.speak(new SpeechSynthesisUtterance(""));   // unlock audio on the click
  if (ds.scn === "live_check") { const oid = prompt("Paytm order ID (a real order on your staging MID):"); if (oid) await post("/api/live/check", { order_id: oid }); return; }
  const body = {};
  if (ds.mode) body.mode = ds.mode;
  if (ds.mule === "true") body.mule = true;
  await post(`/api/scenario/${ds.scn}`, body);
}
$$("[data-scn]").forEach((b) => b.addEventListener("click", () => scenario({ ...b.dataset })));
$("#skip").onclick = () => { if (S.skip) { $("#skip").disabled = true; S.skip(); } };
$("#more").onclick = (e) => { e.stopPropagation(); $("#menu").hidden = !$("#menu").hidden; };
document.addEventListener("click", (e) => { if (!$("#menu").contains(e.target)) $("#menu").hidden = true; });
const reset = async () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); await post("/api/reset"); location.reload(); };
$("#reset").onclick = reset;
function key(k) {
  const map = { "1": "payout_bounce", "2": "chargeback", "3": "live_payment" };
  if (map[k]) scenario({ scn: map[k] });
  if (k === "ArrowRight" && S.skip && !$("#skip").hidden && !$("#skip").disabled) $("#skip").click();
  if (k === "r" || k === "R") reset();
}
window.addEventListener("message", (e) => { if (e.origin === location.origin && e.data && e.data.kavachKey) key(e.data.kavachKey); });
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === "Escape") { $("#menu").hidden = true; return; }
  key(e.key);
});
$("#sound").onclick = () => { S.sound = !S.sound; $("#sound").setAttribute("aria-pressed", S.sound); $("#sound").innerHTML = `<i data-lucide="${S.sound ? "volume-2" : "volume-x"}" class="size-4"></i>`; if (!S.sound && "speechSynthesis" in window) speechSynthesis.cancel(); icons(); };
function dialog(title, html) { $("#dlg-t").textContent = title; $("#dlg-b").innerHTML = html; $("#dlg").showModal(); icons(); }
$("#open-eval").onclick = async () => {
  $("#menu").hidden = true;
  const r = await fetch("/api/eval").then((x) => x.json());
  if (r.error) return dialog("Evaluation", `<p class="text-ink-2">${esc(r.error)}</p>`);
  const fw = r.freeze_watch || {};
  dialog("Evaluation results", `<p class="text-[14px] text-ink-2 mb-4">${r.n} everyday incidents and ${fw.scenarios || 0} generated freeze and chargeback cases, run through the real engine, against a screenshot-trusting assistant.</p>
    <table class="w-full text-[13.5px]"><thead><tr class="text-left text-ink-3"><th class="font-medium py-2">Check</th><th class="font-medium py-2 text-right">Kavach</th><th class="font-medium py-2 text-right">Naive bot</th></tr></thead>
    <tbody>${r.metrics.map((m) => `<tr class="border-t border-line"><td class="py-2 pr-4 text-ink-2">${esc(m.label)}</td><td class="py-2 text-right font-semibold num">${esc(m.kavach)}</td><td class="py-2 text-right text-ink-3 num">${esc(m.baseline)}</td></tr>`).join("")}</tbody></table>
    <p class="mt-4 text-[12px] text-ink-3 leading-relaxed">${esc(r.caveat)}</p>`);
};
if (ONLY === "only-sound") {   // a phone won't speak until someone taps it once
  const t = $("#tap"); t.classList.add("on");
  t.onclick = () => { if ("speechSynthesis" in window) speechSynthesis.speak(new SpeechSynthesisUtterance("")); t.classList.remove("on"); };
}
if (ONLY === "only-desk") document.title = "Paytm Risk & Ops desk · Kavach";
if (ONLY === "only-sound") document.title = "Meena's Soundbox · Kavach";
icons();
boot();
