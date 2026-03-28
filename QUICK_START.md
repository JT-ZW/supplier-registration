# Quick Start Guide - Docker & Deployment

## ✅ Current Status
- **TypeScript**: All 89 errors fixed ✓
- **Docker Build**: Successfully completed ✓
- **Ready for**: Local testing and deployment ✓

---

## 🚀 Quick Commands

### Run Locally with Docker
```bash
# Build images (already done)
docker-compose build

# Start all services
docker-compose up

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Access URLs
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

---

## 🔧 Environment Setup

### Required Environment Variables

**Backend** (`backend/.env`):
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_service_key
JWT_SECRET=your_jwt_secret_key
SENDGRID_API_KEY=your_sendgrid_key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
FRONTEND_URL=http://localhost:3000
```

**Frontend** (`frontend/.env.local`):
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## 📦 Deploy to Fly.io

### Backend Deployment
```bash
cd backend

# Login to Fly.io
flyctl auth login

# Launch app (first time only)
flyctl launch

# Set secrets
flyctl secrets set SUPABASE_URL=your_url
flyctl secrets set SUPABASE_KEY=your_key
flyctl secrets set SUPABASE_SERVICE_KEY=your_service_key
flyctl secrets set JWT_SECRET=your_secret
flyctl secrets set SENDGRID_API_KEY=your_key
flyctl secrets set SENDGRID_FROM_EMAIL=your_email
flyctl secrets set AWS_ACCESS_KEY_ID=your_key
flyctl secrets set AWS_SECRET_ACCESS_KEY=your_secret
flyctl secrets set S3_BUCKET_NAME=your_bucket
flyctl secrets set FRONTEND_URL=https://your-frontend.fly.dev

# Deploy
flyctl deploy
```

### Frontend Deployment
```bash
cd frontend

# Launch app (first time only)
flyctl launch

# Set environment variable
flyctl secrets set NEXT_PUBLIC_API_URL=https://your-backend.fly.dev/api/v1

# Deploy
flyctl deploy
```

---

## 🧪 Testing Checklist

### Before Deployment
- [ ] Environment variables configured
- [ ] Supabase database setup complete
- [ ] S3 bucket created and accessible
- [ ] SendGrid API key configured
- [ ] Docker images built successfully

### After Deployment
- [ ] Frontend loads and displays homepage
- [ ] Vendor registration works
- [ ] Vendor login/authentication works
- [ ] Admin login works
- [ ] Document upload functions
- [ ] Email notifications send correctly

---

## 🐛 Troubleshooting

### Docker Build Issues
```bash
# Clear Docker cache
docker system prune -a

# Rebuild without cache
docker-compose build --no-cache

# Check logs
docker-compose logs backend
docker-compose logs frontend
```

### TypeScript Errors During Development
```bash
# Run error analysis script
.\analyze-typescript-errors.ps1

# Or manually check
cd frontend
npm run build
```

### Port Conflicts
```bash
# Check what's using port 3000 or 8000
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <process_id> /F
```

---

## 📚 Documentation

- **Setup Guide**: `SETUP_GUIDE.md`
- **Docker Setup**: `DOCKER_SETUP.md`
- **Fly.io Deployment**: `FLY_DEPLOYMENT_GUIDE.md`
- **Supabase Setup**: `SUPABASE_STORAGE_SETUP_GUIDE.md`
- **SendGrid Setup**: `SENDGRID_SETUP_GUIDE.md`
- **AWS S3 Setup**: `AWS_S3_SETUP_GUIDE.md`
- **TypeScript Fixes**: `TYPESCRIPT_FIXES_FINAL.md`

---

## 💰 Estimated Costs

### Fly.io (Free Tier Available)
- **Backend**: ~$5/month (1 shared CPU, 256MB RAM)
- **Frontend**: ~$5/month (1 shared CPU, 256MB RAM)
- **Total**: ~$10/month or **FREE** on hobby plan

### Supabase (Free Tier)
- 500MB database
- 1GB file storage
- 2GB bandwidth
- **Cost**: FREE

### AWS S3
- First 5GB storage: FREE
- First 20,000 GET requests: FREE
- First 2,000 PUT requests: FREE
- **Est Cost**: <$1/month

### SendGrid (Free Tier)
- 100 emails/day
- **Cost**: FREE

**Total Estimated Cost**: $0-10/month

---

## 🎯 Next Actions

1. **Test Locally**: 
   ```bash
   docker-compose up
   ```

2. **Configure Environment**: Set up all required services (Supabase, S3, SendGrid)

3. **Deploy Backend**: Push to Fly.io and verify

4. **Deploy Frontend**: Push to Fly.io and connect to backend

5. **Test Production**: Run through full supplier registration flow

---

## 📞 Support

- **Issues**: Check logs with `docker-compose logs`
- **TypeScript**: Run `.\analyze-typescript-errors.ps1`
- **Deployment**: See `FLY_DEPLOYMENT_GUIDE.md`

---

**Status**: ✅ Ready for deployment
**Last Updated**: 2024-02-15
