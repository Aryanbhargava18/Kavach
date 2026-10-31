# 3-minute demo script: five beats, one story

**Setup (before you walk up).**
1. Run `make lan` and open Chrome full screen at the LAN address it prints. If the venue Wi-Fi blocks device-to-device traffic, use a phone hotspot that the laptop and the judge's phone both join.
2. Click the page once (unlocks sound), press **R** to start over. The screen shows only three real surfaces: Meena's phone, her Soundbox, and Paytm's Risk & Ops desk. Demo controls sit in the dark dock at the bottom: **1** freeze, **2** chargeback, **3** missed bill, **→** skip ahead when time is the next thing, **R** reset. Keys work even after you tap the phone.
3. Optional: run `make sarvam-check` with the key in `.env` for Sarvam voices. Without it, Kavach runs on its rules planner and the browser voice.
4. For the judge's own phone, open `http://<laptop-LAN-IP>:8000/m` on it (printed by `make lan`).
5. **Live Paytm check:** put `PAYTM_MID` and `PAYTM_MERCHANT_KEY` (staging) in `.env`, make one test payment on that MID before you walk up, and note its Order ID. Run `make paytm-check ORDER=<id>` once; it must print `OK: Paytm answered.`

One person drives the laptop, one talks, and **the judge holds Meena's phone the whole time.**

---

**Beat 1 · 0:00 · The problem (15 s, idle screen)**
> "One ₹1,000 UPI sale froze a shop's whole ₹8.26 lakh account for ten months. I4C's own table: about ₹303 crore frozen against ₹29 crore actually disputed. And the shopkeeper finds out last, from a bounced supplier payment. Paytm finds out first, and today nobody acts on that."

Hand over the QR. The judge picks **English** or **हिन्दी** (they can switch any time with EN/हि). They're holding her Paytm for Business app with **Kavach Shield**: status, today's sales, the clocks Kavach is holding. It's not a chat.

**Beat 2 · 0:30 · Kavach knows first** (press **1**)
- The 9:00 payout bounces. Nobody typed anything. Kavach **checks Paytm Risk before saying a word** (a possible mule would get only a neutral line).
- **The Soundbox lights up and speaks** in her language; "What she heard" shows the words. The app turns into a case card with a trust line: *Kavach kabhi OTP, PIN ya paise nahi maangta*.
- Judge taps **Yes, keep it safe** on the phone. The case lands on **Paytm's desk** as "Your approval"; the driver clicks **Approve**: that's Paytm Risk's real job, not a demo button. New sales are now safe with Paytm and never move to another account.

**Beat 3 · 1:00 · The case builds itself** (judge taps **Send bank SMS + notice**)
- Kavach reads the notice, **ignores the instruction hidden in it**, matches the one ₹2,400 payment, signs the pack and drafts Paytm's own SOP 9.5(ii) upload.
- On the phone: **₹3,10,000 frozen, a sliver of ₹2,400 disputed, 129×.**
- Judge taps **Prepare the request**, then **The bank took my complaint ✓**.
- *Optional, if a judge is curious:* **Signed evidence pack › Verify** on their phone → Valid; tap the edited copy → TAMPERED. Scroll to the bank officer's checklist.

**Beat 4 · 1:45 · Twelve days later** (press **→**; the dock shows "12 days later")
> "The bank and the officer are simulated. Watch what Kavach does with their decisions."
- Day 3: the bank files **through the bank desk**, inside the SOP's 7 days, so no escalation letter is needed.
- Day 12: the officer limits the hold to ₹2,400. **Kavach doesn't take that on trust**: it sends Paytm's ₹1 validation credit, and **CREDITS LAND**.
- Paytm's desk asks for approval to release; the driver clicks **Approve**.
- **The judge's phone turns green: "Your account works again."** The held payouts are back in her account. Only the disputed ₹2,400 stays held, and both 90-day dates are on the clocks row.
> "In Sri Sai Wines, ten months and a High Court. Here the bank and the officer are simulated, so we're not claiming twelve days. What's real is that every step the SOP asks of the merchant and of Paytm was ready on day one, and Kavach checked the money before it moved."

**Beat 5 · 2:25 · What's live on Paytm today, every clock, and the business** (10–15 s each)
- Dock **⋯** → **Check a real Paytm order** → paste your staging Order ID. Kavach calls **Paytm's real Transaction Status API** twice, the UPI tile flips from SIMULATED to **LIVE · Paytm API**, and it signs a pack from Paytm's actual response. "Every tile says whether it's live or simulated. This one is Paytm, right now."
- Press **2** (customer disputes). The phone shows what's proven (payment, bill) and **what isn't** ("no record can show the goods were handed over"). One question; the judge taps **Yes, I handed them over**; the reply goes in before the deadline. "It owns every clock that silently costs her money."
- Say it (no screen): "Priced per verified resolution, sold through Paytm Intelligence. 6.6 verified actions per incident, zero model calls in offline mode, and a shadow-mode rollout that proves it on Paytm's own history before any merchant hears from it."

**Close · 2:50**
> "The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money."

---

### Questions you'll get, and the screen that answers them
| Question | Show |
|---|---|
| "What if the merchant is the mule?" | Dock ⋯ → **Bounce on a merchant Risk has flagged**: neutral line, Soundbox shows PAYTM TEAM, the right panel becomes Paytm Risk's view |
| "What about a debit freeze?" | Dock ⋯ → **Her payment to a supplier is refused**: caught from UPI code `YE` on her own payment |
| "How do you know it works?" | Dock ⋯ → **Evaluation results**: 240 money-clock scenarios plus the break-the-guard test |
| "Couldn't it just lie to win a chargeback?" | P18: the phone's proof list shows the gap; tap **No, I didn't** → honest accept |
| "Is any of this real?" | Dock ⋯ → **Check a real Paytm order**; every source row on Paytm's desk says Simulated or Live |
| "Show me the agent's reasoning" | Expand **Kavach's log** on Paytm's desk, or Dock ⋯ → **Engineer's view** |

### If something breaks
* **The judge's phone can't connect:** the phone on the laptop screen is the same app; drive it there.
* **No sound:** click the page once. "What she heard" still shows the words.
* **Sarvam down:** the rules planner takes over and says so.
* **Start over:** **Reset** (the judge's phone clears itself).
