# 3-minute demo script · Live screen

**Setup.** Run `make demo` and open Chrome at http://127.0.0.1:8000, full screen and at least 1280 px wide. Turn the sound on, then click the page once so Chrome lets it play audio. Press **Reset**. One person drives and one person talks.

**Before going on stage.** Run `make sarvam-check`, which needs your key in `.env`. The top bar should show **Sarvam** lit and **sarvam planner**. If the check fails, Kavach still runs on its rules planner and says so in the top bar. Don't hide that.

**The screen**
- Left: Meena's phone, where she talks to Kavach.
- Centre: her Soundbox with Kavach inside, wired to Paytm's systems. Each system lights up, and its real value flies to the Soundbox, only when Kavach actually checks it.
- Right: the other side of the story: the shop's billing app, the customer's WhatsApp, or the case file.
- Top: the loop: Detect, Investigate, Reconcile, Act, Verify, Follow up.
- Bottom: the result, plus presenter buttons that move the simulated world forward.

Everything in Paytm's systems on this screen is a **simulation**. Say so once, early.

---

**0:00 · Hook (over the idle screen)**
> "Every day, payments succeed at the bank but never reach the shop's billing app. The Soundbox says ₹4,200 received, the bill still says unpaid, and the argument starts. Kavach is an AI teammate that is on duty for the shop. Watch what happens when nobody complains."

**0:10 · Hero: Kavach notices first** (click **Take a ₹4,200 payment**)
1. The Soundbox announces ₹4,200 and a real value flies in from the UPI switch. On the right, bill B-2209 says **Unpaid**.
2. A few seconds later the loop lights up **Detect**. Kavach saw the failed delivery to the billing app on its own. Point out that nobody has typed anything.
3. **Investigate** and **Reconcile**: the UPI switch says success ₹4,200, the billing app says no entry, there's no refund, and the payout isn't due until 9:00 tomorrow. Each value flies to the Soundbox as it comes back.
4. **Act**: Kavach repairs the ledger, and the bill on the right flips to **Paid**.
   > "It only does this because the bank's own record says SUCCESS, the reference isn't used anywhere else, and no refund exists. Those are deterministic rules, not the model's opinion."
5. **Verify**: it re-reads both records and the Soundbox shows **FIXED ✓**. Meena's phone gets a Hinglish note and the Soundbox *speaks it in Hindi*, with the waveform and a word-by-word subtitle.
6. The bottom line reads: *"Fixed in N s, before anyone complained."*
7. Click **Skip to tomorrow's 9:00 payout**. The settlement run wakes Kavach, and it confirms the money reached Meena's bank before closing the case.

**1:05 · Challenge it** (bottom right **Run a scenario**; let a judge pick)
* **Screenshot ₹4,200, bank says ₹2,400.** The customer tile turns red. The bill stays part-paid, Priya gets a QR for exactly ₹1,800, and nobody is called a fraud.
* **Payment still pending.** Type on Meena's phone: *"Customer se dobara pay karwa do"*. Kavach refuses, **Act · refused**, because a second payment would charge the customer twice. Then press **Bank confirms ₹4,200**: Kavach wakes on the bank's callback and receipts once.
* **Same payment shown for a second bill.** The billing app shows that reference already paid an earlier bill, so Kavach refuses.
* **Refund already on its way back.** The repair is refused because money that is leaving can't pay a bill. Press **Skip … refund service credits the customer**, and Kavach confirms the refund and closes.
* **Reference that doesn't exist.** The UPI switch has no such payment. The goods stay on the shelf.

**2:05 · The case we were shortlisted for: cyber-fraud account hold** (Run a scenario → **Bank froze Meena's account**)
1. Kavach says plainly that Paytm can't see a debit freeze, then asks for **two keys**. Tap **Haan, karo** on Meena's phone, then **Approve as Paytm Risk** at the bottom.
2. Tap **📎 Meena forwards the bank notice**. The case file shows the notice and a signed evidence pack. An instruction hidden in the notice is ignored. Open **Verify it**.
3. Tap **Payout doosre account mein**. Kavach refuses: moving money during a cyber-cell freeze could look like evading a lawful order.

**2:35 · Talk to it** (if time allows)
Hold the mic on Meena's phone and ask *"Kal ka paisa kab aayega?"* Sarvam Saaras transcribes it, and Kavach answers from the settlement engine and says it out loud.

**2:45 · Proof** (top bar **Results**)
> "We generated 243 incidents in a simulator. A bot that trusts screenshots marked 34 bills paid with money that was short, already used, or being refunded. Kavach marked none, and re-checked every one of its 1,509 actions against the records. These are synthetic tests, and the 4 cases it still gets wrong are listed."

**2:55 · Close**
> "The Soundbox tells a shop it got paid. Kavach makes sure the books agree, before anyone has to complain."

---

### If something breaks
* No sound: click the page once (Chrome autoplay). Subtitles and the waveform still show.
* Sarvam or Wi-Fi down: the case falls back to the rules planner and the top bar says so. Typing works if the mic doesn't.
* **Console** (top) shows every tool call, policy decision and verification as a trace. **Systems** shows the simulated switch, billing app, payouts and message outbox.
* Start over: **Reset**.
