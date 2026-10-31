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

## Render: free, no card, from the GitHub repo (recommended)
1. Go to **dashboard.render.com** → sign in **with GitHub**.
2. **New +** → **Blueprint** → pick the repo **Aryanbhargava18/Kavach** → **Apply**. Render reads `render.yaml` and builds the Dockerfile.
3. When it asks for `SARVAM_API_KEY`, paste your key (or leave it empty to use the browser's voice).
4. Wait for **Live** (first build about 5 minutes). Your link is `https://kavach-xxxx.onrender.com`.

Free Render services sleep after 15 minutes idle and take about a minute to wake: open the link before you present.

## Hugging Face Spaces: free, no card, by git push
1. On **huggingface.co** → **New Space** → name `kavach` → SDK **Docker** → **Blank** → **Create**.
2. Under **Settings → Variables and secrets** add a secret `SARVAM_API_KEY` (optional).
3. On your laptop:
```
cd ~/Downloads && git clone https://github.com/Aryanbhargava18/Kavach.git kavach-hf && cd kavach-hf
printf -- '---\ntitle: Kavach\nsdk: docker\napp_port: 8000\n---\n\n' | cat - README.md > README.tmp && mv README.tmp README.md
git commit -am "Hugging Face Space config"
git push https://huggingface.co/spaces/<your-hf-username>/kavach main --force
```
When git asks for a password, paste a Hugging Face **write** token (huggingface.co/settings/tokens). Your link is `https://<your-hf-username>-kavach.hf.space`.

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
