# Kavach: what we are building, and why Paytm should care

## In one line
**Kavach owns every clock that silently costs a Paytm merchant money.** It catches the deadline from Paytm's own records, does the work it can prove, asks the merchant only what only she knows, and acts before the clock runs out.

| Clock | What silence costs | Signal Kavach watches | Demo |
|---|---|---|---|
| Account freeze | Payouts trapped or bounced; supplier payments fail | Payout returns; her own UPI payment declined `YE` | Hero |
| Chargeback reply deadline | Deemed valid; netted from her T+1 payout | Paytm dispute desk | Beat 2 |
| Bank's 7-day grievance window | The hold drags on | Her dated branch acknowledgement | Inside the freeze case |
| T+1 payout | Money not where she expects it | Settlement run | Clocks row |
| Refund to a customer | Disputes, repeat tickets | Refund service | Clocks row |

It is **applied AI, not a chatbot**. Decisions about money are deterministic and re-verified against Paytm's records. A model is used only for language (Hindi in, Hindi out). That is why it can run on a small model, and in offline mode it makes no model calls at all. Meena's app shows a status, where her money is, the clocks, and one next step; chat is a small side sheet.

The product has five surfaces:

| Surface | Who uses it | In the demo |
|---|---|---|
| **Kavach Shield** inside Paytm for Business (+ Soundbox voice) | Meena, in Hindi | Same app on stage and on **a judge's own phone** (`/m`) |
| Paytm Risk console | Paytm Risk / EDD | Two-key approval, mule guard |
| Paytm dispute desk | Paytm disputes ops | Chargeback reply with record-backed evidence |
| Paytm nodal queue | Paytm's PA nodal officer (SOP 9.5(ii)) | Draft row in the ops queue |
| Bank grievance desk | The bank's grievance officer | `/verify/<token>` on any phone |

## The problem, sharpened
- One ₹1,000 UPI sale froze a shop's whole ₹8.26 lakh account for ten months (*Sri Sai Wines v. Union of India*, AP HC, WP 969/2026).
- I4C's own grievance table to 30 Jun 2026 shows about ₹303 cr frozen against ₹29 cr disputed (our sum of its rows, contested cases only).
- Courts keep saying "hold the disputed amount, not the account": Karnataka HC (27 Mar 2026), Kerala HC (21 May 2026), Allahabad HC (Aug 2026). The Rajasthan HC disposed of 105 writs in one judgment (20 Aug 2026).
- The Supreme Court (4 Aug 2026) told the RBI to frame a mule-account SOP. The RBI's draft KYC (Amendment) Directions, 2026 (11 Sep 2026) propose debit holds on the suspected amount by default, account-level holds as a last resort, a 60-day cap absent police instruction, and that the customer be told the reason, the removal process and the officer's contact. **It is a draft, not in force** (one report says from 1 Apr 2027).

**The insight:** the merchant finds out last. Paytm finds out first, from its own payout return file or from her own UPI payment coming back with code `YE`. Nobody acts on that today.

## What Kavach does that a chatbot can't
1. **Notices first, from Paytm-only signals.**
   - Total freeze: the next payout bounces. Kavach watches the settlement engine.
   - Debit freeze: payouts still land, but her own payment through the Paytm app is declined `YE` ("remitting account blocked/frozen", as PSP docs describe it). Kavach watches her PSP responses.
   - Debit freeze with neither signal: Kavach sees nothing and **claims nothing**. The evaluation tests that silence.
