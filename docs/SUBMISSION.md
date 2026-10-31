# Submission answers (copy-paste)

**City and Date:** [City], 31 October 2026
**Track:** Track 3, Autonomous AI Teammates
**Team:** Second Signal · **Lead:** Aryan Bhargava · **Project:** Kavach
**Repo:** https://github.com/Aryanbhargava18/Kavach

---

## Description

**Kavach is an autonomous AI teammate for Paytm's merchant service. Most support starts when a merchant complains; Kavach starts when Paytm's own systems show something is wrong, resolves it across those systems, and brings in a person only when money moves.**

**The problem.** A small merchant's money gets stuck in ways she can't see. A customer says "I paid" but nothing arrived. She's charged twice. A bill stays unpaid after the money came. A chargeback deadline passes, and the amount is deducted automatically. Worst of all, her bank freezes her whole account over a cyber-fraud report, often for a tiny dispute: a High Court freed ₹8.26 lakh frozen for ten months over one ₹1,000 UPI payment, and I4C data shows about ₹303 crore frozen against ₹29 crore disputed. Each one becomes a support ticket after the damage is done.

**The insight.** Paytm sees almost all of these first: the UPI switch, the settlement return file, the dispute desk, failed billing-app messages, UPI decline codes. Nobody acts on them for the merchant.

**What Kavach does.** It runs one loop: notice → investigate at the source → decide under 20 safety rules → act across about 12 systems → re-check → follow up until it's resolved. It resolves payment claims (trusting the bank, not the screenshot), repairs missed bills, refunds true duplicates, answers chargebacks before the deadline without inventing proof, and stops extortion calls. In a freeze, it alerts her within seconds in Hindi or English, holds new payouts with her and Paytm Risk's approval, drafts a request to freeze only the disputed amount with a signed evidence pack, and checks her account with ₹1 before release.

**Why it's a teammate, not a chatbot.** It acts first, explains every decision, asks a person only for money moves or what only she knows, and its own rules blocked 98 unsafe steps its planner proposed.

**Measured.** 483 test cases across 31 scenario types, zero safety failures. Against a screenshot-trusting bot: false receipts 0 vs 88, customers asked to pay twice 0 vs 15, wrong refunds 0 vs 16, payouts rerouted during a freeze 0 vs 6. Every one of 1,609 actions was re-checked at the source.

**Built for Paytm.** It's live as three surfaces: the Soundbox, a Kavach layer in Paytm for Business, and a Risk & Ops desk. It plugs into existing data and calls Paytm's Transaction Status API. Free to merchants, it protects retention, loan collections, support cost, and a bank-facing Paytm Intelligence product.

---

## Technology stack
- **Backend:** Python, FastAPI, Server-Sent Events (live sync across app, Soundbox and staff desk)
- **Agent:** tool-calling loop (plan → act → verify at source), gated by 20 policy rules
- **Paytm API:** Transaction Status API (v3), signed with the official `paytmchecksum`
- **Trust:** Ed25519-signed PDF evidence with a public verifier; Tesseract OCR
- **Frontend:** vanilla JS, Tailwind CSS v4, English and Hindi
- **Infra:** Docker on Render or Hugging Face; 53 tests plus 483-case evaluation suites

## AI/ML tools
- **Sarvam-105B:** tool-calling planner
- **Sarvam Bulbul v3 / Saaras v3:** Hindi and English voice, speech-to-text
- **Claude:** alternative planner; **Claude Code:** used to build and test
- **Rules fallback:** money decisions never depend on a model

## Working Demo URL
`https://<your-render-or-hf-link>/`. Pages: `/m` merchant app · `/desk` Paytm staff · `/world` simulator · `/case` one case end to end

## Demo Video URL
YouTube (Unlisted) or Drive (anyone with link). Script below.

---

### Video script (2:30)
1. **0:00 Problem:** frozen accounts, ₹303 cr vs ₹29 cr, "Paytm knows first".
2. **0:20 Live:** `/world`, pay ₹200: Soundbox announces it, the app updates.
3. **0:35 Freeze:** `/world` → freeze. The app shows "Account frozen"; the Soundbox stays discreet. Tap "Keep it safe"; approve on `/desk`.
4. **1:15 Case:** forward the notice: 129× over-freeze, request to hold only ₹2,400, signed pack.
5. **1:45 Day 12:** `/world` → decide: ₹1 check, approve, "Account works again".
6. **2:05 Proof:** `/case`: steps and outcome tiles map to the Track 3 brief.
7. **2:25 Close:** "The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money."

### Deploy (pick one; full steps in DEPLOY.md)
- **Render:** dashboard.render.com → New → Blueprint → repo Kavach → Apply → paste `SARVAM_API_KEY`.
- **Hugging Face:** New Space (Docker) → push the repo (commands in DEPLOY.md).
