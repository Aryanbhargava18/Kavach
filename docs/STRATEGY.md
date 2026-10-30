# Kavach: what we are building, and why Paytm should care

## In one line
**Kavach is an agent that runs inside Paytm and catches a merchant's frozen bank account from signals only Paytm sees, before she finds out from a bounced supplier payment. It then works the case on both sides: Meena's, and the bank's.**

The website is not the product. It is a glass box that lets judges watch the agent work. The product has four surfaces:

| Surface | Who uses it | In the demo |
|---|---|---|
| Soundbox + Paytm for Business app | Meena, in Hindi | Live screen, and **a judge's own phone** (`/m`) |
| Paytm Risk console | Paytm Risk / EDD | Approve button, Risk desk view, mule guard |
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

## Who pays, and why (no invented numbers)
| Line | Mechanism | How to measure in a pilot |
|---|---|---|
| **Retention** | A frozen merchant whose payouts land in a dead account switches to cash or another QR. Warning her early and holding new sales safely keeps her on Paytm. | Churn of frozen merchants, Kavach vs control; GMV in the 30 days after the freeze |
| **Nodal ops cost** | Every reported-and-settled payment needs a 9.5(ii) upload. Kavach prepares the row from the settlement engine. | Minutes per upload before and after; error rate |
| **Support cost** | "Why didn't my payout come?" tickets get answered before they're raised. | Freeze-related tickets per 1,000 merchants |
| **Pi revenue (banks)** | Banks must check and submit grievances within 7 days, and most of I4C's table is pending. A signed, SOP-mapped case file is the input a bank-side Paytm Intelligence agent needs. | Bank turnaround time; first-pass acceptance; per-case or SaaS fee (to be priced by Paytm) |
| **Loan book (hypothesis)** | Merchant loans are repaid from settlements; payouts trapped in a frozen account hurt collections. Lending and payments sit in different entities, so this needs Paytm to confirm. | Collection rate on frozen merchants |

Merchants pay nothing.

**Scale anchor, not a forecast:** about 1.64 crore merchants on device subscriptions (Paytm Q2 FY27 results, 26 Oct 2026). What share face a freeze each month is a number only Paytm has. The pilot should measure it before anyone multiplies.

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
| Signing key | Paytm HSM | Demo Ed25519 key, fingerprint shown |

## Proof
- **Freeze watchers:** 180 scenarios from an independent generator, 180 pass:
  - caught 90/90 when Paytm has a signal;
  - 0 false alarms on healthy or blind accounts;
  - 0 tipping-off leaks;
  - 0 re-routes.
  - **Mutation test:** remove the planner's guard and P17 still blocks every leak. Remove both and 30/30 leak.
- **Everyday incidents:** 243 generated scenarios versus a screenshot-trusting bot (the existing evaluation).
- **43 automated tests.** All of this is synthetic: it validates logic and guardrails, not real-world detection rates.

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
