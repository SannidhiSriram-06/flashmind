# FlashMind — Deployment Guide

---

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Environment Variables Reference](#environment-variables-reference)
3. [Railway Deployment](#railway-deployment)
4. [MongoDB Atlas Setup](#mongodb-atlas-setup)
5. [Groq API Key](#groq-api-key)
6. [Production Checklist](#production-checklist)
7. [Troubleshooting](#troubleshooting)

---

## Local Development Setup

Tested on macOS and Linux. Python 3.11+ required.

### Step 1 — Clone the repo

```bash
git clone https://github.com/SannidhiSriram-06/flashmind.git
cd flashmind
```

### Step 2 — Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `requirements.txt` includes ChromaDB and sentence-transformers for local vector search.
> In production, `requirements-prod.txt` is used instead (no ChromaDB/torch — much smaller image).

### Step 4 — Create your `.env` file

```bash
# Generate a secure secret key
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# Create .env
cat > .env << 'EOF'
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
GROQ_API_KEY=gsk_...
SECRET_KEY=<paste generated key here>
# Optional:
# DISABLE_VECTOR_STORE=true
# ENV=development
# CORS_ORIGINS=http://localhost:8000
EOF
```

### Step 5 — Run the server

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000` in your browser. The API docs are at `http://localhost:8000/docs`.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGODB_URI` | **Yes** | — | Full MongoDB connection string including credentials and cluster host |
| `GROQ_API_KEY` | **Yes** | — | API key from [console.groq.com](https://console.groq.com). Used to call `llama-3.1-8b-instant` |
| `SECRET_KEY` | **Yes** | — | 32-byte hex string used to sign session cookies with `itsdangerous`. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENV` | No | `development` | Set to `production` to enable `Secure` flag on cookies and strict secret-key enforcement |
| `CORS_ORIGINS` | No | `http://localhost:8000` | Comma-separated list of origins allowed by CORS middleware. Set to your production URL in deployment |
| `DISABLE_VECTOR_STORE` | No | `false` | Set to `true` to skip all ChromaDB/embedding operations. Recommended for cloud deployments with memory or storage constraints |

---

## Railway Deployment

Railway uses the `nixpacks.toml` in the repo root to build the image with `requirements-prod.txt`.

### Step 1 — Create a Railway project

1. Go to [railway.app](https://railway.app) and sign in with GitHub.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select `SannidhiSriram-06/flashmind`.

### Step 2 — Set environment variables

In your Railway project, go to **Variables** and add:

| Key | Value |
|---|---|
| `MONGODB_URI` | Your MongoDB Atlas connection string |
| `GROQ_API_KEY` | Your Groq API key |
| `SECRET_KEY` | A 64-character hex string |
| `ENV` | `production` |
| `DISABLE_VECTOR_STORE` | `true` |
| `CORS_ORIGINS` | `https://<your-app>.up.railway.app` |

> Railway automatically injects `PORT`. The start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` reads it from the environment.

### Step 3 — Deploy

Railway triggers a deployment automatically when you push to `main`. Watch the build logs in the **Deployments** tab.

### Step 4 — Verify

Once deployed, visit `https://<your-app>.up.railway.app/health` — you should see `{"status": "ok"}`.

---

## MongoDB Atlas Setup

### Step 1 — Create a free cluster

1. Go to [cloud.mongodb.com](https://cloud.mongodb.com) and sign in.
2. Click **Build a Database** → choose **Free (M0)**.
3. Select a cloud provider and region close to your Railway region.
4. Name your cluster (e.g., `flashmind`).

### Step 2 — Create a database user

1. In the left sidebar, click **Database Access** → **Add New Database User**.
2. Choose **Password** authentication.
3. Set a username (e.g., `flashmind`) and a strong password.
4. Set role to **Atlas admin** or **Read and write to any database**.
5. Click **Add User**.

### Step 3 — Allow network access

1. Click **Network Access** → **Add IP Address**.
2. For Railway, click **Allow Access from Anywhere** (`0.0.0.0/0`).
   - For tighter security, get Railway's static IP from your project settings and whitelist only that.

### Step 4 — Get the connection string

1. Go to **Database** → click **Connect** on your cluster.
2. Choose **Connect your application** → **Python** → **3.12 or later**.
3. Copy the URI. It looks like:
   ```
   mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   ```
4. Replace `<password>` with your database user's password.
5. Paste this as your `MONGODB_URI` environment variable.

> The app will create the `flashmind` database and all collections automatically on first run.

---

## Groq API Key

1. Go to [console.groq.com](https://console.groq.com) and sign in (free account).
2. Click **API Keys** in the left sidebar → **Create API Key**.
3. Name it (e.g., `flashmind-prod`) and copy the key — it starts with `gsk_`.
4. Set it as `GROQ_API_KEY` in your environment.

> The app uses `llama-3.1-8b-instant` which is free on Groq's current plan. Flashcard generation is capped at 4,000 input characters to stay well within token limits.

---

## Production Checklist

Before going live, verify each item:

- [ ] `MONGODB_URI` is set and points to Atlas (not localhost)
- [ ] `GROQ_API_KEY` is a valid Groq key with access to `llama-3.1-8b-instant`
- [ ] `SECRET_KEY` is at least 32 bytes of random hex — **never** use a guessable value
- [ ] `ENV=production` — enables `Secure` on cookies and hard-fails if `SECRET_KEY` is missing
- [ ] `DISABLE_VECTOR_STORE=true` — prevents ChromaDB from being imported (saves ~5 GB of image size from torch/sentence-transformers)
- [ ] `CORS_ORIGINS` is set to your exact production domain (e.g., `https://flashmind.up.railway.app`)
- [ ] MongoDB network access allows Railway's egress IPs (or `0.0.0.0/0` for simplicity)
- [ ] Test `/health` endpoint returns `{"status": "ok"}`
- [ ] Test signup, PDF upload, and a complete study session end-to-end

---

## Troubleshooting

### Build fails with 5+ GB image / out of memory

**Cause:** `requirements.txt` includes `chromadb`, `sentence-transformers`, and `torch`, which pull in gigabytes of ML dependencies.

**Fix:** Ensure the build command uses `requirements-prod.txt`, not `requirements.txt`.

In `nixpacks.toml`:
```toml
[phases.install]
cmds = ["pip install -r requirements-prod.txt"]
```

Set `DISABLE_VECTOR_STORE=true` so the app doesn't try to import those packages at runtime.

---

### `RuntimeError: MONGODB_URI is not set`

**Cause:** The `MONGODB_URI` environment variable is missing or not injected into the container.

**Fix:**
1. Check Railway **Variables** tab — confirm `MONGODB_URI` is present and not empty.
2. Confirm the variable name is exactly `MONGODB_URI` (case-sensitive).
3. Redeploy after adding the variable (Railway doesn't always hot-reload env changes).

---

### `RuntimeError: SECRET_KEY must be set`

**Cause:** `ENV=production` is set but `SECRET_KEY` is missing.

**Fix:** Generate and set a secure key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Paste the output as `SECRET_KEY` in Railway Variables.

---

### CORS errors in the browser console

**Cause:** `CORS_ORIGINS` does not include your frontend's exact origin.

**Fix:** Set `CORS_ORIGINS` to match exactly, including protocol and no trailing slash:
```
CORS_ORIGINS=https://flashmind.up.railway.app
```

If you have multiple origins (e.g., preview URLs), comma-separate them:
```
CORS_ORIGINS=https://flashmind.up.railway.app,https://flashmind-preview.up.railway.app
```

---

### Railway deployment stuck / DNS not resolving

**Cause:** Railway can take 1–3 minutes to provision the domain after a first deploy.

**Fix:** Wait 2–3 minutes, then hard-refresh. If it persists, go to Railway **Settings** → **Domains** and confirm the domain is generated. You can also add a custom domain there.

---

### PDF upload returns 422 or "No extractable text"

**Cause:** The uploaded PDF is either scanned (image-only) or password-protected.

**Fix:** Use a PDF with selectable text. You can check in any PDF viewer — if you can highlight and copy text, pdfplumber can read it. For scanned PDFs, run OCR first (e.g., with Adobe Acrobat or `ocrmypdf`).

---

### Groq returns "Flashcard generation failed after 3 attempts"

**Cause:** The PDF's extracted text is too short (under 200 characters after chunking), or the Groq API returned non-JSON output three times in a row.

**Fix:**
- Try a longer, text-rich PDF (lecture notes, articles, textbook chapters work best).
- Check your `GROQ_API_KEY` is valid and has not hit rate limits.
- The app retries with three progressively stricter prompts — if all fail, the PDF likely has very little usable content.