2. **Checks Paytm Risk before saying a word.** With two independent Risk signals, a warning could tip off a mule operator. So Meena gets only Legal's neutral message, and her Soundbox shows "PAYTM TEAM". Paytm Risk decides. Two layers enforce this: the planner, and policy rule P17. The mutation test proves each layer matters.
3. **Protects new sales with two keys.** Payouts are held in Paytm's settlement balance with Meena's and Paytm Risk's approval. They are never moved to another account (P6).
4. **Builds the case from the record, not from the notice.** It reads the notice as untrusted text, ignores the injected instruction, and matches the one disputed payment. If the notice's amount contradicts Paytm's record, it refuses. Then it routes under the MHA/I4C SOP and signs the pack (Ed25519 over the PDF's SHA-256).
5. **Asks for the hold to shrink.** It drafts a request in Meena's name to limit the hold to the disputed amount and to tell her the reason, the officer and the removal process. The letter cites the SOP, three High Courts and the RBI draft, labelled as proposed. She approves it, and Kavach re-checks the letter's amount and UTR against the switch record.
6. **Does Paytm's own paperwork.** SOP 9.5(ii) says a payment aggregator uploads the settlement details when a reported payment was already settled. Kavach drafts that row from the settlement engine for the nodal officer to approve. It never uploads.
7. **Hands the bank a checklist, not a story.** The verifier page shows the bank's grievance officer what is signed, what is drafted, and what the bank itself still owes (CDD/EDD, the 7-day submission). There's also a machine-readable JSON.

## Why Paytm, and why now (as reported; check before quoting)
- Paytm says it wants **applied AI for merchants, not another chatbot**, and plans to **sell AI** through Paytm Intelligence (Pi) to banks, lenders and insurers.
- A voice bot that merely talks isn't new to Paytm: its in-house Indic model reportedly already runs collections and retention calls. What's missing is an agent that **acts on records, under rules, against a deadline**.
- Payments margin is reported at "comfortably above 4 bps", which is about ₹1.68 on a ₹4,200 payment. Any human touch on an incident wipes that out. Kavach takes about **4–6 verified actions per incident** in our synthetic evaluation, with zero model calls in offline mode.
- NPCI is reportedly building a common Soundbox back-end. If the speaker becomes a commodity, **the software behind it is what Paytm keeps**. Kavach Shield is that software.
- Paytm's own docs hand merchants a reconciliation job with deadlines: T+1 settlement, refunds and chargebacks netted from payouts, and a chargeback deemed valid if the merchant doesn't reply in time. We found nobody owning that job for the merchant.

## Who pays, and how it's priced (no invented numbers)
| Line | Mechanism | How to measure in a pilot |
|---|---|---|
| **Per verified resolution (Pi module)** | Priced per resolved clock, not per seat: a chargeback answered in time, a freeze case filed, a hold scoped. Sold to banks and other acquirers through Pi; used by Paytm itself first. | Resolutions per month; cost per resolution vs a human agent |
| **Merchant money kept** | Chargebacks no longer lost to silence; payouts not trapped in a frozen account | ₹ of chargebacks deemed valid for no reply, before vs after |
| **Retention** | A frozen merchant stays digital instead of going back to cash | Churn and GMV of affected merchants, Kavach vs control |
| **Nodal ops cost** | Paytm's own SOP 9.5(ii) upload is drafted from the settlement engine | Minutes per upload; error rate |
| **Bank-side product** | The bank's grievance officer gets a signed, SOP-mapped checklist plus JSON | Bank turnaround; first-pass acceptance |

Merchants pay nothing.

**Scale anchor, not a forecast:** about 1.64 crore merchants on device subscriptions (Paytm Q2 FY27). How many freezes and chargebacks they see each month is data only Paytm has. The pilot measures it before anyone multiplies.

## Where it plugs into Paytm
| Kavach piece | Paytm system | Demo status |
|---|---|---|
| Payout watcher | Settlement engine return file (NEFT/IMPS "account frozen" returns) | Simulated; synthetic return code |
| PSP watcher | Paytm UPI app responses for the merchant's own payments (`YE`) | Simulated |
| Voice | AI Soundbox and the Paytm for Business app; Sarvam Saaras/Bulbul | Live with a Sarvam key; browser voice otherwise |
| Two-key hold | Settlement config + Paytm Risk console | Simulated approval |
| Mule guard | Paytm Risk EDD signals, CFCFRMS feed | Simulated signals |
| 9.5(ii) upload | PA nodal team → CFCFRMS | Draft in the ops queue |
| Bank desk | Paytm Intelligence (Pi) for banks | Verifier page + JSON |
| Chargeback clock | Paytm dispute desk (target; Paytm's agent/MCP tools not verified by us) | Simulated desk, synthetic deadline |
| Signing key | Paytm HSM | Demo Ed25519 key, fingerprint shown |

## Proof
- **Money clocks:** 240 scenarios from an independent generator, all passing.
  - Freezes and chargebacks caught 150/150 when Paytm has a signal.
  - 0 false alarms on healthy or blind accounts.
  - 0 tipping-off leaks; 0 re-routes.
  - 0 chargeback replies filed without Meena; 0 invented delivery proof.
  - **Mutation test:** remove the planner's guard and P17 still blocks every leak. Remove both and 30/30 leak.
- **Everyday incidents:** 243 generated scenarios versus a screenshot-trusting bot.
- **45 automated tests.** All synthetic: this validates logic and guardrails, not real-world detection or dispute win rates.

## What we need from Paytm to make it real
1. Read access to the settlement return file and to PSP response codes for merchants' own payments.
2. The Risk signal feed used for EDD.
3. A Legal-approved neutral template and a Risk SLA for guarded cases.
4. A nodal-officer review step for 9.5(ii) drafts.
5. An HSM signing key.
6. One bank partner for the Pi grievance desk pilot.

## Honest limits
- `YE` is described this way in PSP documentation (for example PhonePe's). We could not read NPCI's own code list from here.
- A debit freeze with no payout return and no declined payment is invisible to Paytm. Kavach says so.
- The RBI directions are a draft. The High Court positions are summarised from reporting and judgments, not legal advice. Kavach drafts; Meena signs; the bank and the police decide.
- Under the mule guard, a genuine merchant who happens to have two Risk signals gets a slower, vaguer message. That cost is real. The Risk SLA is what keeps it short.
