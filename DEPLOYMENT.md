# Deployment Guide: Vercel (Frontend) + Render (Backend)

This guide walks you through deploying the AI-Prof platform using:
- **Vercel** for the Next.js frontend
- **Render** for the FastAPI backend + PostgreSQL + Redis + Celery worker

---

## 📋 Prerequisites

1. **GitHub account** with the repository pushed
2. **Vercel account** (free tier available)
3. **Render account** (free tier available)
4. **Git** installed locally

---

## 🚀 Step 1: Push Code to GitHub

```bash
cd c:/Users/ashok/OneDrive/Documents/VSCODE/AI-Prof

# Ensure all deployment files are committed
git add .
git commit -m "Add deployment configuration for Vercel + Render"
git push origin main
```

---

## 🎨 Step 2: Deploy Frontend to Vercel

### Option A: Automatic (Recommended)

1. Go to https://vercel.com
2. Click **"Add New Project"**
3. Import your GitHub repository
4. Vercel auto-detects Next.js

### Option B: Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Navigate to frontend
cd c:/Users/ashok/OneDrive/Documents/VSCODE/AI-Prof/frontend

# Deploy
vercel --prod
```

### Configure Environment Variables (Vercel Dashboard)

After importing, go to **Settings → Environment Variables** and add:

| Key | Value | Environment |
|-----|-------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://your-render-api.onrender.com` | Production |
| `NEXT_PUBLIC_AI_PROVIDER` | `mock` | Production |
| `NEXT_PUBLIC_VOICE_PROVIDER` | `simulated` | Production |
| `NEXT_PUBLIC_DEMO_MODE` | `true` | Production |

