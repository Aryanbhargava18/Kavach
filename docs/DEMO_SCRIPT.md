# 3-minute demo script: five beats, one story

**Setup (before you walk up).**
1. Run `make lan` and open Chrome full screen at the LAN address it prints. If the venue Wi-Fi blocks device-to-device traffic, use a phone hotspot that the laptop and the judge's phone both join.
2. Turn the sound on, click the page once, press **Reset**.
3. Run `make sarvam-check` with the key in `.env`. If it fails, Kavach runs on its rules planner and the top bar says so. Don't hide that.
4. Open **Phone** in the top bar and keep the QR ready.
5. **Live Paytm check:** put `PAYTM_MID` and `PAYTM_MERCHANT_KEY` (staging) in `.env`, make one test payment on that MID before you walk up, and note its Order ID. Run `make paytm-check ORDER=<id>` once; it must print `OK: Paytm answered.` The top bar's **Paytm staging** chip lights up.

One person drives the laptop, one talks, and **the judge holds Meena's phone the whole time.**

---

**Beat 1 · 0:00 · The problem (15 s, idle screen)**
> "One ₹1,000 UPI sale froze a shop's whole ₹8.26 lakh account for ten months. I4C's own table: about ₹303 crore frozen against ₹29 crore actually disputed. And the shopkeeper finds out last, from a bounced supplier payment. Paytm finds out first, and today nobody acts on that."

Hand over the QR. The judge taps **Main Meena hoon · Shuru karo**. They're holding her Paytm for Business app with **Kavach Shield**: status, today's sales, the clocks Kavach is holding. It's not a chat.

**Beat 2 · 0:30 · Kavach knows first** (click **Meena's bank freezes her account**)
- The 9:00 payout bounces. Nobody typed anything. Kavach **checks Paytm Risk before saying a word** (a possible mule would get only a neutral line).
- **The judge's phone buzzes and speaks Hindi.** The app turns into a case card with a trust line: *Kavach kabhi OTP, PIN ya paise nahi maangta*.
- Judge taps **Haan, surakshit rakho**. The driver taps **Approve as Paytm Risk**. New sales are now safe with Paytm and never move to another account.

**Beat 3 · 1:00 · The case builds itself** (judge taps **Bank ka SMS + notice bhejo**)
- Kavach reads the notice, **ignores the instruction hidden in it**, matches the one ₹2,400 payment, signs the pack and drafts Paytm's own SOP 9.5(ii) upload.
- On the phone: **₹3,10,000 frozen, a sliver of ₹2,400 disputed, 129×.**
- Judge taps **Request taiyaar karo**, then **Bank ne complaint le li ✓**.
- *Optional, if a judge is curious:* **Signed evidence pack › Verify** on their phone → Valid; tap the edited copy → TAMPERED. Scroll to the bank officer's checklist.

**Beat 4 · 1:45 · Twelve days later** (Run a scenario → **⏩ 12 days later: the bank and the officer act**)
> "The bank and the officer are simulated. Watch what Kavach does with their decisions."
- Day 3: the bank files **through the bank desk**, inside the SOP's 7 days, so no escalation letter is needed.
- Day 12: the officer limits the hold to ₹2,400. **Kavach doesn't take that on trust**: it sends Paytm's ₹1 validation credit, and **CREDITS LAND**.
- The driver taps **Approve as Paytm Risk** to release.
- **The judge's phone turns green: "Account phir se chalu."** The held payouts are back in her account. Only the disputed ₹2,400 stays held, and both 90-day dates are on the clocks row.
> "In Sri Sai Wines, ten months and a High Court. Here the bank and the officer are simulated, so we're not claiming twelve days. What's real is that every step the SOP asks of the merchant and of Paytm was ready on day one, and Kavach checked the money before it moved."

**Beat 5 · 2:25 · What's live on Paytm today, every clock, and the business** (10–15 s each)
- Run a scenario → **LIVE: check a real Paytm order** → paste your staging Order ID. Kavach calls **Paytm's real Transaction Status API** twice, the UPI tile flips from SIMULATED to **LIVE · Paytm API**, and it signs a pack from Paytm's actual response. "Every tile says whether it's live or simulated. This one is Paytm, right now."
- Run a scenario → **Chargeback: a reply clock nobody is watching**. The phone shows what's proven (payment, bill) and **what isn't** ("no record can show the goods were handed over"). One question; the judge taps **Haan**; the reply goes in before the deadline. "It owns every clock that silently costs her money."
- Say it (no screen): "Priced per verified resolution, sold through Paytm Intelligence. 6.6 verified actions per incident, zero model calls in offline mode, and a shadow-mode rollout that proves it on Paytm's own history before any merchant hears from it."

**Close · 2:50**
> "The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money."

---

### Questions you'll get, and the screen that answers them
| Question | Show |
|---|---|
| "What if the merchant is the mule?" | Run a scenario → **Payout bounces, but Risk has mule signals**: neutral line, Soundbox shows PAYTM TEAM, the right panel becomes Paytm Risk's view |
| "What about a debit freeze?" | **Debit freeze: her payment to a supplier is refused**: caught from UPI code `YE` on her own payment |
| "How do you know it works?" | **Results**: 240 money-clock scenarios plus the break-the-guard test |
| "Couldn't it just lie to win a chargeback?" | P18: the phone's proof list shows the gap; tap **Nahi diya** → honest accept |
| "Is any of this real?" | **LIVE: check a real Paytm order**; the SIMULATED/LIVE tag under every tile |

### If something breaks
* **The phone can't connect:** the laptop's left phone is the same app; drive it there.
* **No sound:** tap the phone once. Captions still show on the laptop.
* **Sarvam down:** the rules planner takes over and says so.
* **Start over:** **Reset** (the judge's phone clears itself).
