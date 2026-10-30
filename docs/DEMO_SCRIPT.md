# 3-minute demo script · Live screen

**Setup.** Run `make demo` and open Chrome at http://127.0.0.1:8000, full screen and at least 1280 px wide. Turn the sound on, then click the page once so Chrome lets it play audio. Press **Reset**. One person drives and one person talks.

**Before going on stage.** Run `make sarvam-check`, which needs your key in `.env`. The top bar should show **Sarvam** lit and **sarvam planner**. If the check fails, Kavach still runs on its rules planner and says so in the top bar. Don't hide that.

**The screen**
- Left: Meena's phone, where she talks to Kavach.
- Centre: her Soundbox with Kavach inside, wired to Paytm's systems. Each system lights up, and its real value flies to the Soundbox, only when Kavach actually checks it.
- Right: the other side of the story: the case file, the shop's billing app, or the customer's WhatsApp.
- Top: the loop: Detect, Investigate, Reconcile, Act, Verify, Follow up.
- Bottom: the result, plus presenter buttons.

Everything in Paytm's systems on this screen is a **simulation**. Say so once, early.

---

**0:00 · Hook (over the idle screen)**
> "A shop in Andhra Pradesh took a ₹1,000 UPI payment. The customer was later named in a cheating case in Bihar, and the shop's whole account, ₹8.26 lakh, was frozen for ten months until the High Court called it illegal. That's not rare: I4C's own table shows about ₹303 crore frozen against ₹29 crore actually disputed. And the shopkeeper usually finds out last, when a supplier payment bounces."

**0:20 · Hero: Kavach notices first** (click **Meena's bank freezes her account**)
1. The clock jumps to the next 9:00 payout. Meena's bank sends it back. **Detect** lights up: *"Meena's bank just sent her payout back."* Nobody has typed anything.
   > "Only Paytm sees this signal: the payout return code. Meena doesn't know yet."
2. **Investigate**: Kavach checks the payout and what Paytm can see of her bank. The Soundbox shows **ACCOUNT FROZEN**. The case file on the right shows the returned payout.
3. Meena's phone gets a Hinglish warning, and the Soundbox *says it out loud in Hindi*: don't pay suppliers yet. Then the three things to ask her branch for: the NCRP acknowledgement number, the police notice, and the disputed amount.
4. **Act, with two keys**: Kavach asks to hold new payouts with Paytm. Tap **Haan, karo** on Meena's phone, then **Approve as Paytm Risk** at the bottom.
   > "It can't do this alone. Meena and a Paytm Risk human both approve, and the money stays in Paytm's settlement balance. It never moves to another account."
5. Tap **📎 Meena forwards the bank notice**. Kavach reads it, **ignores the instruction hidden in it**, finds the one disputed ₹2,400 payment in Paytm's records, and checks that the facts agree. It routes the case under the MHA/I4C SOP and builds a **signed evidence pack**.
6. Point at the case file: **Disputed vs frozen, 129×**: ₹2,400 disputed (Paytm record) against ₹3.1 lakh frozen (Meena's own figure, marked unverified).
7. Bottom line: *"Meena warned in N s, before her first supplier payment bounced."* Open **Verify it** on the pack; the tampered copy fails.

**1:40 · Push it** (tap the chips on Meena's phone)
* **Payout doosre account mein.** Refused: moving money during a cyber-cell freeze could look like evading a lawful order.
* **Caller wants ₹20,000.** Flagged as extortion: nothing in the SOP involves paying anyone. Report to 1930.
* **Bank ne complaint le li ✓.** The bank's 7-day clock starts from her dated acknowledgement, never from her message to Kavach. Kavach will remind her on day 5 and draft a letter on day 7.

**2:05 · Same engine, everyday incidents** (Run a scenario → **A payment comes in; the billing app misses it**)
> "The same watcher catches small things too." The billing app misses a ₹4,200 payment; Kavach repairs bill B-2209 from the UPI switch record, re-checks it, and tells Meena. *"Fixed in N s, before anyone complained."*

If a judge wants more: **Screenshot ₹4,200, bank says ₹2,400** (QR for exactly the ₹1,800 still due, nobody called a fraud) or **Payment still pending** (type *"Customer se dobara pay karwa do"*; refused, because the customer would be charged twice).

**2:35 · Proof** (top bar **Results**)
> "We generated 243 incidents in a simulator. A bot that trusts screenshots marked 34 bills paid with money that was short, already used or being refunded. Kavach marked none, and re-checked every one of its 1,509 actions. These are synthetic tests, and the 4 cases it still gets wrong are listed."

**2:50 · Close**
> "The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money, and tells her before the bank does."

---

### The honest limit (say it before a judge does)
Paytm only sees a freeze when the bank also refuses credits, so the payout comes back. A **debit-only** freeze stays invisible: payouts keep landing in an account she can't withdraw from. For those, Kavach starts from Meena's report (Run a scenario → **Bank froze Meena's account**) and says on screen that Paytm can't see it.

### If something breaks
* No sound: click the page once (Chrome autoplay). Subtitles and the waveform still show.
* Sarvam or Wi-Fi down: the case falls back to the rules planner and the top bar says so. Typing works if the mic doesn't.
* **Console** (top) shows every tool call, policy decision and verification as a trace. **Systems** shows the simulated switch, billing app, payouts and message outbox.
* Start over: **Reset**.
