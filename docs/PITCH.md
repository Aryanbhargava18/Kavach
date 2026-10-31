# Kavach: the full story, in plain words

> **"The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money."**

**In one breath:** when a small merchant's money gets stuck (her bank freezes her account, a customer disputes a payment, a payout bounces), she is the last to know and has nobody to help. Paytm usually knows first. Kavach is an AI agent inside Paytm that acts on what Paytm knows: it tells her in her language within seconds, protects her money, does the paperwork, and watches every deadline. It never moves money without her approval and Paytm Risk's.

---

## The brief, and how Kavach answers it

> *"Build AI teammates that don't just respond; they get the job done. How might we build an AI teammate that can independently handle a customer-service workflow end to end: resolving issues, taking actions across systems, and escalating to humans only when needed?"*

Kavach is that teammate for **Paytm's merchant customer service**. Paytm's customer is the merchant, and the most painful service issue a merchant has is money that's stuck.

| The brief asks for | What Kavach does | Where judges can see it |
|---|---|---|
| **Goes beyond answering questions** | Starts the work itself, from Paytm's own signals, before the merchant asks | Press 1: nobody typed anything, the case opens at 9:01 |
| **Understands context** | Reads the payout return, her payments, Risk signals, the police notice and the SOP before acting; answers vague questions ("when will it come?") from her actual records | Case story → "Understood" steps |
| **Makes decisions** | Decides what's safe: checks Risk before warning, refuses a notice that contradicts the record, picks the right SOP route | Case story → "Decided" steps, with the rule behind each |
| **Takes actions across systems** | Settlement engine, dispute desk, billing app, refund service, evidence signer, nodal queue, notifications, Soundbox: about 12 systems in one freeze case | Case story → "Systems it worked across" |
| **Works alongside humans** | Meena decides what's hers; Paytm Risk approves anything that moves money; the bank and police decide the freeze | Case story → "Humans in the loop" |
| **Escalates only when needed** | Asks a person only when money moves or only a human knows (did you hand over the goods?). Hands to a human queue only if it can't resolve | Case story → "Escalated to a person?" |
| **Measurable outcomes** | Time to notice, time to tell the merchant, actions taken and re-checked, human decisions needed, unsafe steps blocked, money protected; across 483 simulated cases | Case story → the outcome tiles; Evidence → evaluation results |
| **End to end** | From the first bounced payout to money back in her account, with follow-ups on its own | Case story: one case, every step, start to finish |

---

## 1. Who this is for

| Who | Their life today | What Kavach gives them |
|---|---|---|
| **Meena, the merchant** (kirana owner, Lucknow, takes UPI on a Paytm Soundbox, types in Hinglish, reads Hindi or simple English) | Money gets stuck and she doesn't know why, where it is, or what to do. She calls support, waits, gets scared, sometimes pays a scammer, sometimes goes back to cash. | A voice on her Soundbox and one screen in her app: what happened, where her money is right now, and the one thing she needs to do. |
| **Paytm Risk & Ops teams** | They see bounced payouts, disputes and fraud signals as rows in files and queues. Merchants call angry. Every human touch on a ₹500 problem loses money. | Cases that arrive already investigated, with evidence attached. They only approve the steps that move money. Two taps instead of a support call. |
| **The bank's grievance officer** | Gets vague complaints from merchants and has to work out what's verified. | A signed, checkable case file: what's proven, what's drafted, and what the bank itself still has to do. |
| **Paytm, the company** | Pays for support tickets, loses chargebacks to silence, loses merchants to cash, and needs AI products it can sell. | Fewer tickets, less money lost, merchants who stay digital, and a product to sell to banks through Paytm Intelligence (Pi). |

---

## 2. The problem, in depth

### 2a. The account freeze: the biggest one

**How it happens.** Someone is cheated online and reports it on the cyber helpline (1930). Police trace where the money went: it passes through several accounts in "layers". Banks are told to put holds on accounts in that chain. A small merchant ends up in the chain simply because a customer paid her for groceries with money that turned out to be part of a fraud, or with no link to the fraud at all.

