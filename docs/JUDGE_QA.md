# Judge Q&A

**What is Kavach, in one sentence?**
An autonomous teammate for Paytm merchants that notices trouble in Paytm's own payment and payout signals before the merchant complains. The headline case: her bank freezes her account over a cyber-fraud report, the next payout bounces, and Kavach warns her, protects new sales with two keys, and builds an SOP-routed, signed case file. Everyday incidents (a billing app that missed a payment, a pending payment, a double charge) run through the same engine.

**Why lead with the account freeze?**
- **Stakes.** A ₹1,000 payment froze ₹8.26 lakh for ten months in *Sri Sai Wines v. Union of India* (AP HC, WP 969/2026). I4C's own table to 30 Jun 2026 shows about ₹303 crore frozen against ₹29 crore disputed. That ratio is our sum of its rows, over contested cases only, not proof about any one account.
- **A signal only Paytm has.** The payout return code. The merchant's bank doesn't tell her it froze credits; she finds out when a supplier payment fails.
- **It's what we were shortlisted on.** The finals version adds the proactive watcher, the two-key hold and the signed pack.

**How does Paytm know before the merchant does?**
Every night Paytm pays out yesterday's sales. If the merchant's bank refuses the credit, the payout comes back with a return code. Kavach watches those returns. In the demo the return code (`SYN-ACCT-FROZEN`) is **synthetic**, modelled on IMPS/NEFT "account blocked/frozen" returns.

**And when Paytm can't see it?**
A **debit-only** freeze leaves credits flowing, so payouts keep landing in an account she can't withdraw from, and Paytm sees nothing. Kavach doesn't pretend: it starts from Meena's report, says on screen that Paytm can't see the freeze, and proposes the same two-key hold. A test asserts the watcher stays silent in that case.

**Isn't warning the merchant "tipping off" a suspect?**
- Kavach tells her only what Paytm itself observed: her payout came back. The bank sends her an SMS about the freeze anyway.
- It never shares complainant or victim details (SOP 9.1(ii)), and payer handles are masked in everything merchant-facing.
- In production, a merchant already in Paytm Risk's EDD queue (repeat reports, fan-in) would get a generic, Legal-approved message instead. We'd want Risk to own that rule.

**Doesn't the payout hold help a mule account?**
The opposite. The hold keeps money *inside* Paytm's settlement balance and needs both the merchant and a Paytm Risk human. Moving payouts to another account during a freeze is refused (rule P6), and that refusal is on screen. Suspicious patterns go to the Risk desk's EDD, not to the merchant.

**Why not just fix the webhook retries for the billing-app case?**
Paytm should, and that's the first fix. But delivery to a merchant's own POS will always fail sometimes (their server, their network). Kavach owns the gap that's left: it confirms from the switch record, repairs once, re-checks and closes only after the payout lands. It's the small, frequent sibling of the freeze case.

**Is the billing-app failure realistic?**
Yes. Payment-gateway webhooks to merchant systems time out, get 5xx errors and run out of retries. In the demo the failure, the retries (HTTP 503, 503, 504) and the detection are **simulated**. In production, Kavach would read Paytm's real webhook delivery logs.

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
- **Tests:** 39 automated tests cover the policy invariants, both proactive watchers (billing app and payouts), the hero and every challenge, tamper detection, and both LLM paths (scripted).
- **Evaluation:** 243 generated incidents, using a generator that never imports Kavach's decision code.
  - A screenshot-trusting bot marked 34 bills paid with money that was short, used or being refunded. Kavach marked none.
  - Kavach re-checked every one of its 1,605 actions.
  - It still misses 4 extortion phrasings, and we show them.
- This is synthetic evaluation; it isn't real-world accuracy.

**Business case for Paytm?**
- **Keeps merchants digital after a freeze:** the shop that loses ₹3 lakh to a freeze goes back to cash. Warning her early and keeping new sales safe with Paytm is retention.
- **Keeps loan repayments flowing:** merchant loans are repaid from settlements. A held-with-Paytm payout is better than one bouncing between banks. (A hypothesis to confirm with Paytm; lending and payments sit in different entities.)
- **Fewer tickets:** "customer paid, shop says no" tickets are deflected before they're raised.
- **Fewer double charges:** customers aren't charged twice.
- **Less cash fallback:** merchants who don't trust digital payments go back to cash, and that's lost GMV.
- **Same agent everywhere:** the same agent runs inside the AI Soundbox and the Paytm for Business app Paytm already ships.

Pilot metrics would be: freezes caught before the merchant reports them, time from payout return to merchant warning, missed-update incidents fixed before a complaint, time to fix, tickets deflected, double charges prevented, and payouts confirmed.

