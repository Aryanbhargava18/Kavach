# 3-minute demo script

**Setup (before you walk up).**
1. Run `make lan`, not `make demo`, so phones on the venue Wi-Fi can reach the laptop. If the venue Wi-Fi blocks device-to-device traffic, use a phone hotspot that both the laptop and the judge's phone join.
2. Open Chrome full screen at the LAN address the terminal prints. Turn the sound on, click the page once, then press **Reset**.
3. Run `make sarvam-check` with the key in `.env`. The top bar should show **Sarvam** lit. If not, Kavach runs on its rules planner and says so. Don't hide that.
4. Click **Judge's phone** in the top bar and keep the QR dialog ready.

One person drives the laptop. One person talks. **The judge holds Meena's phone.**

---

**0:00 · Hook (idle screen)**
> "A shop took a ₹1,000 UPI payment. The customer was later named in a fraud case, and the shop's whole account, ₹8.26 lakh, was frozen for ten months. I4C's own table shows about ₹303 crore frozen against ₹29 crore actually disputed. And the shopkeeper finds out last, when her supplier payment bounces. Paytm finds out first. Nobody acts on that."

**0:20 · Give the judge Meena's phone**
Show the QR. The judge scans it and taps **Main Meena hoon · Start**.
> "You're Meena now. Keep the sound on."

**0:35 · Kavach notices first** (click **Meena's bank freezes her account**)
1. The clock jumps to the 9:00 payout run. Meena's bank sends the payout back. **Detect** lights up. Nobody typed anything.
2. The Soundbox shows CHECKING, then **checks Paytm Risk before saying a word**.
   > "If Risk already had two independent signals on this shop, Kavach would stay quiet. Telling a possible mule operator would tip them off."
3. **The judge's phone buzzes and speaks in Hindi:** don't pay suppliers yet; ask the branch for the NCRP number, the notice and the disputed amount.
4. The phone asks to hold new payouts with Paytm. **The judge taps "Haan, karo".** The driver clicks **Approve as Paytm Risk**.
   > "Two keys: hers and Paytm Risk's. The money stays with Paytm and never moves to another account."

**1:15 · The case builds itself** (judge taps **📎 Bank ka SMS + notice bhejo** on the phone)
1. Kavach reads the notice, **ignores the instruction hidden in it**, matches the one ₹2,400 payment, and refuses to go on if the amounts disagree.
2. It routes the case under the MHA/I4C SOP and drafts **Paytm's own SOP 9.5(ii) upload** for the nodal officer.
3. It signs the pack. On the case file: **₹2,400 disputed vs ₹3.1 lakh frozen, 129×.**
4. The phone asks: write to the bank, in her name, to limit the hold to ₹2,400? **The judge approves.**
   > "It cites the SOP, three High Courts and the RBI's September draft, labelled as a draft. She signs; the bank decides."

**1:55 · The bank's side, on the judge's phone** (judge taps **Signed pack · verify on this phone**)
1. Green: **Valid**. Tap **Check a copy with one digit changed**: red, **TAMPERED**.
2. Scroll to **For the bank's grievance officer**: what's signed, what's drafted, and what the bank still owes (CDD/EDD and the 7-day submission).
   > "This is the input a bank-side Paytm Intelligence agent reads. The merchant side keeps her on Paytm; the bank side is a Pi product."

**2:20 · Push it** (chips on the phone)
* **Payout doosre account mein** → refused (P6).
* **Caller ₹20,000 maang raha** → flagged as extortion; report to 1930.

**2:35 · Proof** (top bar **Results**)
> "180 freeze scenarios from a separate generator: caught 90 of 90 when Paytm has a signal, zero false alarms, zero leaks, zero re-routes. We also broke our own guard on purpose. Remove one layer and the policy still blocks every leak; remove both and 30 of 30 leak. So the test has teeth. All synthetic, and labelled."

**2:50 · Close**
> "The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money, and tells her before the bank does."

---

### If a judge asks "what about a debit freeze?"
Run a scenario → **Debit freeze: her payment to a supplier is refused**. Payouts still land, so the payout watcher is blind. But her own ₹18,000 payment through the Paytm app comes back `YE`, and Kavach opens the case from that. If neither signal exists, Kavach sees nothing and claims nothing.

### If a judge asks "what if she's a mule?"
Run a scenario → **Payout bounces, but Risk has mule signals**. Her phone gets one neutral line, the Soundbox shows PAYTM TEAM, and the case file turns into **Paytm Risk's view (Meena never sees this)**.

### If something breaks
* **The phone can't connect:** run the same flow on the laptop's left phone; everything mirrors.
* **No sound:** tap the phone screen once. Subtitles still show on the laptop.
* **Sarvam down:** the rules planner takes over and the top bar says so.
* **Start over:** **Reset** (the judge's phone clears itself).