**What goes wrong:**
1. **The whole account is frozen, not just the disputed amount.** A ₹2,400 dispute can lock ₹3 lakh.
2. **Nobody tells her.** No call, no SMS that explains anything. She finds out when her payment to a supplier bounces, or her daily payout doesn't arrive.
3. **She doesn't know the process.** Which branch, what to file, what number to quote, how many days the bank gets. The government's SOP exists, but no merchant has read it.
4. **Her money keeps flowing into the trap.** Paytm keeps sending her daily payouts to the frozen account, where she can't use them.
5. **Scammers fill the silence.** "Pay ₹20,000 and we'll withdraw the complaint."
6. **It drags on for months.** Many merchants give up on UPI and go back to cash.

**Proof this is real, not invented:**
- **Sri Sai Wines v. Union of India (Andhra Pradesh High Court, 2026):** one ₹1,000 UPI payment froze a shop's whole ₹8.26 lakh account for **ten months**. It took a High Court case to release it.
- **I4C's own grievance numbers (up to 30 June 2026):** about **₹303 crore frozen against ₹29 crore disputed**, roughly 10× more money locked than is actually under question. (Our sum of the published table, contested cases only.)
- **Courts keep saying "freeze the disputed amount, not the account":** Karnataka HC (March 2026), Kerala HC (May 2026), Allahabad HC (August 2026). Rajasthan HC disposed of 105 such petitions in one judgment.
- **The regulator is moving:** the Supreme Court asked the RBI for a rule in August 2026. The RBI's **draft** (September 2026) proposes holding only the suspected amount, a 60-day limit without police instruction, and telling the customer the reason and the officer. It's a draft, not law yet; we always say so.

### 2b. The key insight: Paytm knows first

The merchant finds out last. **Paytm often finds out first**, from two signals it already has:
1. **Her payout bounces.** Paytm sends the day's payout; her bank sends it back with a reason ("account frozen"). That lands in Paytm's settlement return file.
2. **Her own payment is declined.** When she pays a supplier through the Paytm app, her bank answers with code **YE** ("account blocked/frozen"). Paytm is her payment app, so it sees that code.

Today those signals sit in files. **Nobody acts on them for the merchant.** That is the gap Kavach fills.

