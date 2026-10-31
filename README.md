# Kavach

**A proactive, voice-first AI teammate for Paytm merchants. It watches Paytm's own payment and payout signals and acts before the merchant complains. When her bank freezes her account over a cyber-fraud report and the next payout bounces, Kavach warns her in Hindi, protects new sales with a two-key hold, and builds an SOP-routed, signed case file. When a payment never reaches her billing app, it repairs the books, checks the fix, and follows up until the payout lands.**

Team Second Signal · Paytm Build for India AI Hackathon · Track 3: Autonomous AI Teammates
Everything here runs on synthetic data. No real money, messages, banks or police systems are touched, and Kavach never moves money.

---

## Live on Paytm (staging)
The read path runs on Paytm's real **Transaction Status API** (`v3/order/status`), signed with Paytm's official `paytmchecksum` library.
1. Paytm Business dashboard → Developer settings → test mode: copy the **MID** and **merchant key** into `.env` as `PAYTM_MID` and `PAYTM_MERCHANT_KEY` (`PAYTM_ENV=staging` is the default).
2. Make any test transaction on that MID and copy its **Order ID**.
3. `make paytm-check ORDER=<order id>` → must print `OK: Paytm answered.`
4. In the app: Run a scenario → **LIVE: check a real Paytm order**. The UPI tile shows **LIVE · Paytm API**; every other tile says **SIMULATED**, because payout returns, PSP decline codes and the dispute desk aren't open to outside developers.

Kavach never signs a pack unless Paytm's own API said SUCCESS, asked twice (rule P20). No keys means it says so; it never fakes a live answer.

## Start here

**Run it on your laptop (Mac or Windows), about one minute:**

```
cd kavach
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

It prints four addresses. Kavach is three products on one engine:

| Product | Who uses it | Open |
|---|---|---|
| **Soundbox** | Meena hears Kavach on the device she already trusts | `/soundbox` on a spare phone (tap once for sound) |
| **Merchant app** | Kavach Shield inside Paytm for Business | `/m` on the judge's phone |
| **Paytm staff website** | Risk & Ops approve anything that moves money; Ops triage the day's return file | `/desk` and `/ops` |

`/world` is the simulator: a teammate or judge plays the customer (pays, disputes), the bank (freezes) and the police (decides) from their own phone. `/case` shows one case end to end. To put it online, see `docs/DEPLOY.md`.

`http://localhost:8000/` shows all three side by side for the projector. Keys: **1** bank freeze, **2** chargeback, **3** missed bill, **→** skip ahead, **R** start over. Phones need the same Wi-Fi (or the laptop's hotspot).

* `docs/STRATEGY.md`: what this is, who at Paytm pays for it, where it plugs in, and what's still simulated.
* `docs/DEMO_SCRIPT.md`: the 3-minute run, with a judge holding Meena's phone (`make lan`, then **Judge's phone**).
* `docs/JUDGE_QA.md`: the hard questions, answered honestly.

**Kavach owns every clock that silently costs a merchant money.** What it catches on its own: a **chargeback reply deadline** (it proves the payment and the bill, never invents delivery, and asks Meena one question), a **total freeze** (the next payout bounces), a **debit freeze** (her own UPI payment through the Paytm app is declined `YE`), and neither when Paytm has no signal. It checks **Paytm Risk before warning anyone** (rule P17). It drafts **Paytm's own SOP 9.5(ii) upload** and **a request in Meena's name to limit the hold to the disputed amount**. The pack's verify page doubles as **the bank grievance officer's checklist**.

## The problem

Rahul pays Meena Kirana ₹4,200 by UPI. His bank says SUCCESS. Meena's billing app still shows the bill as unpaid, because Paytm's webhook to her POS failed three times. Rahul has a green screenshot; Meena has an unpaid bill; both are right about what they can see. Today this becomes a support ticket, an argument at the counter, or a second payment.

