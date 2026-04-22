# Bourbon Alerts

Automated monitor for bourbon lotteries, drops, and auctions. Sends push notifications via [ntfy.sh](https://ntfy.sh) and includes a web dashboard.

## Sources

- **Virginia ABC** — lottery events (primary)
- **Reddit** — r/bourbon, r/dcwhisky, r/VirginiaAlcohol (drops only, no reviews)
- **Breaking Bourbon** — release press releases
- **Unicorn Auctions** — active auction lots
- **Seelbachs** — online bourbon retailer (ships to VA)
- **Whisky Auctioneer / Caskers** — disabled (UK-only / doesn't ship to VA)

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLite, httpx, curl_cffi, APScheduler
- **Frontend**: React + Vite + Tailwind (deployable to Vercel)
- **Notifications**: ntfy.sh

## Setup

### Backend

```bash
pip install -e .
cp config.example.yaml config.yaml
# Edit config.yaml: set your ntfy topic + admin topic

# First run — seed the DB without sending notifications
python -m src.main --seed

# Run the scheduler (scrapes at configured intervals)
python -m src.main

# Or run the web API for the dashboard
uvicorn src.api:app --port 8000
```

### Frontend

```bash
cd web
npm install
cp .env.example .env
# Edit .env: set VITE_API_URL to your backend (local or tunnel)
npm run dev
```

### Connecting a local backend to a hosted frontend

Use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/) to expose the local API:

```bash
cloudflared tunnel --url http://localhost:8000
# Copy the https://*.trycloudflare.com URL into the frontend's VITE_API_URL
```

Then deploy the frontend to Vercel with that URL as the `VITE_API_URL` env var. The backend's `CORS_ORIGINS` env var should include the Vercel URL.

## Commands

- `python -m src.main` — run scheduled scraping
- `python -m src.main --once` — one scrape cycle, then exit
- `python -m src.main --seed` — silently populate DB without notifications
- `python -m src.main --digest` — send the digest email and exit
- `uvicorn src.api:app --port 8000` — web API server