> ⚠️ **Important:** The `NEXT_PUBLIC_API_BASE_URL` should point to your Render backend URL (you'll get this after Step 3).

### Deploy

Click **"Deploy"** in Vercel. Your frontend will be live at:
```
https://your-project-name.vercel.app

---

## 🔧 Step 3: Deploy Backend to Render

### Option A: Using render.yaml (Blueprint)

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repository
4. Render will detect `render.yaml` and show all services:
   - `ai-prof-api` (Web Service)
   - `ai-prof-worker` (Background Worker)
   - `ai-prof-db` (PostgreSQL)
   - `ai-prof-redis` (Redis)
5. Click **"Apply"** to create all services

### Option B: Manual Setup

#### 3.1 Create PostgreSQL Database

1. Click **"New +"** → **"PostgreSQL"**
2. Name: `ai-prof-db`
3. Region: Same as your web service (e.g., Oregon)
4. Plan: **Starter** (free tier available)
5. Click **"Create Database"**
6. Copy the **Internal Database URL**

#### 3.2 Create Redis Instance

1. Click **"New +"** → **"Redis"**
2. Name: `ai-prof-redis`
3. Region: Same as your web service
4. Plan: **Starter**
5. Click **"Create Redis"**
6. Copy the **Internal Redis URL**

#### 3.3 Create Web Service (FastAPI)

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `ai-prof-api`
   - **Region:** Oregon (or closest to your users)
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Starter

4. Add Environment Variables:

| Key | Value | Notes |
|-----|-------|-------|
| `DATABASE_URL` | From PostgreSQL | Internal connection string |
| `REDIS_URL` | From Redis | Internal connection string |
| `JWT_SECRET_KEY` | Generate strong random string | Min 32 characters |
| `ENVIRONMENT` | `production` | |
| `FRONTEND_URL` | `https://your-project.vercel.app` | Your Vercel URL |
| `AI_PROVIDER` | `mock` | Change if you have real API keys |
| `GROQ_API_KEY` | Your key or leave as placeholder | Optional |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | |
| `OPENROUTER_API_KEY` | Your key or leave as placeholder | Optional |
| `OPENROUTER_MODEL` | `openrouter/free` | |
| `GOOGLE_API_KEY` | Your key or leave as placeholder | Optional |
| `GOOGLE_MODEL` | `gemini-2.5-flash` | |
| `VOICE_PROVIDER` | `simulated` | |

5. Click **"Create Web Service"**

#### 3.4 Create Background Worker (Celery)

1. Click **"New +"** → **"Background Worker"**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `ai-prof-worker`
   - **Region:** Same as web service
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `celery -A app.workers.queue_worker.celery_app worker --loglevel=info`
   - **Plan:** Starter

4. Add same Environment Variables as Web Service (especially `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`)

5. Click **"Create Background Worker"**

---

## 🔗 Step 4: Connect Frontend to Backend

1. After Render deploys the backend (may take 2-5 minutes), copy the API URL:
   ```
   https://ai-prof-api.onrender.com
   ```

2. Go to **Vercel Dashboard** → Your Project → **Settings** → **Environment Variables**

3. Update `NEXT_PUBLIC_API_BASE_URL` to your Render API URL

4. Click **"Save"** and then **"Redeploy"** the frontend

---

## ✅ Step 5: Verify Deployment

### Test Backend Health

```bash
curl https://ai-prof-api.onrender.com/health
# Expected: {"status": "ok"}
```

### Test API Documentation

Open in browser:
```
https://ai-prof-api.onrender.com/docs
```

### Test Frontend

Open in browser:
```
https://your-project.vercel.app
```

### Login Credentials

- **Platform Admin:** `admin@platform.local` / `Demo@123`
- **Hospital Admin:** `admin@stmarys.demo` / `Demo@123`

---

## ⚙️ Render Free Tier Limitations

| Service | Free Tier Limit | Notes |
|---------|-----------------|-------|
| Web Service | 750 hours/month | Spins down after 15 min inactivity (cold start ~30s) |
| Worker | 750 hours/month | Same as web service |
| PostgreSQL | 1GB storage | Shared CPU, 256MB RAM |
| Redis | Limited | May not be available on free tier |

### To Avoid Cold Starts

For production use, consider upgrading to **Preview** or **Standard** plans ($7-15/month).

---

## 🔐 Security Checklist for Production

### Backend (Render)

- [ ] `JWT_SECRET_KEY` is a strong random string (use `openssl rand -hex 32`)
- [ ] `ENVIRONMENT=production`
- [ ] Database user has limited permissions
- [ ] CORS configured for your Vercel domain only

### Frontend (Vercel)

- [ ] `NEXT_PUBLIC_API_BASE_URL` points to HTTPS Render URL
- [ ] No sensitive keys prefixed with `NEXT_PUBLIC_`

---

## 🐛 Troubleshooting

### Backend Won't Start

1. Check **Logs** in Render dashboard
2. Verify `DATABASE_URL` is correct
3. Ensure `requirements.txt` has all dependencies
4. Check Python version compatibility

### Frontend Can't Reach API

1. Verify `NEXT_PUBLIC_API_BASE_URL` is set correctly
2. Check CORS settings in backend
3. Ensure API URL includes `https://`

### Celery Worker Not Processing

1. Check worker logs in Render
2. Verify Redis connection
3. Ensure worker has same env vars as web service

### Database Connection Errors

1. Verify PostgreSQL is running
2. Check `DATABASE_URL` format: `postgresql://user:pass@host:5432/dbname`
3. Ensure database is in same region as web service

---

## 📊 Architecture

```
                    ┌─────────────────────┐
                    │     Vercel CDN      │
                    │  (Frontend Hosted)  │
                    │   your-app.vercel.app│
                    └──────────┬──────────┘
                               │
                    HTTP/HTTPS│
                               │
                    ┌──────────▼──────────┐
                    │   Render Platform   │
                    │                     │
                    │  ┌────────────────┐ │
                    │  │  Web Service   │ │
                    │  │  (FastAPI)     │ │
                    │  │  Port $PORT    │ │
                    │  └───────┬────────┘ │
                    │          │          │
                    │  ┌───────▼──────┐  │
                    │  │  PostgreSQL  │  │
                    │  │  (Database)  │  │
                    │  └──────────────┘  │
                    │                     │
                    │  ┌────────────────┐ │
                    │  │     Redis     │ │
                    │  │   (Queue)     │ │
                    │  └───────┬────────┘ │
                    │          │          │
                    │  ┌───────▼──────┐  │
                    │  │  Worker      │  │
                    │  │  (Celery)    │  │
                    │  └──────────────┘  │
                    │                     │
                    └─────────────────────┘
```

---

## 💰 Estimated Monthly Costs (Production)

| Service | Free Tier | Starter Plan |
|---------|-----------|--------------|
| Vercel Frontend | ✅ Free (hobby) | $20/mo (pro) |
| Render Web Service | ⚠️ Cold starts | $7/mo |
| Render Worker | ⚠️ Cold starts | $7/mo |
| Render PostgreSQL | ⚠️ Limited | $7/mo |
| Render Redis | ⚠️ May not be free | $7/mo |
| **Total** | **$0** (dev/test) | **~$28/mo** (production) |

---

## 🔄 Updating Deployment

### Update Frontend

```bash
# Make changes
git add .
git commit -m "Update frontend"
git push origin main

# Vercel auto-deploys on push
```

### Update Backend

```bash
# Make changes
git add .
git commit -m "Update backend"
git push origin main

# Render auto-deploys on push (if configured)
```

### Manual Redeploy

- **Vercel:** Dashboard → Deployments → Redeploy
- **Render:** Dashboard → Service → Manual Deploy

---

## 🎯 Quick Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Vercel project created & connected
- [ ] Frontend env vars configured (`NEXT_PUBLIC_API_BASE_URL`)
- [ ] Frontend deployed successfully
- [ ] Render PostgreSQL created
- [ ] Render Redis created
- [ ] Render Web Service created with env vars
- [ ] Render Worker created with env vars
- [ ] Backend deployed & healthy
- [ ] Frontend env updated with Render API URL
- [ ] Frontend redeployed
- [ ] Login test successful
- [ ] API docs accessible

---

## 📞 Support

- **Vercel Docs:** https://vercel.com/docs
- **Render Docs:** https://render.com/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Next.js Docs:** https://nextjs.org/docs
```