The same shape repeats with harder variants: the screenshot was edited (₹4,200 shown, ₹2,400 paid), the payment is still pending, the reference doesn't exist, the money arrived after the QR expired and is already being refunded, the same UTR is presented for a second bill, or the bank has frozen Meena's account over a cyber-fraud report.

## What Kavach does

One loop, the same for every incident: **understand → plan → use tools → reconcile → apply policy → act → verify → follow up or hand off.**

1. **Opens a case and loads the policy** for that kind of incident (`create_support_case`, `get_incident_policy`).
2. **Treats the screenshot as a claim.** It reads it (Tesseract and Sarvam vision as two independent readers) and never acts on it alone.
3. **Reconciles four systems** for the same payment: the UPI switch, the shop's POS ledger (with the webhook delivery log), the refund service and the settlement engine. Each lands as one row in the reconciliation grid.
4. **Applies a deterministic policy gate** (P1–P16) to every action, whichever planner proposed it. The gate re-reads the systems itself.
5. **Acts through tools**: repairs the ledger from the switch record (idempotent on UTR), replays the Soundbox, sends a verified receipt, asks for exactly the amount still due, refunds a proven duplicate once, holds payouts with two keys, builds a signed evidence pack.
6. **Re-verifies every action** against the source of truth. Nothing closes on an unverified outcome.
7. **Follows up on its own.** The hero case stays open until the next morning's payout includes the payment; it wakes on the settlement engine's callback, with a scheduled poll as backstop.
8. **Hands off** where a human must decide: Paytm Risk for holds and EDD, the bank and police for freezes.

## The hero, and the judge challenges

| What happened in Paytm's systems | What Kavach does |
|---|---|
| **Hero.** Meena's bank freezes her account (debit and credit) over a cyber-fraud report. Nobody tells Paytm. | At the next 9:00 run the payout comes back RETURNED. The payout watcher opens a case on its own, confirms the return code, warns Meena in Hinglish and on her Soundbox before her supplier payments bounce, tells her what to ask her branch for (NCRP ack number, notice, disputed amount), and proposes a two-key payout hold. When she forwards the notice, the same case reads it, matches the one disputed payment, routes it under the SOP, signs the pack, and shows disputed vs frozen. A debit-only freeze stays invisible to Paytm, and Kavach says so. |
| **Everyday.** Rahul paid ₹4,200; switch SUCCESS; POS webhook failed ×3 (HTTP 504) | Ledger row reads **MISSING**. Policy P16 allows a repair. Kavach posts the switch record into the ledger, re-reads both systems (exactly one entry for that UTR, bill PAID), replays the Soundbox, sends Rahul a verified receipt on WhatsApp, tells Meena in Hinglish, and schedules "confirm tomorrow's 9:00 payout". Next morning the settlement callback wakes it, the payout row turns **SETTLED**, and only then does it close. |
| Screenshot ₹4,200, switch ₹2,400 | Claim row struck through. Bill stays PARTIAL. QR for exactly ₹1,800 still due. Nobody is called a fraud (P8). |
| Payment still pending | "Collect again" is blocked (P1). Kavach watches the switch and receipts once when the bank confirms. |
| No such transaction | Switch row **NOT FOUND**. No receipt, goods held, polite ask for the full UPI reference. |
| Money arrived after the QR expired; auto-refund already running | Ledger repair **denied (P14)**: money that's leaving can't pay a bill. Fresh QR sent, refund tracked to the customer's account. |
| Same UTR presented for a second bill | Ledger shows the UTR **USED ON B-2210**. Repair denied (P15: one payment settles one bill). Fresh QR. |
| Real-looking screenshot, bank says FAILED | Switch row FAILED. Receipt denied, customer told the money will return, goods held. |
| Cyber-fraud account hold | Paytm can't see a debit freeze, and Kavach says so. Two-key payout hold (Meena + Paytm Risk), police notice read with prompt-injection ignored, one disputed ₹2,400 sale matched, SOP routing and clocks, signed PDF with a QR verifier. Re-routing payouts is refused (P6). |