**What would production need?**
- Read access to switch status, settlement and webhook delivery logs.
- A ledger-repair endpoint on partner POS systems, or Paytm's own billing.
- Refund writes behind the same policy gate.
- Approved WhatsApp templates.
- A Paytm-held signing key in an HSM.
- Legal sign-off on the freeze workflow.

## Questions about the latest build

**How do you catch a debit freeze, if payouts still land?**
From her own payments. When Meena pays a supplier through the Paytm app, Paytm is her PSP and sees her bank's response. A debit freeze comes back as UPI code `YE`, which PSP documentation (for example PhonePe's) describes as "remitting account blocked/frozen". Kavach opens the case from that. If she hasn't paid anyone through Paytm and payouts aren't bouncing, Paytm sees nothing, and Kavach claims nothing. The evaluation tests that silence (20 scenarios, 0 false alarms).

**What if the merchant is the mule?**
Kavach checks Paytm Risk before it says a word. With two or more independent signals (repeat reports, fan-in), Meena gets one neutral, Legal-approved line, her Soundbox shows "PAYTM TEAM", nothing is held on her say-so, and the case goes to Paytm Risk's EDD queue. Two layers enforce this: the planner, and policy rule P17, which refuses any message with case details. We proved each layer matters by breaking them on purpose: with one layer removed there were still 0 leaks; with both removed, 30/30 leaked.

**Isn't that unfair to a genuine merchant with two signals?**
It delays her, and that's a real cost. It's a human's call, not a verdict, and Risk owns the SLA. The alternative, telling a mule operator which account is under watch, costs victims money.

**Why would a bank listen to Meena's letter?**
Because it asks for what the courts and the regulator already point to: hold the disputed amount, not the account. The letter cites the MHA/I4C SOP, Karnataka HC (27 Mar 2026), Kerala HC (21 May 2026, WP(C) 31951/2024) and Allahabad HC (Aug 2026). It also cites the RBI's draft KYC (Amendment) Directions, 2026, labelled as proposed and not in force. Its figures come from Paytm's record, and Kavach re-checks them before she sees the letter. It's a draft she signs, not legal advice.

**What does Paytm itself get out of this?**
- **Retention:** a frozen merchant stays on Paytm instead of going back to cash.
- **Lower nodal ops cost:** Kavach drafts Paytm's own SOP 9.5(ii) settlement upload.
- **Fewer tickets.**
- **A Pi product for banks:** the bank's grievance desk gets a signed, SOP-mapped checklist plus JSON (open any pack's verify page).

`docs/STRATEGY.md` has the full table, and says which numbers only Paytm can supply.

**Why not just build this inside the bank?**
Because the bank doesn't see the sale. Paytm sees the counter, the settlement trail and, for its own app users, the decline code. The bank sees one credit line. The bank-side desk is something Paytm sells, not something the bank already has.

**Is the RBI rule in force?**
No. The draft was released on 11 Sep 2026 and comments closed on 2 Oct 2026. Kavach labels it as a draft everywhere it appears. The SOP and the High Court orders are what apply today.

## The money clocks

**What is Kavach, in one sentence, now?**
It owns every clock that silently costs a Paytm merchant money: account freezes, chargeback reply deadlines, the bank's 7-day grievance window, T+1 payouts and refunds. It catches each one from Paytm's own records, proves what the records prove, asks the merchant only what only she knows, and acts before the deadline.

**Why chargebacks?**
Paytm's own documentation says refunds and chargebacks are netted from settlements, and a chargeback is deemed valid if the merchant doesn't reply in time. A kirana owner doesn't watch a dispute desk, so silence costs her money. In the demo the deadline is synthetic and the desk is simulated.

**Couldn't Kavach just win more disputes by saying the goods were delivered?**
That would be inventing evidence in her name. Kavach files only items backed by a Paytm record (the switch record and her bill). It says plainly that the Soundbox only proves the notification played. A handover goes in only if Meena says so, labelled as her statement. If she says she didn't hand over the goods, Kavach accepts the chargeback. Rule P18 enforces this, and the evaluation checks it: 0 invented proof and 0 replies filed without her in 60 chargeback scenarios.

**How would Paytm make money from this?**
As a Paytm Intelligence operations module, priced per verified resolution, not per seat. Paytm uses it on its own merchant base first, then sells it to banks and acquirers. The decisions are deterministic and the model only handles language, so it can run on a small model; offline mode makes no model calls.

**Isn't this a chatbot with extra steps?**
Meena's app has no chat on its main screen. It shows a status, where her money is, the clocks Kavach is holding, and one next step, with chat as an optional side sheet. Every money decision is a rule that re-reads Paytm's records, every action is re-verified, and a mutation test proves the guardrails are load-bearing.

