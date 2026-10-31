# Kavach: what to say to mentors and judges

## In one breath

When a bank freezes a small shopkeeper's account, nobody tells her. Paytm usually finds out first, but nobody acts on it. **Kavach is an AI agent inside Paytm that acts on it.** It warns her in her language within seconds, keeps her money safe, and builds her case. It never moves money without her approval and Paytm Risk's.

> **"The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money."**

---

## 1. The problem (tell it as a story)

Meena runs a kirana store in Lucknow and takes UPI on her Paytm Soundbox. One customer pays her ₹2,400. Weeks later, someone reports that money as cyber fraud, maybe not even about her.

Her bank freezes her **whole account**, not just the ₹2,400.

- **Nobody tells her.** She finds out when her payment to her supplier bounces.
- Her daily payouts from Paytm keep bouncing too. She doesn't know where her money is.
- She doesn't know the rules: who to call, what to file, how many days the bank gets.
- Scammers call: "pay ₹20,000 and we'll withdraw the complaint."
- Often she gives up on digital payments and goes back to cash.

**This really happens. Two facts to quote:**
- **Sri Sai Wines (Andhra Pradesh High Court, 2026):** one ₹1,000 UPI payment froze a shop's whole ₹8.26 lakh account for **ten months**. It took a High Court case to fix.
- **The government's own grievance numbers** (I4C, up to June 2026): about **₹303 crore frozen against ₹29 crore actually disputed**, roughly ten times more money locked than is under question. (This is our sum of the published table, contested cases only.)

## 2. The gap nobody owns

Paytm *sees* the problem first: the moment Meena's bank sends her payout back, Paytm knows something is wrong. Today that signal sits in a file. Nobody tells Meena, nobody protects her next payout, nobody helps her through the process.

It's not just freezes. Every merchant has **clocks that silently cost money**:
- **A chargeback** (customer disputes a payment): if nobody replies by the deadline, the money is deducted from her payout automatically.
- **A payment the billing app missed**: the customer paid, but the bill still says unpaid.
- **A payout that never lands.**

Paytm's own documents put these deadlines on the merchant. **Nobody watches them for her. Kavach does.**

## 3. What we built: three products on one engine

| Product | Who | What it does |
|---|---|---|
| **Soundbox voice** | Meena, at the counter | Speaks the alert in Hindi or English on the device she already trusts |
| **Merchant app** (inside Paytm for Business) | Meena, on her phone | Shows where her money is, like a delivery tracker, and asks for her decision with one tap |
| **Risk & Ops desk** (website for Paytm staff) | Paytm Risk and Ops teams | Each case arrives with the evidence already gathered; staff approve anything that moves money; Ops triage the day's file of payouts banks sent back |

It works in English or Hindi, chosen on the first screen, the way Indian apps do.

## 4. The demo: five moments

1. **Kavach notices first.** The bank sends Meena's ₹4,580 payout back. Nobody typed anything. Within seconds her Soundbox speaks and her app shows "Account frozen".
2. **Two keys protect her money.** Kavach asks: "Keep today's sales safe with Paytm?" Meena taps yes; Paytm Risk approves on the desk. New money stays safe with Paytm and is never sent to another account.
3. **The case builds itself.** She forwards the bank SMS and police notice. Kavach reads it (and ignores a fake instruction hidden inside), matches the one disputed payment, and shows her: **₹3,10,000 frozen for a ₹2,400 dispute, 129 times more.** It drafts a request, in her name, to freeze only the disputed amount, and a signed evidence pack that fails verification if anyone changes a digit.
4. **Twelve days later** (simulated bank and police): the officer limits the hold to ₹2,400. Kavach doesn't take that on trust: it sends ₹1 to check the account really works, and only then does Paytm Risk release her money.
5. **The chargeback clock.** A customer disputes a payment. Kavach shows what Paytm's records prove (the payment, the bill) and admits what they don't (that the goods were handed over). It asks Meena one question and replies before the deadline.

**Ask it anything:** "when will it come?" gets "₹4,580 from today's 8 payments reaches your bank tomorrow at 9:00 am. I'll check it lands."

## 5. Why it's safe (judges will push on this)

- **It never moves money on its own.** Holding or releasing money needs Meena **and** Paytm Risk.
- **It checks Paytm Risk before saying a word.** If the merchant shows fraud signals (a possible money mule), Kavach doesn't reveal the case. She gets a neutral "Paytm team will contact you" and Risk decides.
- **It never invents evidence.** In a chargeback it won't claim the goods were delivered unless Meena says so.
- **It re-checks everything at the source.** After every action it checks the real record again.
- **Scam-proof messaging.** Every alert says "Kavach never asks for OTP, PIN or money". "Pay to withdraw the complaint" calls get "Don't pay, report to 1930."
- **If the AI fails,** a rules engine takes over and the screen says so.

## 6. Why Paytm cares

- **Fewer support tickets:** the merchant knows what happened before she calls.
- **Less money lost:** chargebacks no longer lost just because nobody replied in time.
- **Merchants stay digital:** a frozen merchant who gets help doesn't go back to cash.
- **Something to sell:** Paytm says it wants applied AI for merchants, not chatbots, and plans to sell AI to banks through **Paytm Intelligence (Pi)**. Kavach fits that, priced per problem actually resolved.
- **It scales cheaply:** cost grows with problems, not merchants. Paytm has about **1.64 crore** merchants on devices, but only the payouts that bounce with a freeze reason open a case. A full day's return file triages in milliseconds.
- **It plugs into what Paytm already has:** the settlement return file, payment response codes, the dispute desk, Soundbox and the Paytm for Business app.

## 7. Be honest about what's real

- **Real:** the agent and its safety rules, both languages, the voice (Sarvam AI), the signed evidence packs, Paytm's real Transaction Status API (with staging keys).
- **Simulated:** the bank, the police, the UPI switch and the billing app. Everything simulated is labelled on screen.
- **Tested:** 243 everyday payment problems and 240 generated freeze and chargeback cases, all handled correctly; 0 cases where it tipped off a flagged merchant. These are simulations: they prove the logic, not real-world rates.

## 8. Hard questions, short answers

- **"Isn't this just a chatbot?"** No. It acts before anyone asks: it watches Paytm's own signals, opens the case, protects the money and tracks deadlines. Chat is just one way she can ask.
- **"What if the merchant is the fraudster?"** It checks Paytm Risk first and reveals nothing if there are signals. Risk decides, not the AI.
- **"Can it unfreeze accounts?"** No, only the bank and police can. It gets her the right paperwork on day one, asks for only the disputed amount to be held, and checks the money before it moves.
- **"Why would Paytm build this?"** Fewer tickets, fewer chargeback losses, merchants who stay digital, and an AI product to sell through Pi.
- **"How do you know it works?"** 483 simulated cases with zero safety failures, plus a live call to Paytm's real API.

## Close

> "Paytm knows first. Kavach makes sure Meena isn't the last to know, and that she keeps her money."
