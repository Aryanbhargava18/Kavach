"use strict";
/* Live stage. Reads the same state and event stream as the console (S, handle() in app.js); nothing here is scripted.
   Every caption, node state and bubble comes from a real step the engine emitted. */
(() => {
  const NODES = [
    { id: "switch", label: "UPI switch", x: 21, y: 16, icon: "switch" },
    { id: "ledger", label: "Billing app", x: 79, y: 16, icon: "ledger" },
    { id: "policy", label: "Rules and SOP", x: 9, y: 54, icon: "policy" },
    { id: "refund", label: "Refunds", x: 91, y: 54, icon: "refund" },
    { id: "customer", label: "Customer", x: 23, y: 90, icon: "chat" },
    { id: "payout", label: "Payouts", x: 77, y: 90, icon: "payout" },
  ];
  const IC = {
    switch: "M4 8h15l-3-3M20 16H5l3 3", ledger: "M5 3h11l3 3v15H5zM8 9h8M8 13h8M8 17h5", refund: "M4 12a8 8 0 1 0 3-6M4 4v4h4",
    payout: "M12 3v11M7 9l5 5 5-5M4 17v3h16v-3", policy: "M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z", chat: "M4 5h16v11H9l-5 4z",
  };
  const T2N = { read_screenshot: "customer", lookup_transaction: "switch", get_payment_status: "switch", find_duplicate_payments: "switch", check_sale_pattern: "switch",
    get_merchant_ledger: "ledger", get_refund_status: "refund", get_settlement_status: "payout", get_bank_signal: "payout", get_incident_policy: "policy",
    route_sop: "policy", get_sop_clocks: "policy", ask_sop: "policy", read_document: "policy", parse_notice: "policy" };
  const A2N = { reconcile_payment: "ledger", initiate_refund: "refund", request_settlement_hold: "payout", change_settlement_account: "payout",
    send_customer_update_simulated: "customer", issue_verified_receipt: "customer", request_payment: "customer", generate_evidence_pack: "policy",
    create_support_case: "policy", record_case_event: "policy", draft_escalation: "policy", escalate_to_human: "policy", replay_soundbox: null };
  const COL2N = { switch: "switch", ledger: "ledger", refund: "refund", settlement: "payout", claim: "customer" };
  const TVERB = { read_screenshot: "Reading the customer's screenshot", lookup_transaction: "Finding the payment at the UPI switch",
    get_payment_status: "Asking the UPI switch what really happened", get_merchant_ledger: "Checking Meena's billing app",
    get_refund_status: "Checking for refunds on this payment", get_settlement_status: "Checking when it reaches Meena's bank",
    get_soundbox_log: "Checking what the Soundbox announced", get_incident_policy: "Loading the rules for this kind of problem",
    find_duplicate_payments: "Looking for a double charge", get_bank_signal: "Checking what Paytm can see of her bank",
    read_document: "Reading the bank notice", parse_notice: "Pulling the facts out of the notice", route_sop: "Finding the right step in the cyber-fraud SOP",
    get_sop_clocks: "Working out the deadlines", ask_sop: "Looking it up in the SOP", check_sale_pattern: "Comparing with her usual sales" };
  const FIXES = new Set(["reconcile_payment", "issue_verified_receipt", "initiate_refund", "request_settlement_hold", "request_payment", "generate_evidence_pack", "send_customer_update_simulated"]);

  const ST = { nodeState: {}, activeNode: null, seenM: new Set(), billStatus: {}, sig: "", boxTimer: null, q: [], qBusy: false };

  // ------------------------------------------------------------------ build the map
  function buildMap() {
    const map = $("#map");
    $("#wires").innerHTML = NODES.map((n) => `<line id="w-${n.id}" x1="50" y1="50" x2="${n.x}" y2="${n.y}"/>`).join("");
    NODES.forEach((n) => {
      const d = el("div", "node", `<div class="nd"><svg viewBox="0 0 24 24"><path d="${IC[n.icon]}"/></svg></div><b>${esc(n.label)}</b><span></span>`);
      d.id = `n-${n.id}`; d.style.left = n.x + "%"; d.style.top = n.y + "%";
      map.appendChild(d);
    });
  }
  function setNode(id, tone, text, extra) {
    const n = $(`#n-${id}`); if (!n) return;
    n.className = `node ${tone || ""} ${extra || ""}`;
    if (text != null) n.querySelector("span").textContent = text;
    const w = $(`#w-${id}`); if (w) w.setAttribute("class", tone || "");
    if (window.Scene3D) Scene3D.node(id, tone || "");
  }
  function activate(id) {
    if (window.Scene3D) NODES.forEach((n) => Scene3D.node(n.id, null, n.id === id));
    $$(".node.active").forEach((n) => n.classList.remove("active"));
    $$("#wires line.active").forEach((l) => l.classList.remove("active"));
    if (!id) return;
    $(`#n-${id}`)?.classList.add("active");
    $(`#w-${id}`)?.classList.add("active");
  }
  function nodeText(key, c) {
    if (!c || c.status == null) return "";
    if (key === "claim") return `${/notice/i.test(c.label || "") ? "notice" : "screenshot"} says ${rs(c.amount)}`;
    if (key === "switch") return c.amount != null ? `${c.status.toLowerCase()} · ${rs(c.amount)}` : c.status.toLowerCase();
    if (key === "ledger") return c.repaired ? `${(c.status.split("· ")[1] || "bill")} paid ✓` : c.status.replace("MISSING", "no entry").toLowerCase();
    if (key === "settlement") return c.status === "NOT YET" ? (c.note || "not yet").replace("next payout ", "next payout ") : `${c.status.toLowerCase()} · ${rs(c.amount)}`;
    return `${c.status.toLowerCase()}${c.amount ? " · " + rs(c.amount) : ""}`;
  }
  function paintNodes(inc) {
    const rec = (inc && inc.recon) || {};
    NODES.forEach((n) => { if (n.id !== "policy") setNode(n.id, "", ""); });
    $("#n-customer b").textContent = inc && inc.kind === "freeze" ? "Police notice" : inc && inc.customer && inc.customer.name ? inc.customer.name : "Customer";
    Object.entries(COL2N).forEach(([k, id]) => {
      const c = rec[k]; if (!c) return;
      setNode(id, tone(k, c, rec), nodeText(k, c), k === "ledger" && c.repaired ? "fixed" : "");
    });
    if (!rec.settlement && rec.bank) setNode("payout", tone("bank", rec.bank, rec), rec.bank.status.toLowerCase());
    const steps = inc ? S.steps[inc.id] || [] : [];
    const deny = steps.filter((s) => s.kind === "policy" && s.verdict === "DENY");
    const allow = steps.filter((s) => s.kind === "policy" && s.verdict === "ALLOW");
    if (deny.length) setNode("policy", "bad", `stopped ${deny.length} unsafe step${deny.length > 1 ? "s" : ""}`);
    else if (allow.length) setNode("policy", "ok", `${allow.length} action${allow.length > 1 ? "s" : ""} checked`);
    else setNode("policy", "", inc ? "" : "");
  }

  // ------------------------------------------------------------------ the Soundbox
  function box(state, lcd, ms) {
    const b = $("#box"); b.dataset.state = state;
    if (window.Scene3D) { Scene3D.box(state, lcd); if (ms) setTimeout(() => { if (b.dataset.state === "idle") Scene3D.box("idle", ST.lcd || "ON DUTY"); }, ms + 20); }
    if (lcd != null) $("#lcd").textContent = lcd;
    clearTimeout(ST.boxTimer);
    if (ms) ST.boxTimer = setTimeout(() => { b.dataset.state = "idle"; $("#lcd").textContent = ST.lcd || "ON DUTY"; }, ms);
  }
  window.stageSpeak = () => { const b = $("#box"); if (b.dataset.state !== "stopped") box("speaking", null, 3200); };

  // ------------------------------------------------------------------ captions
  function caption(line, sub, toneC, hold = 1500) {
    ST.q.push({ line, sub, tone: toneC, hold });
    if (ST.q.length > 3) ST.q.splice(0, ST.q.length - 3);
    pump();
  }
  function pump() {
    if (ST.qBusy || !ST.q.length) return;
    ST.qBusy = true;
    const c = ST.q.shift();
    showLine(c);
    setTimeout(() => { ST.qBusy = false; pump(); }, ST.q.length ? Math.min(c.hold, 900) : c.hold);
  }
  function showLine(c) {
    const l = $("#line");
    l.textContent = c.line; l.className = `line in ${c.tone || ""}`;
    void l.offsetWidth;
    $("#sub").textContent = c.sub || "";
    $("#go-row").hidden = true;
  }
  const firstSentence = (t, n = 170) => { const s = String(t || "").split(/(?<=[.!?])\s/)[0]; return s.length > n ? s.slice(0, n - 1) + "…" : s; };

  function captionFor(s, inc) {
    switch (s.kind) {
      case "intake":
        if (s.sender === "monitor" && s.engine === "payout-monitor") return ["Meena's bank just sent her payout back.", s.text + " · nobody has told Meena", "warn", 2800];
        if (s.sender === "monitor") return ["Meena's billing app never heard about this payment.", s.text, "warn", 2600];
        return [s.sender === "customer" ? `${(inc.customer && inc.customer.name) || "A customer"} writes in: “${firstSentence(s.text, 90)}”` : `Meena: “${firstSentence(s.text, 90)}”`, "Kavach owns this until it's fixed.", "", 1800];
      case "think": return [firstSentence(s.text), s.text.length > 170 ? "" : "", s.tone === "warn" ? "warn" : "", 2200];
      case "tool": return [TVERB[s.tool] || s.tool.replace(/_/g, " "), s.summary, "", 1000];
      case "evidence": return [s.verdict, inc.decisive ? inc.decisive.text : "", s.tone === "bad" ? "bad" : s.tone === "good" ? "ok" : "warn", 2600];
      case "policy":
        if (s.verdict === "DENY") return [`Kavach stopped itself from ${DENY_NAMES[s.action] || s.action.replace(/_/g, " ")}.`, s.reason, "bad", 3000];
        return null;
      case "approval": return [`Needs ${s.approvers.map((a) => APPROVER[a] || a).join(" and ")} to approve before it can ${VERB[s.action] || s.action.replace(/_/g, " ")}.`, s.reason, "warn", 2400];
      case "action":
        if (s.action === "notify_merchant") return [firstSentence(s.args.text.replace(/^[^\w₹]+/u, "").replace(/:?\s*Payment T\d{8,}/, "").replace(/\s*\(UPI Ref \d+\)/, ""), 120), "Sent to Meena" + (s.args.speak ? " and spoken on her Soundbox" : ""), "", 2600];
        if (s.action === "resolve_incident") return ["Case closed.", s.args.outcome, "ok", 3000];
        if (s.action === "reconcile_payment") return ["Fixed Meena's books from the bank's own record.", (s.result || {}).summary, "ok", 2200];
        if (s.action === "schedule_followup") return ["Kavach will come back to this on its own.", (s.result || {}).summary, "", 2000];
        return [ACTION_NAMES[s.action] || s.action, (s.result || {}).summary, "", 1500];
      case "verify":
        if (s.action === "final re-check" || s.action === "reconcile_payment") return ["Checked again. Both records agree.", s.check, "ok", 2000];
        return null;
      case "followup": return ["Back on its own.", s.purpose + (s.via ? ` (${s.via})` : ""), "", 1800];
    }
    return null;
  }

  // ------------------------------------------------------------------ Meena's phone: her running chat with Kavach, across cases
  function meenaItem(s) {
    const inc = S.incidents[s.incident] || {};
    const key = `${s.incident}:${s.n}`;
    if (s.kind === "intake" && s.sender === "merchant") return [key, `<div class="bub me">${esc(s.text)}<time>${tm(s.at)}</time></div>`];
    if (s.kind === "action" && s.action === "notify_merchant") {
      const x = s.args.extra || {};
      const links = x.pack ? `<br><a href="/pack/${x.pack}.pdf" target="_blank" rel="noopener">Signed pack</a> · <a href="/verify/${x.pack}" target="_blank" rel="noopener">Verify it</a>` : "";
      return [key, `<div class="bub k">${esc(s.args.text)}${links}<time>${tm(s.at)}</time></div>`];
    }
    if (s.kind === "action" && inc.channel !== "whatsapp" && (s.action === "issue_verified_receipt" || s.action === "request_payment")) {
      const r = s.result || {};
      const body = s.action === "issue_verified_receipt" ? `<div class="rc"><b>Verified with the UPI switch</b><br>${esc(r.summary || "")}</div>`
        : `Show this to the customer: pay ${rs(s.args.amount)}${r.upi_uri ? `<img class="qr" src="/api/qr?data=${encodeURIComponent(r.upi_uri)}" alt="QR for ${rs(s.args.amount)}">` : ""}`;
      return [key, `<div class="bub k">${body}<time>${tm(s.at)}</time></div>`];
    }
    if (s.kind === "approval" && s.approvers.includes("merchant")) {
      return [key, `<div class="bub k" data-ap="${s.incident}">${esc(s.reason)}<br><b>Kya main ${esc(VERB[s.action] || s.action.replace(/_/g, " "))} karun?</b>
        <div class="acts"><button data-yes="${s.incident}">Haan, karo</button><button class="no" data-no="${s.incident}">Abhi nahi</button></div><time>${tm(s.at)}</time></div>`];
    }
    return null;
  }
  function addMeena(s, animate) {
    const it = meenaItem(s); if (!it || ST.seenM.has(it[0])) return;
    ST.seenM.add(it[0]);
    const ol = $("#m-msgs");
    $(".ph-hint", ol)?.remove();
    const li = document.createElement("li"); li.style.display = "contents"; li.innerHTML = it[1];
    if (!animate) li.firstElementChild.style.animation = "none";
    ol.appendChild(li);
    li.querySelector("[data-yes]")?.addEventListener("click", (e) => { e.target.parentElement.innerHTML = "<span class='done'>Sending…</span>"; post("/api/approve", { incident_id: e.target.dataset.yes, approver: "merchant", yes: true }); });
    li.querySelector("[data-no]")?.addEventListener("click", (e) => { e.target.parentElement.innerHTML = "<span class='done'>Declined</span>"; post("/api/approve", { incident_id: e.target.dataset.no, approver: "merchant", yes: false }); });
    ol.scrollTop = 1e9;
  }
  function approvalResult(s) {
    if (s.approver !== "merchant") return;
    $$(`[data-ap="${s.incident}"] .acts`).forEach((a) => { a.innerHTML = `<span class="done">${s.approved ? "✓ Meena approved" : "Meena declined"}</span>`; });
  }

  // ------------------------------------------------------------------ the other side
  function renderRight() {
    const inc = S.incidents[S.sel];
    const top = $("#r-top"), body = $("#r-body"), cap = $("#r-cap"), cf = $("#c-form");
    if (inc && inc.channel === "whatsapp") {
      const name = inc.customer.name || "Customer";
      top.innerHTML = `<i class="ph-av wa">${esc(name[0])}</i><div><b>${esc(name)}</b><span>WhatsApp with Meena Kirana · simulated</span></div>`;
      cap.textContent = `${name}'s phone`;
      cf.hidden = false;
      const items = [];
      (S.steps[inc.id] || []).forEach((s) => {
        if (s.kind === "intake" && s.sender === "customer") {
          const shotStep = (S.steps[inc.id] || []).find((x) => x.kind === "tool" && x.tool === "read_screenshot" && x.n > s.n && x.n < s.n + 8);
          const shot = shotStep ? `<img class="shot" src="/api/shot/${shotStep.args.shot_id}.png" alt="Payment screenshot" data-zoom>` : "";
          items.push(`<div class="bub cust">${esc(s.text)}${shot}<time>${tm(s.at)}</time></div>`);
        }
        if (s.kind === "action" && s.action === "send_customer_update_simulated") items.push(`<div class="bub kwa">${esc(s.args.text)}<time>${tm(s.at)} ✓✓</time></div>`);
        if (s.kind === "action" && s.action === "issue_verified_receipt") items.push(`<div class="bub kwa"><div class="rc"><b>Verified with the UPI switch</b><br>${esc((s.result || {}).summary || "")}</div><time>${tm(s.at)} ✓✓</time></div>`);
        if (s.kind === "action" && s.action === "request_payment") { const r = s.result || {}; items.push(`<div class="bub kwa">Pay ${rs(s.args.amount)} to Meena Kirana Store${r.upi_uri ? `<img class="qr" src="/api/qr?data=${encodeURIComponent(r.upi_uri)}" alt="QR">` : ""}<time>${tm(s.at)} ✓✓</time></div>`); }
      });
      body.innerHTML = items.join("") || `<p class="ph-hint">No messages yet.</p>`;
    } else if (inc && inc.kind === "freeze") {
      top.innerHTML = `<i class="ph-av">§</i><div><b>Case file</b><span>Account hold · built by Kavach</span></div>`;
      cap.textContent = "Meena's case file";
      cf.hidden = true;
      const f = inc.facts || {};
      const doc = (S.steps[inc.id] || []).find((s) => s.kind === "tool" && s.tool === "read_document");
      const parts = [];
      const back = inc.recon && inc.recon.settlement && inc.recon.settlement.status === "RETURNED" ? inc.recon.settlement : null;
      if (back) {
        const held = S.world && S.world.settlement_config && S.world.settlement_config.paused;
        parts.push(`<div class="bill focus"><div class="bill-top"><b>Payout ${esc(back.ref || "")}</b><span class="bill-amt">${rs(back.amount)}</span></div>
          <div class="bill-who">Sent back by Meena's bank${f.proactive ? ", found by Kavach before anyone complained" : ""}</div><span class="bill-st UNPAID">Returned · account frozen</span>
          <div class="bill-note">${held ? "New payouts held in Paytm's settlement balance (Meena + Paytm Risk approved). Nothing moved to another account." : "Back in Paytm's settlement balance. Holding new payouts needs Meena and Paytm Risk."}</div></div>`);
      }
      const disputed = f.disputed_txn && inc.recon && inc.recon.switch && inc.recon.switch.amount, locked = f.locked_stated;   // T1: the switch record, never the notice
      if (disputed && locked && locked > disputed) {
        const pct = Math.max(1.5, Math.min(100, (disputed / locked) * 100));
        parts.push(`<div class="bill overhold"><div class="bill-top"><b>Disputed vs frozen</b><span class="bill-amt">${Math.round(locked / disputed)}×</span></div>
          <div class="oh-bar" role="img" aria-label="${rs(disputed)} disputed out of ${rs(locked)} frozen"><i style="width:${pct}%"></i></div>
          <div class="bill-note"><b>${rs(disputed)}</b> disputed (Paytm record) · <b>${rs(locked)}</b> frozen (Meena's figure, unverified). The SOP prefers holding only the disputed amount where it can be identified.</div>
          <div class="bill-note dim">Nationally, I4C's own table to 30 Jun 2026: ₹303 cr frozen against ₹29 cr disputed (our sum of its rows).</div></div>`);
      }
      if (doc) parts.push(`<div class="bill case-file"><b>Bank SMS and police notice</b><img src="/api/doc/${doc.args.doc_id}.png" alt="Notice" data-zoom></div>`);
      if (f.pack) parts.push(`<div class="bill"><div class="bill-top"><b>Signed evidence pack</b></div><div class="bill-note">Token ${esc(f.pack.token)}. Change one digit and verification fails.</div><div class="bill-note"><a href="/pack/${esc(f.pack.token)}.pdf" target="_blank" rel="noopener">Open PDF</a> · <a href="/verify/${esc(f.pack.token)}" target="_blank" rel="noopener">Verify it</a></div></div>`);
      (f.clocks || []).forEach((c) => parts.push(`<div class="bill small"><div class="bill-top"><b>${esc(c.clock)}</b></div><div class="bill-note">${c.start ? `${esc(c.start)} → ${esc(c.due || "?")}` : esc(c.starts_on || "needs a dated event")}</div></div>`));
      if (inc.money && inc.money.amount && !back && !(disputed && locked)) parts.push(`<div class="bill small"><div class="bill-note">${rs(inc.money.amount)} ${esc(inc.money.label)}</div></div>`);
      body.innerHTML = parts.join("") || `<p class="ph-hint">Kavach builds the case here as Meena shares the notice.</p>`;
    } else {
      top.innerHTML = `<i class="ph-av bill">₹</i><div><b>Billing app</b><span>Meena Kirana Store · today's bills</span></div>`;
      cap.textContent = "The shop's billing app";
      cf.hidden = true;
      const bills = (S.world && S.world.bills) || [];
      const focus = inc && inc.facts && inc.facts.bill_id;
      const led = inc && inc.recon && inc.recon.ledger;
      const order = [...bills].sort((a, b) => (b.bill_id === focus) - (a.bill_id === focus));
      body.innerHTML = order.slice(0, 6).map((b, i) => {
        const f = b.bill_id === focus || (!focus && i === 0);
        const prev = ST.billStatus[b.bill_id];
        const flip = prev && prev !== b.status ? "flip" : "";
        ST.billStatus[b.bill_id] = b.status;
        const note = f && led && led.repaired ? `Marked paid by Kavach from the UPI switch record (UTR …${String(led.ref || "").slice(-4)}). Paytm's update to this app had failed.`
          : f && b.status !== "PAID" ? `Paid ${rs(b.paid_amount)} of ${rs(b.amount)}` : "";
        return `<div class="bill ${f ? "focus" : "small"} ${flip}"><div class="bill-top"><b>${esc(b.bill_id)}</b><span class="bill-amt">${rs(b.amount)}</span></div>
          <div class="bill-who">${esc(b.customer || "walk-in")}</div><span class="bill-st ${b.status}">${b.status === "PAID" ? "Paid" : b.status === "PARTIAL" ? "Part paid" : "Unpaid"}</span>
          ${f && note ? `<div class="bill-note">${esc(note)}</div>` : ""}</div>`;
      }).join("") || `<p class="ph-hint">No bills yet.</p>`;
    }
    $$("[data-zoom]", body).forEach((im) => im.onclick = () => openImg(im.src));
    body.scrollTop = inc && inc.channel === "whatsapp" ? 1e9 : 0;
  }

  // ------------------------------------------------------------------ the band
  function secs(a, b) { return Math.max(0, Math.round((new Date(b) - new Date(a)) / 1000)); }
  function dur(n) { return n < 60 ? `${n} s` : `${Math.floor(n / 60)} min ${n % 60} s`; }
  function renderBand() {
    const inc = S.incidents[S.sel];
    const all = Object.values(S.incidents);
    const r = $("#result");
    if (!inc) { r.innerHTML = all.length ? "" : "Nothing to fix yet. Run a scenario and watch Kavach work."; return; }
    const steps = S.steps[inc.id] || [];
    const denies = steps.filter((s) => s.kind === "policy" && s.verdict === "DENY").length;
    const fix = steps.find((s) => s.kind === "verify" && s.ok && FIXES.has(s.action));
    let h = "";
    if (inc.pending && inc.pending.approvers && inc.pending.approvers.length) {
      h = `Waiting for <b>${inc.pending.approvers.map((a) => APPROVER[a] || a).join(" and ")}</b> to approve. Kavach won't ${esc(VERB[inc.pending.action] || inc.pending.action.replace(/_/g, " "))} on its own.`;
    } else if (inc.kind === "freeze" && inc.facts && inc.facts.proactive && steps.some((s) => s.kind === "action" && s.action === "notify_merchant")) {
      const warned = steps.find((s) => s.kind === "action" && s.action === "notify_merchant");
      h = `Meena warned in <b class="good">${dur(secs(inc.created_at, warned.at))}</b>, before her first supplier payment bounced.`;
      if (inc.money && inc.money.amount) h += ` <b class="amt-b">${rs(inc.money.amount)}</b> ${esc(inc.money.label)}.`;
      if (denies) h += ` Stopped <b class="bad">${denies}</b> unsafe step${denies > 1 ? "s" : ""}.`;
    } else if (fix) {
      const proactive = inc.facts && inc.facts.proactive;
      const repaired = steps.some((x) => x.kind === "verify" && x.ok && x.action === "reconcile_payment");
      h = `${repaired ? "Fixed" : "Handled"} in <b class="good">${dur(secs(inc.created_at, fix.at))}</b>${proactive ? ", before anyone complained" : ""}.`;
      if (inc.money && inc.money.amount) h += ` <b class="amt-b">${rs(inc.money.amount)}</b> ${esc(inc.money.label)}.`;
      if (denies) h += ` Stopped <b class="bad">${denies}</b> unsafe step${denies > 1 ? "s" : ""}.`;
    } else if (inc.status === "investigating") {
      h = `Working. <b>${steps.filter((s) => s.kind === "tool").length}</b> checks so far.`;
    } else {
      h = esc(inc.headline || STATUS[inc.status] || "");
      if (denies) h += ` Stopped <b class="bad">${denies}</b> unsafe step${denies > 1 ? "s" : ""}.`;
    }
    const fu = (S.followups || []).filter((f) => f.incident === inc.id && !f.fired)[0];
    const handled = all.length, stopped = all.reduce((n, i) => n + (S.steps[i.id] || []).filter((s) => s.kind === "policy" && s.verdict === "DENY").length, 0);
    const money = all.filter((i) => i.kind !== "freeze").reduce((n, i) => n + ((i.money && i.money.amount) || 0), 0);
    const small = inc.status === "resolved" ? `Closed: ${inc.outcome || ""}` : fu ? `Next, on its own: ${fu.purpose.toLowerCase()} (${dayTm(fu.due)})` : "";
    r.innerHTML = `${h}<small>${esc(small)}${small ? " · " : ""}Today: ${handled} case${handled > 1 ? "s" : ""}, ${money ? rs(money) + " kept right, " : ""}${stopped} unsafe step${stopped === 1 ? "" : "s"} stopped, 0 support tickets.</small>`;
  }
  window.stageActions = (btns) => {
    const sig = btns.map((b) => b[0]).join("|");
    if (sig === ST.sig) return;
    ST.sig = sig;
    const box2 = $("#next-acts"); box2.innerHTML = "";
    btns.forEach(([label, fn, go], i) => { const b = el("button", `nx ${go && i === 0 ? "go2" : ""}`, esc(label)); b.onclick = () => { b.disabled = true; fn(); }; box2.appendChild(b); });
  };
  window.stageSuggest = (opts) => {
    const mk = (cls) => { let c = $(`.${cls}`); return c; };
    ["m", "c"].forEach((w) => {
      const form = w === "m" ? $("#m-form") : $("#c-form");
      let row = form.previousElementSibling && form.previousElementSibling.classList.contains("chips-in") ? form.previousElementSibling : null;
      if (!row) { row = el("div", "chips-in"); form.before(row); }
      row.innerHTML = "";
      opts.filter((o) => (o.as === "merchant") === (w === "m")).forEach((o) => {
        const b = el("button", o.cls === "doc" ? "doc" : "", esc(o.label)); b.type = "button";
        b.onclick = () => sendAs(o.as, o.draft.text, o.draft.doc_id);
        row.appendChild(b);
      });
    });
    void mk;
  };
  function sendAs(as, text, doc_id) {
    unlockAudio(); S.follow = true;
    if (doc_id) S.nextDoc = null;
    const inc = S.incidents[S.sel];
    if (as === "customer") post("/api/customer/message", { text, shot_id: null, customer: inc && inc.channel === "whatsapp" ? inc.customer : null });
    else post("/api/merchant/message", { text, shot_id: null, doc_id: doc_id || null });
  }

  // ------------------------------------------------------------------ phases: detect → investigate → reconcile → act → verify → follow up
  const ACT = new Set(["reconcile_payment", "issue_verified_receipt", "request_payment", "initiate_refund", "request_settlement_hold", "generate_evidence_pack",
    "replay_soundbox", "record_case_event", "change_settlement_account", "draft_escalation"]);
  const PH = ["detect", "investigate", "reconcile", "act", "verify", "follow"];
  function phaseOf(s) {
    switch (s.kind) {
      case "intake": return "detect";
      case "think": return null;
      case "tool": return ["get_merchant_ledger", "get_refund_status", "get_settlement_status"].includes(s.tool) ? "reconcile" : "investigate";
      case "evidence": return "reconcile";
      case "policy": return s.verdict === "DENY" ? "refuse" : ACT.has(s.action) ? "act" : null;
      case "approval": case "approval_result": return "act";
      case "action": return ["schedule_followup", "resolve_incident", "escalate_to_human"].includes(s.action) ? "follow" : ACT.has(s.action) ? "act" : null;
      case "verify": return ACT.has(s.action) || s.action === "final re-check" ? "verify" : null;
      case "followup": return "follow";
    }
    return null;
  }
  function paintPhases(inc, live) {
    const steps = inc ? S.steps[inc.id] || [] : [];
    let cur = null, refused = false, reached = -1;
    steps.forEach((s) => { const p = phaseOf(s); if (!p) return; if (p === "refuse") { refused = true; cur = "act"; } else cur = p; reached = Math.max(reached, PH.indexOf(cur)); });
    const done = inc && inc.status === "resolved";
    $$("#phases li").forEach((li, i) => {
      li.classList.toggle("done", done || i < PH.indexOf(cur) || (i <= reached && li.dataset.p !== cur));
      li.classList.toggle("now", !done && li.dataset.p === cur);
      li.classList.toggle("refused", li.dataset.p === "act" && refused);
    });
    $("#phases").classList.toggle("idle", !inc);
    if (live && window.Scene3D) Scene3D.phase(done ? "follow" : refused && cur === "act" ? "refuse" : cur || "idle");
  }

  // ------------------------------------------------------------------ real values flying between the systems and Kavach
  function fly(fromId, text, toneC, outbound) {
    if (!window.Scene3D || !text) return;
    const a = Scene3D.screen(fromId), b = Scene3D.boxScreen(); if (!a || !b) return;
    const [p, q] = outbound ? [b, a] : [a, b];
    const c = el("div", `chip ${toneC || ""}`, esc(text));
    $("#fly").appendChild(c);
    const anim = c.animate([
      { transform: `translate(${p.x}px, ${p.y}px) translate(-50%, -50%) scale(.85)`, opacity: 0 },
      { transform: `translate(${p.x}px, ${p.y}px) translate(-50%, -50%) scale(1)`, opacity: 1, offset: 0.15 },
      { transform: `translate(${(p.x + q.x) / 2}px, ${(p.y + q.y) / 2 - 26}px) translate(-50%, -50%) scale(1)`, opacity: 1, offset: 0.6 },
      { transform: `translate(${q.x}px, ${q.y}px) translate(-50%, -50%) scale(.7)`, opacity: 0 }],
      { duration: 1500, easing: "cubic-bezier(.45,.05,.3,1)" });
    anim.onfinish = () => c.remove();
  }
  function shortVal(s, inc) {
    const rec = inc.recon || {};
    const col = { read_screenshot: "claim", get_payment_status: "switch", lookup_transaction: "switch", get_merchant_ledger: "ledger", get_refund_status: "refund", get_settlement_status: "settlement" }[s.tool];
    if (col && rec[col]) return [nodeText(col, rec[col]), tone(col, rec[col], rec)];
    const t = String(s.summary || "").split(" · ")[0];
    return [t.length > 34 ? t.slice(0, 33) + "…" : t, ""];
  }

  // ------------------------------------------------------------------ voice: waveform + Hindi subtitle, word by word
  const V = { ctx: null, analyser: null, raf: 0, words: [], mode: null, t0: 0, fallback: 0 };
  function setSubtitle(text) {
    V.words = []; let i = 0;
    const html = text.split(/(\s+)/).map((w) => { if (/^\s+$/.test(w)) { i += w.length; return w; } V.words.push({ at: i, len: w.length }); i += w.length; return `<span>${esc(w)}</span>`; }).join("");
    $("#hindi").innerHTML = html;
  }
  function hl(k) { $$("#hindi span").forEach((s, j) => s.classList.toggle("on", j <= k)); }
  function startViz(mode, text, voice) {
    cancelAnimationFrame(V.raf); clearTimeout(V.fallback);
    V.mode = mode; V.t0 = performance.now();
    setSubtitle(text); $("#voice").hidden = false; $("#voice").dataset.voice = voice || "kavach";
    $("#sub").hidden = true;
    if (window.Scene3D) Scene3D.box("speaking"); $("#box").dataset.state = "speaking";
    const cv = $("#wave"), g = cv.getContext("2d"), data = new Uint8Array(64);
    const est = Math.max(1800, text.length * 75);
    const draw = () => {
      const t = performance.now() - V.t0;
      g.clearRect(0, 0, cv.width, cv.height);
      const n = 56, bw = cv.width / n;
      if (V.analyser && mode === "audio") V.analyser.getByteFrequencyData(data);
      for (let i = 0; i < n; i++) {
        const env = Math.sin(Math.PI * i / n);
        const v = V.analyser && mode === "audio" ? data[(i * 3) % 64] / 255 : (0.25 + 0.75 * Math.abs(Math.sin(t / 140 + i * 0.55) * Math.sin(t / 310 + i * 0.21))) * (mode === "silent" ? 0.5 : 1);
        const h = Math.max(2, v * env * cv.height * 0.95);
        g.fillStyle = voice === "soundbox" ? "rgba(255,176,32,.9)" : "rgba(31,182,240,.95)";
        g.fillRect(i * bw + 1.5, (cv.height - h) / 2, bw - 3, h);
      }
      if (mode !== "synth") hl(Math.floor((t / est) * V.words.length));
      if (mode === "silent" && t > est) return endViz();
      V.raf = requestAnimationFrame(draw);
    };
    draw();
  }
  function endViz() {
    cancelAnimationFrame(V.raf); clearTimeout(V.fallback);
    hl(1e9);
    setTimeout(() => { if (!V.raf || V.mode === "ended") { $("#voice").hidden = true; $("#sub").hidden = false; } }, 1600);
    V.mode = "ended"; V.raf = 0;
    if ($("#box").dataset.state === "speaking") box("idle", ST.lcd || "ON DUTY");
  }
  window.stageVoice = {
    pending(text, voice) { clearTimeout(V.fallback); V.fallback = setTimeout(() => startViz("silent", text, voice), 900); },
    audio(a, text, voice) {
      clearTimeout(V.fallback);
      try {
        V.ctx ||= new (window.AudioContext || window.webkitAudioContext)();
        const src = V.ctx.createMediaElementSource(a); V.analyser = V.ctx.createAnalyser(); V.analyser.fftSize = 128;
        src.connect(V.analyser); V.analyser.connect(V.ctx.destination);
      } catch (_) { V.analyser = null; }
      a.addEventListener("playing", () => startViz(V.analyser ? "audio" : "silent", text, voice), { once: true });
    },
    synth(text, voice) { startViz("synth", text, voice); },
    word(ci) { const k = V.words.findIndex((w) => w.at > ci) - 1; hl(k < 0 ? V.words.length - 1 : k); },
    silent(text, voice) { startViz("silent", text, voice); },
    end() { endViz(); },
  };
  window.stageListening = (on) => {
    if (on) { box("listening", "SUN RAHA HOON"); if (window.Scene3D) Scene3D.box("listening", "SUN RAHA HOON"); caption("Kavach is listening.", "Meena can speak in Hindi or Hinglish.", "", 1200); }
    else { box("idle", ST.lcd || "ON DUTY"); }
  };

  // ------------------------------------------------------------------ wiring
  function repaint(fromStep) {
    const inc = S.incidents[S.sel];
    paintNodes(inc); renderRight(); renderBand(); if (!fromStep) paintPhases(inc, true);
    if (!fromStep && inc) {   // replay: show the last meaningful line, no queue
      const steps = S.steps[inc.id] || [];
      for (let i = steps.length - 1; i >= 0; i--) { const c = captionFor(steps[i], inc); if (c) { showLine({ line: c[0], sub: c[1], tone: c[2] }); break; } }
    }
  }
  window.stageBoot = () => {
    buildMap();
    Object.values(S.steps).flat().sort((a, b) => a.at.localeCompare(b.at)).forEach((s) => addMeena(s, false));
    repaint(false);
    $("#go-row").hidden = Object.keys(S.incidents).length > 0;
  };
  window.stageSelect = () => { repaint(false); };
  window.stageOn = (ev) => {
    if (ev.type === "tool_start") {
      if (ev.incident !== S.sel && S.sel) return;
      activate(T2N[ev.tool]); box("thinking", "CHECKING");
      return;
    }
    if (ev.type === "step") {
      const s = ev.step;
      setTimeout(() => {   // after app.js has stored it
        addMeena(s, true);
        if (s.kind === "approval_result") approvalResult(s);
        if (s.incident !== S.sel) return;
        const inc = S.incidents[s.incident] || {};
        const c = captionFor(s, inc);
        if (c) caption(c[0], c[1], c[2], c[3]);
        paintPhases(inc, true);
        if (s.kind === "tool" && T2N[s.tool]) { const [v, tn] = shortVal(s, inc); fly(T2N[s.tool], v, tn, false); window.Scene3D && Scene3D.focus(T2N[s.tool]); }
        if (s.kind === "action" && A2N[s.action]) fly(A2N[s.action], ACTION_NAMES[s.action] || s.action, "ok", true);
        if (s.kind === "policy" && s.verdict === "DENY") fly("policy", `refused · ${s.rule}`, "bad", false);
        if (s.kind === "tool") { activate(null); if ($("#box").dataset.state === "thinking") box("idle", ST.lcd || "ON DUTY"); }
        if (s.kind === "action" && A2N[s.action]) { activate(A2N[s.action]); window.Scene3D && Scene3D.burst(A2N[s.action], "ok"); setTimeout(() => activate(null), 900); }
        if (s.kind === "policy" && s.verdict === "DENY") { box("stopped", "STOPPED", 2600); setNode("policy", "bad"); }
        if (s.kind === "verify" && s.ok && (s.action === "reconcile_payment" || s.action === "final re-check")) { ST.lcd = "FIXED ✓"; box("fixed", ST.lcd, 2600); }
        if (s.kind === "action" && s.action === "resolve_incident") { ST.lcd = "CLOSED ✓"; box("fixed", ST.lcd, 3000); }
        if (s.kind === "intake") ST.lcd = "ON DUTY";
        if (s.kind === "evidence") { ST.lcd = s.stamp || "ON DUTY"; box("idle", ST.lcd); }
        repaint(true);
      }, 0);
      return;
    }
    if (ev.type === "incident") { setTimeout(() => { if (ev.incident.id === S.sel) { paintNodes(ev.incident); renderBand(); } }, 0); return; }
    if (ev.type === "world_event" && ev.event.kind === "soundbox") {
      box("speaking", `+${rs(ev.event.amount)}`, 3200);
      setTimeout(() => fly("switch", `UPI · +${rs(ev.event.amount)} SUCCESS`, "ok", false), 200);
      if (!S.sel || (S.incidents[S.sel] || {}).status === "resolved") caption(`“Paytm par ${rs(ev.event.amount)} prapt hue.”`, "Meena's Soundbox just announced a payment. Kavach checks that every system agrees.", "", 2400);
      return;
    }
    if (ev.type === "world") { setTimeout(renderRight, 0); }
  };

  $("#m-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const t = $("#m-text").value.trim(); if (!t) return;
    $("#m-text").value = "";
    sendAs("merchant", t, null);
  });
  $("#c-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const t = $("#c-text").value.trim(); if (!t) return;
    $("#c-text").value = "";
    sendAs("customer", t, null);
  });
  const menu = $("#st-menu");
  [$("#st-menu-open"), $("#st-menu-open2")].forEach((b) => b && (b.onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; }));
  document.addEventListener("click", (e) => { if (!menu.contains(e.target)) menu.hidden = true; });
  menu.addEventListener("click", (e) => { if (e.target.closest("[data-scn]")) { menu.hidden = true; $("#go-row").hidden = true; } });
  $("#go-row").addEventListener("click", (e) => { if (e.target.closest("[data-scn]")) $("#go-row").hidden = true; });
  setInterval(renderBand, 2000);
})();
