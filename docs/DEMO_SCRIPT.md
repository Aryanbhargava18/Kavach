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
Show the QR. The judge scans it and taps **Main Meena hoon · Shuru karo**. They now hold Meena's Paytm for Business app with **Kavach Shield**: a status card, today's sales, what Kavach has already fixed. It's not a chat.
> "You're Meena now. Keep the sound on."

**0:35 · Kavach notices first** (click **Meena's bank freezes her account**)
1. The clock jumps to the 9:00 payout run. Meena's bank sends the payout back. **Detect** lights up. Nobody typed anything.
2. The Soundbox shows CHECKING, then **checks Paytm Risk before saying a word**.
   > "If Risk already had two independent signals on this shop, Kavach would stay quiet. Telling a possible mule operator would tip them off."
3. **The judge's phone buzzes, a push banner drops in, and it speaks in Hindi.** The app turns into a case: **Account freeze**, caught at 9:01 "before anyone told you", with the money map and a tracker.
4. **Aapka agla kadam:** hold new sales with Paytm? **The judge taps "Haan, surakshit rakho".** The driver clicks **Approve as Paytm Risk**. On the phone, "Nayi sale surakshit" ticks green.
   > "Two keys: hers and Paytm Risk's. The money stays with Paytm and never moves to another account."

**1:15 · The case builds itself** (judge taps **Bank ka SMS + notice bhejo** on the phone, or photographs a printed notice with **📷 Photo kheecho**)
1. Kavach reads the notice, **ignores the instruction hidden in it**, matches the one ₹2,400 payment, and refuses to go on if the amounts disagree.
2. It routes the case under the MHA/I4C SOP and drafts **Paytm's own SOP 9.5(ii) upload** for the nodal officer.
3. It signs the pack. **On the judge's phone the money map fills in: ₹3,10,000 frozen, a sliver of ₹2,400 disputed, "129× zyada", and what's safe with Paytm.** The tracker ticks through Notice and Case.
4. Next step: **Bank ko request: hold sirf ₹2,400 tak.** **The judge taps "Request taiyaar karo".** The letter appears under *Aapke documents*. Tap it to read it.
   > "It cites the SOP, three High Courts and the RBI's September draft, labelled as a draft. She signs; the bank decides."

**1:55 · The bank's side, on the judge's phone** (judge taps **Signed evidence pack › Verify**)
1. Green: **Valid**. Tap **Check a copy with one digit changed**: red, **TAMPERED**.
2. Scroll to **For the bank's grievance officer**: what's signed, what's drafted, and what the bank still owes (CDD/EDD and the 7-day submission).
   > "This is the input a bank-side Paytm Intelligence agent reads. The merchant side keeps her on Paytm; the bank side is a Pi product."

**2:10 · A second clock: the chargeback** (Run a scenario → **Chargeback: a reply clock nobody is watching**)
> "Freezes are the dramatic clock. The everyday one is this. A customer's bank raises a chargeback. If nobody replies in time, Paytm's process treats it as valid and nets it from her payout."
1. The phone shows **Chargeback · ₹960**, a countdown, and **what's proven**: the UPI switch record (T1) and her bill (T1). Then **what isn't**: "Saman diya gaya — koi record yeh nahi dikha sakta."
   > "The Soundbox only proves the notification played. Kavach will not invent delivery proof. Rule P18 refuses it even if a model tries."
2. One question: **Kya aapne saman diya tha?** The judge taps **Haan**: the reply goes in before the deadline, with her statement labelled as hers. (If they tap **Nahi diya**, Kavach accepts the chargeback rather than file a false reply.)
3. Point at the **clocks row**: next payout, chargeback reply, refunds. "Every clock that silently costs her money. Kavach holds all of them."

**2:20 · Push it** (the judge taps **Poochiye** and picks a question)
* **Payout doosre account mein bhej do** → refused (P6).
* **Ek aadmi 20 hazaar maang raha hai…** → flagged as extortion; report to 1930.
* Back on the main screen, tap **Kal branch jaiye → Bank ne complaint le li ✓**: the action card becomes a **7-day countdown** that Kavach will chase on its own.

**2:35 · Proof** (top bar **Results**)
> "240 scenarios from a separate generator, freezes and chargebacks: caught 150 of 150 when Paytm has a signal, zero false alarms, zero leaks, zero replies filed without Meena, zero invented proof. We also broke our own guard on purpose. Remove one layer and the policy still blocks every leak; remove both and 30 of 30 leak. So the test has teeth. All synthetic, and labelled."

**2:50 · Close**
> "The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money. It owns every clock that silently costs her, priced per verified resolution, sold through Paytm Intelligence."

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
