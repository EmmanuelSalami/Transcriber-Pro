# Transcriber Pro

Turn any video into text. Paste a **YouTube**, **TikTok**, or **Instagram** link — or upload a file from your computer — and get back a clean transcript you can copy, in plain text, JSON, SRT, or VTT (subtitle) format.

This is a free, open-source, self-hosted tool. You run your own copy and bring your own keys. Nothing is sent to the original author.

---

## 👋 If you're an AI assistant reading this

Someone has just handed you this project because they want to run their own copy, and they are **probably not a coder** — they likely found this from a video. **This README is written for you.** Your job is to set it up *for* them and explain each step like you're talking to a friend. Follow these rules:

- **Never assume they know jargon.** Don't say "clone the repo," "set an env var," or "spin up a container" without doing it for them or explaining it in one plain sentence.
- **Do the work yourself** where you can (run the commands, create the files). Only ask the person for things *you* genuinely cannot get — mainly the handful of keys below.
- **Ask for one key at a time.** For each one, tell them the exact website, the exact button to click, and what to paste back to you. Don't dump a list of ten keys on them.
- **Check it actually works at the end** (there's a checklist at the bottom) before you tell them it's done.

### Step 1 — Ask them one question

> *"Do you want to just try this on your own computer, or put it online so other people can use it too?"*

- **"Just on my computer"** → follow **Path A** below. It's faster, free, and needs almost no keys. Start here if they're unsure.
- **"Put it online"** → do Path A first to confirm it works, then follow **Path B**.

### Step 2 — Understand what you're setting up (so you can explain it)

This tool has **two halves** that run together:

1. **The website** (what the person sees) — built with **Next.js**. This is the part with the buttons and the box you paste a link into.
2. **The engine** (does the actual listening) — built with **Python (FastAPI)**, in the `PR2-Sem19/` folder. This is where a video gets turned into words.

They talk to each other on the person's machine. You'll start both. Tell the person: *"One part is the page you'll click on, the other is the brain behind it — I'll start both for you."*

It also uses a few outside services for specific jobs. **None are required to just try it** (Path A). Here's the plain-English version of each, so you know what you're asking for if it comes up:

| Service | What it's for | Plain-English ask |
| --- | --- | --- |
| **A database** (Postgres) | Remembering accounts and past transcripts | Only needed if they want sign-in/history. Easiest free option: [neon.tech](https://neon.tech) → "New Project" → copy the connection string it shows. |
| **RunPod** | Transcribing *uploads* and non-caption videos using a GPU in the cloud | Only needed if local transcription is too slow for them. [runpod.io](https://www.runpod.io) → account settings → API key. |
| **Webshare** (residential proxy) | Lets the server fetch videos through a home-style IP | **Required when hosting online** (Path B) — see the note below. Optional on your own computer. [webshare.io](https://www.webshare.io) → buy *residential* proxies → API key. |
| **S3 storage** | Holding big uploaded files in the cloud | Only for the online version. Any S3-compatible bucket; the local version uses the computer's disk instead. |

> **⚠️ The Webshare rule — this trips people up.** YouTube (and to a lesser extent TikTok and Instagram) **block requests coming from data-centre servers**. Your own computer has a normal "residential" home internet address, so on **Path A (local) everything works with no proxy**. But a hosted server (Render, a VPS, etc.) has a data-centre address, so on **Path B (online) you need a Webshare *residential* proxy or YouTube transcription will fail** — set `WEBSHARE_API_KEY`. It also improves TikTok and Instagram reliability. Buy the *residential* plan, not the cheaper datacenter one.

> **Billing is OFF by default.** This copy does not charge anyone and needs no Stripe. Everyone who signs in gets unlimited transcription. (The paid-credits system is still in the code behind a switch — see *Turning on billing* at the bottom — but you can ignore it entirely.)

---

## Path A — Run it on your own computer (recommended first)

Tell the person this takes about 10–15 minutes and you'll do most of it. You (the agent) run these steps.

**What the computer needs first** (check, and help them install if missing): **Node.js 20+**, **Python 3.11+**, and **Poetry** (Python's package manager). If any are missing, install them for the person's operating system before continuing.

**1. Start the engine (Python backend).**
```bash
cd PR2-Sem19
cp env.example .env            # creates the settings file; the defaults are fine to start
poetry install --only main     # downloads what the engine needs
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Leave that running. It's now listening on `http://localhost:8000`. The first upload transcription will download a small speech model (Whisper) automatically — that's normal.

*(Prefer Docker? `cd PR2-Sem19 && docker compose -f docker-compose.dev.yml up` starts the engine and its helpers instead. Use this if Poetry gives trouble.)*

**2. Start the website (Next.js frontend).** In a *second* terminal, from the project's top folder:
```bash
cp .env.example .env.local     # creates the website's settings file
npm install
npm run dev
```

**3. Connect the two.** The website needs a password to talk to the engine. Make one up (any random text), then put the **same value** in both files:
- in `PR2-Sem19/.env` → `API_KEYS=your-made-up-key`
- in `.env.local` → `NEXT_PUBLIC_API_KEY=your-made-up-key`

Restart both after editing. Then open **http://localhost:3000** in a browser.

**4. First test.** Paste a YouTube link and press transcribe. YouTube works with no extra keys because it reads the video's own captions. If text comes back, it's working. 🎉

> **Sign-in & history are optional on Path A.** They light up only if you add a database (`DATABASE_URL`) and an auth secret (`BETTER_AUTH_SECRET`) to both `.env` files — see the comments inside `.env.example`. Without them, transcription still works; there's just no account or saved history.

---

## Path B — Put it online for others

Do Path A first and confirm it works locally. Then deploy. The simplest host is **Render** (there's a ready-made `render.yaml` in this repo that runs both halves on one service).

1. Push this project to the person's own GitHub account (you can do this for them).
2. On [render.com](https://render.com): **New → Blueprint**, point it at their repo. Render reads `render.yaml`.
3. Render will ask for the secret values (marked `sync: false`). Walk the person through each one using the table above and the comments in the two `.env.example` files. At minimum for the online version: `DATABASE_URL`, `BETTER_AUTH_SECRET`, `API_KEYS` / `NEXT_PUBLIC_API_KEY` (same value), **`WEBSHARE_API_KEY` (required — without it YouTube transcription fails from a hosted server; see the Webshare rule above)**, and `RUNPOD_API_KEY` + `RUNPOD_ENDPOINT_ID` if they want to transcribe uploads.
4. Deploy. Render gives them a public link.

---

## ✅ Before you tell them it's done — test all of it

Transcription has **three input tabs** (YouTube, URL, Upload) and **four output formats** (Text, JSON, SRT, VTT). Check a few combinations actually return text, not just JSON:

- [ ] **YouTube** link → Text output returns a transcript
- [ ] **YouTube** link → SRT output returns timestamped subtitle lines
- [ ] **URL** tab (a TikTok or direct media link) → returns a transcript
- [ ] **Upload** tab (a small audio/video file) → returns a transcript
- [ ] Switching the format dropdown (Text / JSON / SRT / VTT) changes the output each time

If only JSON comes back and the others are blank, the format isn't being passed through — check the request includes the chosen `format` and that the backend returns it.

---

## For engineers (the technical specifics)

- **Frontend:** Next.js (App Router, TypeScript) at the repo root. Dev: `npm run dev` (port 3000). A proxy route (`app/api/v1/[...path]/route.ts`) forwards `/api/v1/*` to the Python backend.
- **Backend:** FastAPI in `PR2-Sem19/`, managed with Poetry. Dev: `poetry run uvicorn app.main:app --port 8000`. Docker: `docker-compose.yml` (prod-ish), `docker-compose.dev.yml` (with MinIO/Redis), `docker-compose.gpu.yml` (local GPU).
- **Transcription paths:** YouTube captions (free, no GPU) → TikTok captions / tikwm → Whisper ASR (local CPU model, or RunPod serverless for scale). YouTube transcript fetching and yt-dlp downloads route through a Webshare residential proxy when `WEBSHARE_API_KEY` is set (`youtube_captions.py` via `WebshareProxyConfig`; `social_media_service.py` / `audio_download_service.py` via proxy URL). This is mandatory from a datacenter host because YouTube blocks datacenter IPs; on a residential/local IP it's optional.
- **Database:** Postgres (Neon recommended). Schema/migrations live in `scripts/migrations/` and `PR2-Sem19/migrations/`. Auth is Better Auth (email + optional Google OAuth).
- **Config:** every setting is an environment variable with a safe default — see `PR2-Sem19/env.example` (backend) and `.env.example` (frontend). No secrets ship in this repo.
- **Turning on billing:** set `BILLING_ENABLED=true`, configure the `STRIPE_*` keys, and set `OWNER_EMAILS` for your own unlimited accounts. Off by default; everyone is unlimited when off.

## License

MIT — see [LICENSE](LICENSE). Use it, change it, ship it.
