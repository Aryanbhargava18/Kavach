# Judge Q&A

**What is Kavach, in one sentence?**
An autonomous operations teammate for Paytm merchants. It notices when a payment succeeded at the bank but never reached the shop's billing system, fixes the shop's books safely, checks the fix, tells the merchant in Hindi, and stays on the case until the payout lands.

**Why is "nobody complained" the headline?**
Because that's the difference between a support bot and a teammate. A bot waits for a ticket. Kavach watches the delivery of payment updates to the merchant's POS. When a confirmed payment fails to arrive, it opens the case itself, investigates with tools, and has fixed it before the customer is at the counter arguing. Customer disputes, refunds, duplicates and freezes run through the same engine as other incident paths.

**Is the failure realistic?**
Yes. Payment-gateway webhooks to merchant systems time out, get 5xx errors and run out of retries. When that happens the money is real but the merchant's bill says unpaid, which is the classic "customer paid, shop says not received". In the demo the failure, the retries (HTTP 503, 503, 504) and the detection are **simulated**. In production, Kavach would read Paytm's real webhook delivery logs.

**What is real and what is simulated?**
- **Real, running code:** the agent loop, every tool call, the deterministic policy gate, post-action verification, follow-ups that wake on callbacks, OCR, the signed evidence pack with tamper detection, and (with a key) Sarvam speech, voice and planning.
- **Simulated:** Paytm's UPI switch, settlement engine, refund service and Soundbox. Also the shop's billing app, WhatsApp delivery, the Paytm Risk approval, and the bank and police.
- We never claim a Paytm connection. The top bar shows which integrations are live.

**Where is the AI, and where is it deliberately not?**
- **AI:** understanding Meena's Hindi or Hinglish voice (Sarvam Saaras); planning which tools to call and what to say (Sarvam-105B tool calling); speaking back in Hindi (Bulbul); reading screenshots and notices (OCR, plus Sarvam as a second reader where available).
- **Deliberately not AI:** deciding whether money moved, whether a bill can be marked paid, and whether an action is allowed. Those are deterministic rules that re-read the source systems themselves, because money decisions must never hallucinate.

**Can the model mark a bill paid on its own?**
Only through `reconcile_payment`, and only if the rules agree:
- the UPI switch says SUCCESS for this merchant;
- the reference isn't already in the ledger;
- no refund exists for it;
- it fits what's still due on that bill.

Then Kavach re-reads both systems and they must agree. It never moves money: no payouts, no refunds without the merchant's OK, and no re-routing during a freeze.

**What does it refuse, and why?**
- **Collecting again while a payment is pending:** that would charge the customer twice.
- **Counting money that's being refunded:** it is leaving, so it can't pay a bill.
- **Applying one payment to two bills.**
- **Receipting an edited screenshot.**
- **Building an evidence pack on a notice that contradicts Paytm's own record.**
- **Sending payouts to another account during a cyber-cell freeze.**

Each refusal shows on screen with the reason, and it never accuses the customer.

**How do you use Sarvam?**
- **Saaras:** speech-to-text when Meena talks.
- **Bulbul:** Kavach's Hindi voice and the Soundbox.
- **Sarvam-105B:** plans with tool calling, including the proactive hero, and answers SOP questions from retrieved passages with checked citations.
- **Vision:** used as a second reader of images where available. Sarvam's dedicated Vision product is a job-based document API, so a quick screenshot read falls back to OCR if the chat model won't take the image.
- **Fallback:** if any Sarvam call fails on stage, that case falls back to the rules planner, and the screen says so.

**Why not LangGraph or a React rebuild?**
- The loop is an explicit state machine you can read in one file.
- The 3D view is three.js, bundled locally so the demo runs offline.
- More frameworks would add demo risk without changing what the agent can do.

**What does the signed pack prove?**
Only that the PDF is byte-identical to what this Kavach instance issued. It is not a Paytm signature, not proof of innocence, and not court-admissible by itself. The verifier page says so.

**How do you know it works?**
- **Tests:** 37 automated tests cover the policy invariants, the proactive watcher, the hero and every challenge, tamper detection, and both LLM paths (scripted).
- **Evaluation:** 243 generated incidents, using a generator that never imports Kavach's decision code.
  - A screenshot-trusting bot marked 34 bills paid with money that was short, used or being refunded. Kavach marked none.
  - Kavach re-checked every one of its 1,509 actions.
  - It still misses 4 extortion phrasings, and we show them.
- This is synthetic evaluation; it isn't real-world accuracy.

**Business case for Paytm?**
- **Fewer tickets:** "customer paid, shop says no" tickets are deflected before they're raised.
- **Fewer double charges:** customers aren't charged twice.
- **Less cash fallback:** merchants who don't trust digital payments go back to cash, and that's lost GMV.
- **Same agent everywhere:** the same agent runs inside the AI Soundbox and the Paytm for Business app Paytm already ships.

Pilot metrics would be: missed-update incidents fixed before a complaint, time to fix, tickets deflected, double charges prevented, and payouts confirmed.

**What would production need?**
- Read access to switch status, settlement and webhook delivery logs.
- A ledger-repair endpoint on partner POS systems, or Paytm's own billing.
- Refund writes behind the same policy gate.
- Approved WhatsApp templates.
- A Paytm-held signing key in an HSM.
- Legal sign-off on the freeze workflow.
