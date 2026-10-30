# Partner integrations

Everything below is optional. Without keys Kavach runs fully offline and the top bar shows each one as "offline".

| Service | What Kavach uses it for | Turn it on |
|---|---|---|
| **Sarvam AI** | `sarvam-105b` plans with tool calling (same policy gate as offline). Saaras transcribes Meena's voice notes. Bulbul speaks Kavach's Hindi replies and the Soundbox. Vision reads screenshots and notice photos as a second reader next to Tesseract. Answers "Ask the SOP" questions from retrieved passages. | `SARVAM_API_KEY=sk_...` in `.env`. Check with `make sarvam-check`. |
| **n8n** | Delivers Kavach's events (follow-ups, approvals, escalation letters, EDD assignments). Kavach decides; n8n only delivers. | Import `n8n/kavach-followups.json`, add SMTP credentials to "Send email", activate, then set `N8N_WEBHOOK_URL=https://<your-n8n>/webhook/kavach`. |
| **Cognee** | Retrieval for "Ask the SOP" over the `kavach_sop` dataset. Citations are still checked against what was retrieved. | Run Cognee, set `COGNEE_URL` (and `COGNEE_API_KEY` for Cognee Cloud), then `make cognee-load` once. |
| **Claude** | Alternative planner (`KAVACH_PLANNER=claude`). | `ANTHROPIC_API_KEY=...` |

The n8n workflow is a starter: check node versions when you import it (Webhook v2, Code v2, Send Email v2.1).
