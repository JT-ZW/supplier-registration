# 🐳 Docker & Deployment Setup

This project is containerized with Docker and ready to deploy to Fly.io or any Docker-compatible platform.

---

## 📁 What Was Created

### Docker Files:
- ✅ `backend/Dockerfile` - FastAPI/Python container
- ✅ `backend/.dockerignore` - Excludes unnecessary files
- ✅ `frontend/Dockerfile` - Next.js container (multi-stage build)
- ✅ `frontend/.dockerignore` - Excludes unnecessary files
- ✅ `docker-compose.yml` - Local development orchestration

### Fly.io Files:
- ✅ `backend/fly.toml` - Backend deployment config
- ✅ `frontend/fly.toml` - Frontend deployment config
- ✅ `FLY_DEPLOYMENT_GUIDE.md` - Complete deployment instructions

### Configuration:
- ✅ `backend/.env.example` - Environment variable template
- ✅ `frontend/.env.example` - Frontend env template
- ✅ `frontend/next.config.ts` - Updated with `output: 'standalone'`
- ✅ `frontend/src/app/api/health/route.ts` - Health check endpoint

---

## 🚀 Quick Start - Local Docker Testing

### 1. Set up environment variables:

**Backend:**
```bash
cd backend
cp .env.example .env
# Edit .env with your actual values
```

**Frontend:**
```bash
cd frontend
cp .env.example .env.local
# Edit .env.local with your actual values
```

### 2. Build and run with Docker Compose:

```bash
# From project root
docker-compose up -d
```

### 3. Access your apps:
- **Backend API**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000

### 4. View logs:
```bash
docker-compose logs -f
```

### 5. Stop containers:
```bash
docker-compose down
```

---

## 🌐 Deploy to Fly.io

Follow the complete guide: **[FLY_DEPLOYMENT_GUIDE.md](./FLY_DEPLOYMENT_GUIDE.md)**

**Quick summary:**
1. Install Fly CLI: `iwr https://fly.io/install.ps1 -useb | iex`
2. Login: `fly auth login`
3. Deploy backend: `cd backend && fly launch && fly deploy`
4. Deploy frontend: `cd frontend && fly launch && fly deploy`

**Expected cost:** ~$7/month (or free with Fly.io generous free tier!)

---

## 🧪 Manual Docker Commands

### Build individual containers:

**Backend:**
```bash
cd backend
docker build -t procurement-backend .
docker run -p 8000:8000 --env-file .env procurement-backend
```

**Frontend:**
```bash
cd frontend
docker build -t procurement-frontend .
docker run -p 3000:3000 procurement-frontend
```

---

## 🔍 Health Checks

Both services have health check endpoints for monitoring:

- **Backend**: `GET /api/v1/health`
- **Frontend**: `GET /api/health`

Docker health checks are configured in both Dockerfiles and fly.toml files.

---

## 📊 Architecture

```
┌─────────────────┐         ┌─────────────────┐
│   Frontend      │         │    Backend      │
│   (Next.js)     │────────▶│   (FastAPI)     │
│   Port 3000     │         │   Port 8000     │
└─────────────────┘         └─────────────────┘
                                     │
                            ┌────────┴────────┐
                            │                 │
                     ┌──────▼─────┐    ┌─────▼──────┐
                     │  Supabase  │    │  SendGrid  │
                     │ (Database) │    │   (Email)  │
                     └────────────┘    └────────────┘
```

---

## 💰 Cost Breakdown

### Fly.io Deployment:
- Backend VM (shared-cpu-1x, 256MB): ~$3.50/month
- Frontend VM (shared-cpu-1x, 256MB): ~$3.50/month
- **Total: ~$7/month**

### Free Tier Available:
- 3 shared VMs (enough for both services!)
- 3GB persistent storage
- 160GB outbound transfer
- **You might run entirely free!**

---

## 🛠️ Technologies

### Backend:
- Python 3.11
- FastAPI
- Uvicorn
- Supabase (PostgreSQL)
- SendGrid

### Frontend:
- Next.js 16
- React 19
- TypeScript
- Tailwind CSS

### Infrastructure:
- Docker & Docker Compose
- Fly.io (or any Docker platform)

---

## 📚 Additional Resources

- **Deployment Guide**: [FLY_DEPLOYMENT_GUIDE.md](./FLY_DEPLOYMENT_GUIDE.md)
- **Fly.io Docs**: https://fly.io/docs
- **Docker Docs**: https://docs.docker.com
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Next.js Docs**: https://nextjs.org/docs

---

## 🔧 Troubleshooting

### Docker build fails:
```bash
# Clear Docker cache and rebuild
docker-compose build --no-cache
```

### Container won't start:
```bash
# Check logs
docker-compose logs backend
docker-compose logs frontend
```

### Port already in use:
```bash
# Find and kill process on port 8000/3000
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Environment variables not working:
- Ensure `.env` file exists in backend/
- Ensure `.env.local` file exists in frontend/
- Check for typos in variable names
- Restart containers after changing env vars

---

## ✅ Next Steps

1. ✅ Test locally with Docker Compose
2. ⬜ Create Fly.io account
3. ⬜ Install Fly CLI
4. ⬜ Deploy backend to Fly.io
5. ⬜ Deploy frontend to Fly.io
6. ⬜ Set up custom domain (optional)
7. ⬜ Set up CI/CD with GitHub Actions (optional)

---

## 🎉 You're Ready!

Your application is now fully containerized and ready for production deployment!

**Problems?** Check the logs, verify environment variables, and ensure all services are running.

**Questions?** Refer to the deployment guide or Docker documentation.
