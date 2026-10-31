# Put Kavach online (about 5 minutes)

Kavach needs one always-on server (it keeps the demo world in memory and streams live updates), so use **Railway** or **Render**, not Vercel.

## Railway, straight from your laptop folder (no GitHub needed)
```
npm i -g @railway/cli
railway login
cd kavach
railway init            # create a new project
railway up              # builds the Dockerfile and deploys
railway domain          # gives you a public https address
```
Then in the Railway dashboard → your service → **Variables**, add:
- `SARVAM_API_KEY` = your key (for voice; leave out to use the browser's voice)
- `KAVACH_PLANNER` = `offline` (saves Sarvam credits; already the default)

Railway tells Kavach its own address automatically, so QR codes and links point to the right place.

## Render (if you prefer)
New → Web Service → deploy from a Git repo or a Docker image → it detects the Dockerfile. Add the same variables. Render also tells Kavach its address automatically.

## The addresses to share
| Who | Open |
|---|---|
| Projector / judges' laptop | `https://<your-domain>/` |
| Meena's app (judge's phone) | `https://<your-domain>/m` |
| Her Soundbox (spare phone) | `https://<your-domain>/soundbox` |
| The world: customer, bank, police (teammate's or judge's phone) | `https://<your-domain>/world` |
| Paytm's staff website | `https://<your-domain>/desk` and `/ops` |
| One case end to end | `https://<your-domain>/case` |

## Good to know
- **One shared demo world.** Everyone who opens the link sees the same shop. "Start over" resets it for everyone, so keep the World page with your team during judging.
- **Your key stays out of the code.** `.env` is excluded from the image (`.dockerignore`); the key lives only in the platform's Variables.
- **Free plans sleep.** Open the link a minute before you present so it wakes up.
