# Submission answers (copy-paste)

**City and Date:** [City], 31 October 2026
**Track:** Track 3, Autonomous AI Teammates
**Team:** Second Signal · **Lead:** Aryan Bhargava · **Project:** Kavach
**Repo:** https://github.com/Aryanbhargava18/Kavach

---

## Description

**Kavach is an autonomous AI teammate for Paytm's merchant service. It acts before the merchant complains.**

**Problem:** when a bank freezes a small merchant's account over a cyber-fraud report, nobody tells her. Often the whole balance is locked for a small dispute: a High Court freed ₹8.26 lakh frozen for ten months over one ₹1,000 UPI payment, and I4C data shows about ₹303 crore frozen against ₹29 crore disputed.

**Insight:** Paytm knows first, when her payout bounces or her own payment is declined (UPI code YE). Today nobody acts on it.

**What Kavach does, end to end:** it detects the bounce, checks Paytm Risk (never tipping off a mule account), and alerts her within seconds in Hindi or English on her Soundbox and app. It protects new payouts with two approvals (merchant and Paytm Risk), reads the police notice, ignores a hidden prompt injection, and drafts a request to freeze only the disputed amount, with a signed evidence pack. When the hold is limited, it verifies the account with ₹1 before release. The same loop handles chargebacks, missed payments, fake screenshots and double charges.

**Proven:** 243/243 everyday incidents and 240/240 freeze and chargeback cases handled correctly; 0 tip-offs, 0 invented evidence; 1,609 of 1,609 actions re-checked at the source. A screenshot-trusting bot issued 88 false receipts; Kavach issued 0.

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