Every row in that table is a scenario in the **Simulate** menu, and an eval family in `eval/`.

## The Live screen

The default view. Meena's phone on the left; in the centre her Soundbox with Kavach in it (three.js, bundled), wired to Paytm's simulated systems, which light up and send their real values to the Soundbox only when Kavach calls them; the billing app, the customer's WhatsApp or the case file on the right; the loop (Detect → Investigate → Reconcile → Act → Verify → Follow up) along the top; Hindi voice with a waveform and word-by-word subtitles; the result and presenter controls along the bottom. Start it with **Meena's bank freezes her account**: nobody complains, Kavach finds the bounced payout on its own. **Take a ₹4,200 payment** shows the same watcher on an everyday incident.

## The console

The trace view for anyone who wants to inspect every step. One screen, three panes:

* **Incident inbox** (left): every case with its customer, amount and state (investigating, watching, needs your OK, resolved, with a human).
* **Agent workspace** (centre): the customer's WhatsApp thread or Meena's chat, with each tool call shown inline as it runs (name, result, milliseconds, click for the raw JSON), policy blocks as red cards with the rule, approval cards with buttons, and a stage rail for the loop.
* **Payment intelligence** (right): the verdict, the **reconciliation grid** (Claim · UPI switch · Shop's ledger · Refund · Payout), the money at stake, what Kavach will do next and when, every change it made with how it checked, and SOP clocks for freezes.

A second view, the **Paytm Risk desk**, runs enhanced due diligence on a simulated CFCFRMS feed of frozen merchants. It escalates only on two or more independent signals, so a festival-season spike never lands in the EDD queue.

## What's in it

| Capability | How |
|---|---|
| Customer and merchant in their own words | WhatsApp-style thread (simulated delivery inside the 24-hour customer-service window); Meena by voice or text in Hinglish/Hindi |
| Voice | Sarvam **Saaras** speech-to-text and **Bulbul** speech (browser speech APIs offline) |
| Planning with tools | Sarvam **sarvam-105b** tool calling, Claude, or offline playbooks, all behind the same policy gate |
| Reading screenshots and notices | Tesseract OCR **and** Sarvam vision; disagreement is reported |
| Reconciliation | UPI switch, POS ledger + webhook log, refund service, settlement engine, Soundbox log |
| Repair | `reconcile_payment`: switch-confirmed, idempotent on UTR, refused if refunded, used elsewhere or more than the amount due |
| Follow-ups | Wake on the system's own callback (switch, refund, settlement), poll as backstop; every one also emitted as an **n8n** event |
| Account freeze | Notice reader, SOP routing, dated-event clocks, Ed25519-signed bilingual pack with QR verifier |
| Ask the SOP | Cognee (or local) retrieval + Sarvam answer; every citation checked against what was retrieved |
| Paytm Risk desk | Deterministic EDD on a simulated CFCFRMS feed |

Partner setup: `integrations/README.md`. Copy `.env.example` to `.env` and add keys; the top bar shows each integration live or offline.

## Run it

```sh
make demo          # http://127.0.0.1:8000
```

Needs Python 3.11+ and Tesseract OCR (`brew install tesseract`). Without Tesseract everything works except reading screenshots, and Kavach asks for the UPI reference instead. Chrome gives Hindi voice input and output through the browser; typing always works.

```sh
make test          # 50 tests: both proactive watchers (billing app, payouts), policy invariants, hero + every judge challenge, tamper detection, desk, clocks, both LLM paths (scripted)
make eval          # 243 everyday incidents + 800 desk merchants vs naive baselines, then 180 freeze-watch scenarios with a mutation check (≈3–4 min, offline)
make sarvam-check  # with SARVAM_API_KEY: one live call to each Sarvam API Kavach uses
make llm-check     # with SARVAM_API_KEY (or ANTHROPIC_API_KEY): hero scenarios on the live planner, safety + timing
make lan           # serve on the venue Wi-Fi so a judge's phone can scan the pack's QR
```

### Planner

* **No key:** deterministic playbooks. The top bar says *rules planner*. We don't call these AI.
* **`SARVAM_API_KEY`:** sarvam-105b plans with tool calling over the same tools. **`ANTHROPIC_API_KEY`:** Claude does (`KAVACH_LLM_MODEL`).
* Either way the model can only touch the world through the policy gate, and every action is re-verified. If the API fails mid-demo, that incident falls back to the playbook and the trace says so.

## How it's built

```
customer (WhatsApp, simulated) / Meena (voice or text)
        │
   understand.py ── interpreter (offline, or the LLM)
        │
   agent.py   Engine: understand → plan → tools → reconcile → policy → act → verify → follow up / hand off
        │             ├─ planner_offline.py   deterministic playbooks
        │             └─ llm.py               Sarvam / Claude tool-use planner (same tools, same gate)
        │
   tools.py   16 READ tools (switch, POS ledger, refunds, settlement, Soundbox, OCR, notice parser, SOP…)
              17 WRITE tools, every one through ─► policy.py (P1–P16, reads the world itself)
        │
   world.py   simulated Paytm: UPI switch, POS bills + ledger + webhook log, settlement engine (09:00 run),
              refund service, Soundbox, support cases, outbox, ops queue, virtual clock with callbacks
   shots.py   screenshot render + OCR     sop.py  MHA/I4C SOP routes + clocks
   proof.py   Ed25519-signed manifest binding the PDF's SHA-256; verifier with tamper/expiry checks
```

FastAPI + Server-Sent Events, vanilla JS with no build step, fonts bundled so the demo runs offline.

## What is real and what is simulated

| Real, running code | Simulated |
|---|---|
| Tool calls, the policy engine, post-action verification, follow-ups and callbacks | Paytm's UPI switch, settlement engine, refund service, Soundbox fleet and the shop's POS (`world.py`) |
| Ledger repair logic (idempotency, refund and reuse checks) | WhatsApp delivery (messages go to a local outbox) |
| OCR (Tesseract) and, with a key, Sarvam vision/STT/TTS/LLM | Paytm Risk approvals (a button) |
| Ed25519 signing, SHA-256 PDF binding, tamper detection | Bank and police systems; nothing is filed |
| SOP routing with paragraph citations (`docs/sop_rules.md`) | The demo signing key is not a Paytm key |

## Honest limits

* The evaluation is synthetic: it checks logic in a closed world, not real fraud detection. The naive bot is our own model of a screenshot-trusting assistant, so its column illustrates failure modes rather than measuring a product. `eval/results.json` lists the 4 scenarios Kavach still gets wrong: held-out extortion phrasings the offline interpreter misses ("ek banda bol raha hai paise transfer karo warna…").
* The offline interpreter is keyword-based and written by the same team as the test phrases, so its understanding score is optimistic. When it doesn't understand, Kavach asks rather than acting.
* The LLM planners are tested against a scripted API in this repo. Run `make llm-check` with a real key before using one on stage.
* WhatsApp replies assume the customer messaged first (Meta's 24-hour service window); anything later would need an approved template.
* The freeze workflow is not legal advice. Kavach never declares anyone innocent and never promises an unfreeze.
* Questions for Paytm mentors: is POS webhook delivery logged per attempt? Does Paytm receive CFCFRMS holds directly? Can PA settlement be held at merchant request?

## Licence and lineage

Written from scratch for this final. An earlier prototype was built on a public third-party repository with no licence; none of that code is used. Fonts: Anek Devanagari, IBM Plex Mono, Noto Sans Devanagari (SIL OFL) and DejaVu Sans (Bitstream Vera licence); licences are in `assets/` and `app/static/fonts/`.