If neither signal exists (a debit freeze and she hasn't paid anyone through Paytm), Kavach sees nothing and **claims nothing**. We test that silence too.

### 2c. The other "silent money clocks"

The same pattern (a deadline the merchant doesn't know about, a signal Paytm already has) shows up elsewhere:

| Clock | What silence costs her | Signal Paytm already has |
|---|---|---|
| **Chargeback reply deadline** | If nobody replies in time, the dispute is "deemed valid" and the money is deducted from her next payout. | Paytm's dispute desk |
| **Missed payment in the billing app** | The customer paid, but the bill still says unpaid: arguments, double collection. | The failed message (webhook) to her billing app |
| **Payout that never lands** | She doesn't know where her money is. | The settlement run and return file |
| **Bank's 7-day grievance window** | If the bank doesn't forward her complaint, the hold drags on. | Her dated branch acknowledgement |

### 2d. Why today's answers don't work
- **Support is reactive.** It waits for her to call, after the damage is done.
- **Chatbots answer but don't act.** They explain the policy; they don't protect her payout, gather evidence or track deadlines.
- **Banks don't explain.** The freeze is a compliance action; communication isn't their priority.
- **Generic "fraud alert" SMS teach merchants to distrust every alert,** so even a real warning gets ignored.

---

## 3. How Kavach solves it: six steps, every time

| Step | What it means | In the freeze case |
|---|---|---|
| **1. Watch** | Listen to Paytm's own signals, not just her messages. | Sees the payout bounce at 9:01 am. Nobody typed anything. |
| **2. Check before speaking** | Look at the records and Paytm Risk's signals before saying a word. | Confirms the return reason. Checks Risk: if she looks like a money mule, she gets only a neutral message and Risk decides. |
| **3. Protect** | Stop more money from getting trapped, with two keys. | Asks Meena "keep today's sales safe with Paytm?"; she taps yes; Paytm Risk approves. Payouts wait safely with Paytm, never sent to any other account. |
| **4. Act** | Do the paperwork she can't. | Reads the bank SMS and police notice, ignores a fake instruction hidden inside, matches the one disputed payment in Paytm's records, and drafts a request in her name to hold only the disputed amount. Drafts Paytm's own required upload for its nodal officer. |
| **5. Prove** | Back every claim with records anyone can check. | A signed evidence pack. Change one digit and verification fails. The bank's officer gets a checklist, not a story. |
| **6. Follow up** | Own the deadlines until it's actually fixed. | Reminds her on day 5 if the bank hasn't acted; when the officer limits the hold, sends ₹1 to check the account really works; only then does Paytm Risk release her money. |

**The AI's role is narrow on purpose.** The AI (Sarvam, India's language model) understands her messages and speaks in Hindi or English. Decisions about money go through fixed rules and two human approvals, and every action is re-checked against the real record afterwards. If the AI fails, the rules run on their own.

---

## 4. The three products

### Soundbox voice: for Meena at the counter
Her Soundbox already announces "₹500 received". Now it also says, in her language: *"Meena ji, your bank returned today's payout. Your account is frozen. Talk to your bank before paying any supplier."* Shopkeepers trust that device more than any SMS. The display shows "KAVACH ALERT".

### Merchant app (inside Paytm for Business): for Meena on her phone
- **Home = a live money tracker**, like order tracking: Collected → With Paytm → Your bank (tomorrow 9:00 am) → Confirmed by Kavach. It answers the most common question ("when will my money come?") before she asks.
- **What Kavach is watching:** payments, payouts and disputes, live.
- **Today's payments**, each checked with the bank.
- **When something breaks:** one clear status ("Account frozen"), the same tracker showing exactly where the money stopped and where it is now, and **one decision at a time** with a big button.
- **Ask about your money:** any phrasing, English or Hindi. "When it will come" gets "₹4,580 reaches your bank tomorrow at 9:00 am; I'll check it lands."
- Every alert says: *"This is inside your Paytm app. Kavach never asks for OTP, PIN or money."*

### Risk & Ops desk (website for Paytm staff)
- Each case arrives **already investigated**: when Kavach found it, how fast the merchant was told, the amount, how many checks it ran, how many unsafe steps it blocked.
- **"Your approval"** appears only when money would move. Approve or decline in one click.
- Evidence attached: the returned payout, disputed vs frozen, the signed pack, what each source system says (labelled live or simulated).
- **Today's return file:** Ops uploads the bank's daily file of bounced payouts, even a messy one. Kavach sorts every row by reason (frozen, dormant, closed, wrong IFSC, name mismatch). **Only real freezes become freeze cases**; the others get the right simple message. A million-payout day takes milliseconds.

---

## 5. The other cases it handles
- **Chargeback:** shows what Paytm's records prove (payment, bill) and **admits what they don't** (that the goods were handed over). Asks Meena one question, replies before the deadline, never invents proof.
- **Paid, but the bill says unpaid:** repairs the billing app from the bank's own record.
- **Fake screenshot** (₹4,200 on the picture, ₹2,400 at the bank): trusts the bank, not the picture. No receipt for money that didn't arrive.
- **Payment still pending:** doesn't ask the customer to pay twice; comes back when the bank decides.
- **Charged twice:** refunds the duplicate and checks the refund lands.
- **Extortion call:** "Don't pay. Report on 1930."
- **Possible money mule:** reveals nothing to the merchant; Paytm Risk decides.

---

## 6. Why it's safe
1. **Never moves money alone.** Holding or releasing needs Meena **and** Paytm Risk.
2. **Never tips off a fraudster.** Checks Risk signals before warning anyone.
3. **Never sends money to a new account during a freeze.**
4. **Never invents evidence.** No "goods delivered" claims she didn't make.
5. **Never trusts the notice over the record.** If the police notice's amount contradicts Paytm's record, it refuses to build on it.
6. **Re-checks every action** against the real system afterwards.
7. **Scam-proof wording** on every alert; the extortion pattern is caught.
8. **Private trouble stays private.** The Soundbox is a loudspeaker on the counter, so customers hear it. For a freeze or a dispute it says only *"an important message from Paytm is waiting in your app"*, and the display shows CHECK APP. Phone notifications hide the details too ("Important update about your money"), because family members and shop helpers see lock screens.
9. **Honest fallback:** if the AI is down, the rules run and the screen says so.

---

## 7. Why Paytm should build it
- **Fewer support tickets:** she knows before she calls.
- **Less money lost:** chargebacks are no longer lost just because nobody replied.
- **Merchants stay digital:** a frozen merchant who's helped doesn't go back to cash.
- **It protects Paytm's moat:** if Soundbox hardware becomes a commodity (NPCI is reportedly building a common back-end), **the intelligence behind it is what Paytm keeps.**
- **Something to sell:** Paytm says it wants applied AI for merchants, not chatbots, and plans to sell AI to banks through Pi. Kavach fits: priced per problem actually resolved, not per seat.
- **Cheap to run:** cost grows with problems, not merchants. About 1.64 crore merchants are on Paytm devices, but only bounced payouts with a freeze reason open a case. Decisions are rules (about 4 checks per case); the AI is used only for language.
- **Plugs into what exists:** the settlement return file, payment response codes, the dispute desk, Soundbox and the Paytm for Business app. Kavach reads from these and writes back through them, behind the same approval rules.

**How Paytm would roll it out:**
1. **Shadow mode:** run it on 90 days of Paytm's history with no merchant contact, and count what it would have caught and how early.
2. **Alerts only** to a small group of merchants.
3. **Actions with approvals.**
4. **One partner bank.**

---

## 8. What's real, what's simulated, what's tested
- **Real and working:** the agent, all its safety rules, English and Hindi, the Soundbox and app voice (Sarvam AI), signed evidence packs anyone can verify, the messy return-file triage, and a live call to **Paytm's real Transaction Status API** (staging keys).
- **Simulated:** the bank, the police, the UPI switch, the billing app and the 12 days. Labelled on screen.
- **Tested:** 243 everyday payment problems and 240 generated freeze and chargeback cases, all handled correctly; 0 times it tipped off a flagged merchant; 0 invented proof. These are simulations: they prove the logic, not real-world rates. The pilot measures those.

## 9. What it is not
- **Not a chatbot.** It starts the work before she asks. Chat is just one way in.
- **Not an unfreeze button.** Only the bank and police can unfreeze. Kavach gets the right paperwork in on day one, asks for only the disputed amount to be held, and checks the money before it moves.
- **Not a lawyer.** It drafts; Meena signs; the bank and police decide.

---

## 10. Hard questions, short answers
- **"Isn't this just a chatbot?"** No. It acts first, from Paytm's own signals: it opens the case, protects her money and tracks deadlines. A chatbot waits to be asked.
- **"What if the merchant is the fraudster?"** It checks Paytm Risk first and reveals nothing if there are signals. Humans decide.
- **"Why not just send an SMS?"** An SMS says "account frozen" and leaves her alone and scared. Kavach protects the next payout, builds the case and follows up until the money is back.
- **"Do banks accept this?"** The pack follows the government SOP, is signed and checkable, and lists what the bank itself owes. It makes the officer's job easier.
- **"How do you know it works?"** 483 simulated cases with zero safety failures, plus a live call to Paytm's real API. A shadow-mode pilot on real history is the next step.
- **"Can Paytm legally hold her payouts?"** Once her bank returns a payout, that money is already back with Paytm; sending it again every day just bounces again. The hold only stops that loop, with her consent and Paytm Risk's, and the money is never sent to a different account. The exact wording needs Paytm Legal's sign-off before launch; we say that openly.
- **"Won't the Soundbox embarrass her in front of customers?"** That's why it doesn't say what happened. It says a message is waiting; the details are on her phone.
- **"What about other languages?"** English and Hindi today. Sarvam's voice supports most major Indian languages, so adding Tamil, Marathi or Bengali means translating the message table, not rebuilding.
- **"What does it cost Paytm?"** Mostly rules (about 4 checks per case); the AI only for language; two Risk taps per freeze case.

## Close
> "Paytm knows first. Kavach makes sure Meena isn't the last to know, and that she keeps her money."
