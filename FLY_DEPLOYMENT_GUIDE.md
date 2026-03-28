# 🚀 Fly.io Deployment Guide

Complete guide to deploying your Procurement System to Fly.io with Docker.

---

## 📋 Prerequisites

- [x] Docker installed (you have this!)
- [ ] Fly.io account (create at https://fly.io/app/sign-up)
- [ ] Fly CLI installed
- [ ] Your environment variables ready

---

## 🛠️ Step 1: Install Fly CLI

### Windows (PowerShell):
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

**Important:** After installation, **close and reopen PowerShell** for the PATH to update.

### Verify installation:
```powershell
flyctl version
```

**Troubleshooting:** If `flyctl` is not recognized:
1. **Restart PowerShell** (close and open a new window)
2. Or refresh PATH in current session:
   ```powershell
   $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
   ```
3. Or use full path: `& "$env:USERPROFILE\.fly\bin\flyctl.exe" version`

**Note:** The command is `flyctl` (not `fly`). You can create an alias:
```powershell
Set-Alias fly flyctl
```

---

## 🔐 Step 2: Login to Fly.io

```bash
flyctl auth login
```

This will open your browser to authenticate.

**Note:** You can use `flyctl` or `fly` interchangeably (they're the same command).

---

## 🧪 Step 3: Test Docker Locally (Optional but Recommended)

### Test Backend:
```bash
cd backend
docker build -t procurement-backend .
docker run -p 8000:8000 --env-file .env procurement-backend
```

Visit http://localhost:8000/docs to verify it works.

### Test Frontend:
```bash
cd frontend
docker build -t procurement-frontend .
docker run -p 3000:3000 procurement-frontend
```

Visit http://localhost:3000 to verify it works.

### Test with Docker Compose:
```bash
# From project root
docker-compose up -d
docker-compose logs -f
```

---

## 🚀 Step 4: Deploy Backend to Fly.io

### 4.1: Navigate to backend directory:
```bash
cd backend
```

### 4.2: Create Fly app (skip if app already exists):
```bash
fly launch --no-deploy
```

**Answer the prompts:**
- App name: `procurement-backend` (or your preferred name)
- Region: Choose closest to you (e.g., `iad` for US East)
- Would you like to set up a database? **No** (you're using Supabase)
- Would you like to deploy now? **No**

This creates/updates the `fly.toml` configuration.

### 4.3: Set environment secrets:
```bash
# Required secrets
fly secrets set SUPABASE_URL="https://your-project.supabase.co"
fly secrets set SUPABASE_KEY="your-anon-key"
fly secrets set SUPABASE_SERVICE_KEY="your-service-key"
fly secrets set SECRET_KEY="your-jwt-secret-key"
fly secrets set SENDGRID_API_KEY="your-sendgrid-key"
fly secrets set SENDGRID_FROM_EMAIL="noreply@yourdomain.com"

# Optional (if using AWS S3):
fly secrets set AWS_ACCESS_KEY_ID="your-aws-key"
fly secrets set AWS_SECRET_ACCESS_KEY="your-aws-secret"
fly secrets set AWS_S3_BUCKET="your-bucket-name"
fly secrets set AWS_REGION="us-east-1"

# Set frontend URL (will update after deploying frontend)
fly secrets set FRONTEND_URL="https://procurement-frontend.fly.dev"
```

### 4.4: Deploy backend:
```bash
fly deploy
```

### 4.5: Verify backend is running:
```bash
fly open
# Or visit: https://procurement-backend.fly.dev/docs
```

---

## 🎨 Step 5: Deploy Frontend to Fly.io

### 5.1: Navigate to frontend directory:
```bash
cd ../frontend
```

### 5.2: Create Fly app:
```bash
fly launch --no-deploy
```

**Answer the prompts:**
- App name: `procurement-frontend` (or your preferred name)
- Region: Same as backend for best performance
- Would you like to set up a database? **No**
- Would you like to deploy now? **No**

### 5.3: Set environment secrets:
```bash
# Backend API URL (use your actual backend URL - MUST include /api/v1)
fly secrets set NEXT_PUBLIC_API_URL="https://procurement-backend.fly.dev/api/v1"

# Supabase (if frontend uses it directly)
fly secrets set NEXT_PUBLIC_SUPABASE_URL="https://your-project.supabase.co"
fly secrets set NEXT_PUBLIC_SUPABASE_ANON_KEY="your-anon-key"
```

### 5.4: Deploy frontend:
```bash
fly deploy
```

### 5.5: Verify frontend is running:
```bash
fly open
# Or visit: https://procurement-frontend.fly.dev
```

---

## 🔄 Step 6: Update Backend CORS

Now that frontend is deployed, update the backend's FRONTEND_URL:

```bash
cd ../backend
fly secrets set FRONTEND_URL="https://procurement-frontend.fly.dev"
```

---

## 📊 Step 7: Monitor Your Apps

### View logs:
```bash
# Backend logs
cd backend
fly logs

# Frontend logs
cd frontend
fly logs
```

### Check status:
```bash
fly status
```

### View dashboard:
```bash
fly dashboard
```

Or visit: https://fly.io/dashboard

---

## 💰 Step 8: Cost Optimization

### Free tier includes:
- Up to 3 shared-cpu-1x VMs with 256MB RAM
- 3GB persistent storage
- 160GB outbound transfer

### Your setup costs (with 2 apps):
- Backend: ~$3.50/month (shared-cpu-1x, 256MB)
- Frontend: ~$3.50/month (shared-cpu-1x, 256MB)
- **Total: ~$7/month** (or free if within limits!)

### To scale up (if needed):
```bash
fly scale vm shared-cpu-1x --memory 512  # More memory
fly scale count 2  # Multiple instances
```

---

## 🔧 Common Commands

### Redeploy after code changes:
```bash
fly deploy
```

### SSH into your app:
```bash
fly ssh console
```

### View environment variables:
```bash
fly secrets list
```

### Scale down to save money:
```bash
fly scale count 0  # Stop all machines
fly scale count 1  # Start again
```

### Update a secret:
```bash
fly secrets set SECRET_NAME="new-value"
```

### Delete an app (careful!):
```bash
fly apps destroy app-name
```

---

## 🚨 Troubleshooting

### App won't start:
1. Check logs: `fly logs`
2. Verify health check endpoint exists
3. Ensure all required secrets are set: `fly secrets list`

### Can't connect frontend to backend:
1. Verify NEXT_PUBLIC_API_URL is correct
2. Check CORS settings in backend
3. Ensure both apps are in same region (lower latency)

### Build fails:
1. Test Docker build locally first
2. Check Dockerfile syntax
3. Verify all dependencies are in requirements.txt/package.json

### Out of memory:
```bash
fly scale vm shared-cpu-1x --memory 512
```

---

## 📝 Next Steps

### Set up custom domain (optional):
```bash
fly certs add yourdomain.com
fly certs add api.yourdomain.com
```

### Set up CI/CD with GitHub Actions:
Create `.github/workflows/deploy.yml` for automatic deployments.

### Enable auto-scaling:
Already enabled in fly.toml with:
- `auto_stop_machines = true`
- `auto_start_machines = true`
- `min_machines_running = 0`

This means apps will auto-sleep when not used (saves money!) and wake up on requests.

---

## 🎉 You're Live!

Your apps are now running on Fly.io:
- **Backend API**: https://procurement-backend.fly.dev
- **Frontend**: https://procurement-frontend.fly.dev
- **Cost**: ~$7/month (or free!)

### Need help?
- Fly.io Docs: https://fly.io/docs
- Community Forum: https://community.fly.io
- Your logs: `fly logs`

---

## 📦 Quick Reference

```bash
# Deploy
fly deploy

# Logs
fly logs

# Status
fly status

# SSH
fly ssh console

# Secrets
fly secrets set KEY="value"
fly secrets list

# Scale
fly scale count 1
fly scale vm shared-cpu-1x --memory 256

# Dashboard
fly dashboard

# Open app in browser
fly open
```
