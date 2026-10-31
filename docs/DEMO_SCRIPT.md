# How to show Kavach: a 5-minute demo where the judges drive

**The idea:** the world is simulated (bank, police, UPI switch, billing app), because nobody can plug a real bank into a hackathon. **The agent is live.** Nothing it says is pre-recorded; it reacts to whatever happens. So don't just play a story: **let the judges push it, and let it respond.**

## Before you walk up (5 minutes)
1. On the laptop: `python run.py`. Open `http://localhost:8000/` full screen on the projector. Press **R** to start clean.
2. On your phone (or the judge's), open the `/m` address it prints; pick **English** or **हिन्दी**. That's Meena's app.
3. Optional: a second phone on `/soundbox` (tap once for sound). That's her Soundbox on the counter.
4. Sound on. Click the projector page once so audio works.

Two people: **one talks, one drives.** The judge holds the phone.

---

## 0:00 · The problem (40 s, idle screen, no clicking)

> "Meena runs a kirana store in Lucknow. A customer pays her ₹2,400 on UPI. Weeks later that money is reported as cyber fraud, maybe not even about her. Her bank freezes her **whole** account. Nobody tells her. She finds out when her payment to her supplier bounces.
>
> This is real. A shop in Andhra Pradesh had ₹8.26 lakh frozen for ten months over one ₹1,000 payment; it took the High Court to fix it. The government's own numbers show about ₹303 crore frozen against ₹29 crore actually disputed.
>
> Here's the thing: **Paytm usually knows first.** The moment her payout bounces back from her bank, Paytm sees it. Today, nobody acts on that."

## 0:40 · Set the rules of the demo (15 s)

> "Three screens: Meena's phone, her Soundbox on the shop counter, and Paytm's Risk desk. The bank, police and UPI switch are a simulator, because no one can connect a real bank at a hackathon. Kavach itself is not scripted. It watches that simulator exactly the way it would watch Paytm's files. **Please try to break it.**"

## 0:55 · Kavach notices first (40 s): press **1**

What the judges see:
- The bank sends Meena's ₹4,580 payout back. **Nobody typed anything.**
- Within seconds, her phone shows **"Account frozen"**, and the tracker shows exactly where her money stopped.
- The Soundbox says only *"an important message from Paytm is waiting in your app"*.

> "Notice what the Soundbox *didn't* say. It's a loudspeaker on her counter, and customers are standing there. Private trouble stays on her phone."

## 1:35 · The judge decides (40 s)

The phone asks: *"Keep today's sales safe with Paytm?"*

> "Your call. You're Meena."

- **If the judge taps No:** Kavach respects it and doesn't hold anything. Say: *"It never moves money without her."* (Press **R** and **1** to go again if you need the full story.)
- **If Yes:** the case jumps to Paytm's desk as **"Your approval"**. Click **Approve**: *"This is Paytm Risk's real job. Two keys: the merchant and Paytm. The AI can't move money alone."*

## 2:15 · The case builds itself (40 s)

Judge taps **Send bank SMS + notice** on the phone.
- Kavach reads the notice, **ignores a fake instruction hidden inside it**, and matches the one disputed payment in Paytm's records.
- The phone shows: **₹3,10,000 frozen for a ₹2,400 dispute, 129 times more.**
- It drafts a request, in her name, to freeze only the disputed amount, plus a signed evidence pack.

> "Change one digit in that pack and verification fails. The bank's officer gets proof, not a story."

The judge taps **Prepare the request**, then **The bank took my complaint**.

## 2:55 · Twelve days later (30 s): press **→**

> "The bank and police are simulated; watch what Kavach does with their decision."
- The officer limits the hold to ₹2,400. **Kavach doesn't trust that blindly:** it sends ₹1 to check the account works.
- The desk asks for approval to release; click **Approve**.
- The phone turns green: **"Your account works again."**

## 3:25 · Prove it isn't scripted (60 s): the most important minute

Pick two:
- **"Ask it anything, in your own words."** The judge types on the phone, any phrasing, English or Hindi: *"paisa kab aayega"*, *"is my money safe"*, typos included. It answers from her actual records, not a script.
- **"Upload a messy file."** Open **Today's return file →** on the desk. Download the sample, mess it up in front of them (rename columns, write a sentence instead of a code), and upload it. It still sorts every row; only real freezes become cases.
- **"Fake proof."** Dock **⋯** → *Screenshot ₹4,200, bank says ₹2,400*: it trusts the bank, not the picture.
- **"Real Paytm."** If staging keys are in `.env`: Dock **⋯** → *Check a real Paytm order*. That's Paytm's actual API, live.

## Show the whole case in one screen (30 s): this is the brief, answered
On Paytm's desk click **Open the full case story** (or Dock **⋯** → *Case story*). Ideally keep it open on a second screen during the demo; it updates live.

> "This is the one case we just ran, end to end, straight from the engine's log. It noticed at 9:01 before anyone asked, told Meena in 6 seconds, used 12 systems, took 8 actions and re-checked every one, and asked a human only 3 times, only when money moved. Filter by Decided, Acted, Human: every step, who did it, which system it touched."

Point at the tiles while you say the brief's words: **understands context, decides, acts across systems, works with humans, escalates only when needed, measurable outcomes.**

## 4:25 · The second deadline (20 s): press **2**

> "Freezes aren't the only silent clock. A customer disputes a payment; if nobody replies in time, the money is deducted automatically."
- Kavach shows what Paytm can prove and **admits what it can't** (that the goods were handed over). The judge answers one question; it replies before the deadline.

## 4:45 · Why Paytm (15 s, say it, no screen)

> "Fewer support calls, fewer chargebacks lost to silence, merchants who stay digital, and an AI product Paytm can sell to banks. The way to make it real: run it in shadow mode on 90 days of Paytm's own data, no merchant contact, and count what it would have caught."

## Close
> "The Soundbox tells a shop it got paid. Kavach makes sure it keeps the money."

---

## Saying "simulated" without losing the room
- Say it **once, early, confidently**, as a rule of the demo, not an apology.
- Then put the live parts where judges can touch them: **their own words, their own file, their own decision.**
- If asked "is the data real?": *"The shop and the bank are simulated; the agent's decisions are live. The path to real data is shadow mode on Paytm's history. That's step one of the rollout."*

## If something breaks
- **Phone won't connect:** use the phone on the projector screen; it's the same app.
- **No sound:** click the page once; "What she heard" shows the words anyway.
- **Anything weird:** press **R**, then **1**. Ten seconds to restart.
- **Sarvam slow or down:** Kavach falls back to its rules and keeps going.
