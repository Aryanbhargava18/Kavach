# Final submission: copy-paste answers

**City and Date:** [Your city], 31 October 2026

**Track Selected:** Track 3, Autonomous AI Teammates

**Team Name:** Second Signal · **Team Lead:** Aryan Bhargava · **Project Title:** Kavach

---

## Provide a brief description of your project and the problem it solves

Kavach is an autonomous AI teammate for Paytm's merchant customer service. It doesn't wait for a complaint: it watches Paytm's own signals, opens the case, does the work across Paytm's systems, and asks humans only for decisions that move money.

**The problem.** When a bank freezes a small merchant's account over a cyber-fraud report, nobody tells her. She finds out when her supplier payment bounces, while her daily payouts keep flowing into an account she can't use. Often the whole balance is frozen for a small dispute: a High Court released a shop's ₹8.26 lakh, frozen for ten months over one ₹1,000 UPI payment, and the government's own I4C data shows about ₹303 crore frozen against ₹29 crore actually disputed. Merchants call support, pay scammers who promise to "withdraw the complaint", or go back to cash.

**The insight.** Paytm usually knows first: the payout bounces back from her bank, or her own payment is declined with code YE. Today nobody acts on that.

**What Kavach does, end to end.** It notices the bounced payout within seconds. It checks Paytm Risk before saying a word (so a possible mule account is never tipped off). It tells the merchant in English or Hindi on her Soundbox and app, discreetly, because the Soundbox is heard by customers. It protects new payouts with two keys (merchant + Paytm Risk). It reads the police notice, ignores a hidden prompt-injection line, matches the one disputed payment in Paytm's records, and drafts a request in her name to freeze only the disputed amount, plus a tamper-evident signed evidence pack and Paytm's own nodal upload. It follows the bank's deadlines, and when the hold is limited it verifies the account with ₹1 before Paytm Risk releases her money. The same loop handles chargeback deadlines (it never invents proof of delivery), missed billing-app payments, fake payment screenshots, double charges and extortion calls.

**Three surfaces, one engine:** the Soundbox voice, a Kavach layer in Paytm for Business (a live "where is my money" tracker and one-tap decisions), and a Risk & Ops desk for Paytm staff, including triage of the daily settlement-return file, even messy ones.

**Measurable outcomes.** In one freeze case: noticed before anyone asked, merchant told in 6 seconds, about 12 systems used, every action re-checked at the source, 3 human decisions, money released after verification. In evaluation: 243/243 everyday incidents and 240/240 generated freeze and chargeback cases handled correctly, with 0 tip-offs and 0 invented evidence (synthetic; a shadow-mode pilot on Paytm's history is the next step). Bank, police and UPI switch are simulated and labelled; Paytm's Transaction Status API is called live.

---

## Technology Stack: databases, APIs, cloud etc.

- **Backend:** Python 3.12, FastAPI, Uvicorn; Server-Sent Events for live updates across all screens.
- **Agent engine:** a tool-using agent loop (interpret → plan → read tools → policy gate → act → re-verify at the source → follow-ups), with 20 explicit policy rules (two-key approvals, tipping-off guard, no rerouting during a freeze, no invented evidence, verified release).
- **Paytm integration:** Paytm Payments **Transaction Status API (v3/order/status)**, live on staging, signed with Paytm's official `paytmchecksum` library. Designed to plug into Paytm's settlement-return file, PSP response codes (UPI YE), dispute desk, settlement config, Paytm for Business notifications and Soundbox voice.
- **Evidence and trust:** ReportLab + pypdf for case PDFs, signed with **Ed25519** over the file hash (`cryptography`), and a public verifier page with a machine-readable JSON checklist for the bank's grievance officer; QR codes (`qrcode`).
- **Documents:** Tesseract OCR for screenshots and police notices (read as untrusted text, with prompt-injection detection).
- **Frontend:** vanilla JavaScript, no build step; Tailwind CSS v4, Lucide icons, Motion and Geist fonts (vendored so the demo runs offline); English and Devanagari Hindi throughout.
- **Data:** a simulated Paytm world (UPI switch, settlement engine, billing app, refunds, dispute desk, bank and police desk) kept in memory with a virtual clock. No external database in the prototype; production would read Paytm's own stores.
- **Optional integrations:** n8n webhooks for automations; Cognee for SOP retrieval.
- **Cloud and ops:** Docker container deployable to Railway or Render (always-on, for live streaming); pytest suite (53 tests) plus two evaluation harnesses (483 simulated cases) and a mutation test of the safety guard.

---

## AI/ML tools, models or pre-trained models used (Claude Code, Copilot etc.)

- **Sarvam AI (India's sovereign LLM stack):**
  - **Sarvam-105B:** tool-calling planner (OpenAI-style function calling, policy-gated) and SOP question answering with checked citations.
  - **Bulbul v3:** text-to-speech in Hindi and English for the Soundbox and app voice.
  - **Saaras v3:** speech-to-text for the merchant's voice notes.
- **Anthropic Claude:** supported as an alternative tool-use planner (`KAVACH_PLANNER=claude`).
- **Deterministic fallback:** a rules planner and a typo-tolerant Hindi/Hinglish/English interpreter, so money decisions never depend on a model and the demo never breaks if an API is down.
- **Tesseract OCR:** reads payment screenshots and police notices.
- **Claude Code:** used as our AI pair-programmer to build, test and red-team the project.

---

## Working Demo URL
`https://<your-railway-domain>/` (after deploying; see below). Also list the pages:
`/` projector view · `/m` merchant app · `/soundbox` · `/desk` Paytm Risk & Ops · `/world` simulator (customer, bank, police) · `/case` one case end to end.

## Working Demo Video Recording URL
Upload the screen recording (script below) to YouTube as **Unlisted** or to Google Drive with "Anyone with the link can view", and paste the link.

## GitHub/Code Repository URL
https://github.com/Aryanbhargava18/Kavach

---

# Getting the Demo URL (about 5 minutes)
```
npm i -g @railway/cli
railway login
cd kavach
railway init
railway up
railway domain
```
In the Railway dashboard → Variables: add `SARVAM_API_KEY`. Open the domain once to check it, and again a minute before judging (free plans sleep).

# The demo video (2–3 minutes, screen recording of `/` plus `/world` on a phone or a second window)
1. **0:00–0:20 · Problem.** Idle screen. Say: frozen accounts, nobody tells the merchant, ₹303 cr frozen vs ₹29 cr disputed, "Paytm knows first".
2. **0:20–0:35 · Live, not scripted.** On `/world`, as a customer, pay Meena ₹200: the Soundbox says "Received 200 rupees", and the payment appears in her app.
3. **0:35–1:20 · The freeze.** On `/world`, tap "Freeze Meena's account". Show: her app says Account frozen, the Soundbox says only "a message is waiting" (privacy), the tracker shows where money stopped. Tap "Yes, keep it safe" in the app; approve on Paytm's desk.
4. **1:20–1:50 · The case builds itself.** Forward the notice: 129× more frozen than disputed, request to hold only the disputed amount, signed pack.
5. **1:50–2:10 · 12 days later.** `/world` → "they decide": ₹1 check, approve, "Your account works again".
6. **2:10–2:35 · Proof.** Open `/case`: the outcome tiles and steps (Noticed, Decided, Acted, Verified, Human) answer the Track 3 brief.
7. **2:35–2:50 · Close.** "The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money."
