# 🚀 Supplier Registration System - Setup Guide

## Current Status ✅

**Completed:**
- ✅ Frontend built successfully (11 routes)
- ✅ Backend structure complete (FastAPI + Python)
- ✅ Environment files created (.env templates)
- ✅ Database schema aligned with frontend (updated migration)
- ✅ Backend models updated with camelCase aliases

**Next:** Follow the steps below to configure and run the system.

---

## 📋 Step-by-Step Setup

### Step 1: Configure Supabase (Database)

1. **Create a Supabase Project**
   - Go to [supabase.com](https://supabase.com) and create a free account
   - Create a new project
   - Wait for the project to finish provisioning

2. **Get Your Credentials**
   - In your Supabase dashboard, go to **Project Settings > API**
   - Copy these values:
     - **Project URL** (e.g., `https://abcdefg.supabase.co`)
     - **anon public** key
     - **service_role** key (keep this secret!)

3. **Run the Database Migration**
   - In Supabase dashboard, go to **SQL Editor**
   - Click **New Query**
   - Copy the entire contents of `backend/app/db/migrations/001_initial_schema.sql`
   - Paste and run it
   - Then copy and run `backend/app/db/migrations/002_seed_data.sql`

4. **Verify Tables Created**
   - Go to **Table Editor** in Supabase
   - You should see: `suppliers`, `documents`, `admin_users`, `audit_logs`

---

### Step 2: Configure AWS S3 (File Storage)

1. **Create an AWS Account** (if you don't have one)
   - Go to [aws.amazon.com](https://aws.amazon.com)

2. **Create an S3 Bucket**
   - Go to **S3** service
   - Click **Create bucket**
   - Name it (e.g., `supplier-documents-yourcompany`)
   - Region: Choose closest to your users
   - **Block all public access** (we'll use presigned URLs)
   - Click **Create bucket**

3. **Create IAM User for S3 Access**
   - Go to **IAM** service > **Users** > **Create user**
   - Username: `supplier-app-s3-user`
   - **Attach policies directly** > Select `AmazonS3FullAccess`
   - Click **Create user**
   - Click on the user > **Security credentials** > **Create access key**
   - Choose **Application running on AWS** > **Next**
   - Copy the **Access Key ID** and **Secret Access Key** (save them securely!)

4. **Configure CORS for the Bucket**
   - Go to your S3 bucket > **Permissions** > **CORS**
   - Add this configuration:
   ```json
   [
     {
       "AllowedHeaders": ["*"],
       "AllowedMethods": ["GET", "PUT", "POST"],
       "AllowedOrigins": ["http://localhost:3000"],
       "ExposeHeaders": ["ETag"]
     }
   ]
   ```

---

### Step 3: Update Environment Files

1. **Backend** - Edit `backend/.env`:
   ```env
   # Update these with your actual values:
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your-supabase-anon-key
   SUPABASE_SERVICE_KEY=your-supabase-service-role-key

   AWS_ACCESS_KEY_ID=your-aws-access-key
   AWS_SECRET_ACCESS_KEY=your-aws-secret-key
   AWS_REGION=us-east-1
   S3_BUCKET_NAME=your-bucket-name

   # Generate a secure JWT secret:
   # Run: python -c "import secrets; print(secrets.token_hex(32))"
   JWT_SECRET_KEY=your-generated-secret-key-here
   ```

2. **Frontend** - Edit `frontend/.env.local`:
   ```env
   # Update these to match your backend:
   NEXT_PUBLIC_API_URL=http://localhost:8000/v1
   NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
   ```

---

### Step 4: Install Dependencies & Start Backend

```powershell
# Navigate to backend
cd backend

# Create a virtual environment (recommended)
python -m venv venv

# Activate it
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**You should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

**Test the backend:**
- Open browser: http://localhost:8000/docs
- You should see the Swagger UI with all API endpoints

---

### Step 5: Start Frontend

**Open a NEW terminal** (keep backend running):

```powershell
# Navigate to frontend
cd frontend

# Install dependencies (if not already done)
npm install

# Start the dev server
npm run dev
```

**You should see:**
```
▲ Next.js 16.0.6
- Local:        http://localhost:3000
```

---

## 🎯 Testing the Application

### 1. Test Supplier Registration Flow

1. **Open** http://localhost:3000
2. Click **Register as Supplier**
3. Fill out the registration form:
   - Step 1: Business Information
   - Step 2: Contact Information
   - Step 3: Address Information
   - Step 4: Banking Information
4. Click **Next** through each step
5. **Upload Documents** (use PDFs or images < 20MB)
6. **Review & Submit** your application

### 2. Test Admin Portal

1. **Open** http://localhost:3000/admin/login
2. **Login** with default credentials:
   - Email: `admin@procurement.com`
   - Password: `Admin123!`
3. View the **Dashboard** with analytics
4. Go to **Suppliers** list
5. Click on a supplier to **review** their application
6. **Approve**, **Reject**, or **Request More Info**

---

## 📝 Default Admin Credentials

**Email:** `admin@procurement.com`  
**Password:** `Admin123!`

⚠️ **Change this password immediately in production!**

---

## 🛠 Troubleshooting

### Backend won't start?
- Check that all `.env` variables are set correctly
- Verify Supabase credentials
- Make sure port 8000 is not in use

### Frontend won't start?
- Run `npm install` again
- Check that `.env.local` exists and has correct values
- Make sure port 3000 is not in use

### Database connection errors?
- Verify Supabase URL and keys in `.env`
- Check that migrations ran successfully in Supabase SQL Editor
- Ensure Row Level Security (RLS) policies are created

### File upload fails?
- Check AWS S3 credentials in `.env`
- Verify bucket name is correct
- Check CORS configuration on S3 bucket
- Ensure IAM user has S3 permissions

### CORS errors?
- Backend CORS is configured for `http://localhost:3000`
- S3 CORS should allow `http://localhost:3000`
- For production, update both to your production domain

---

## 📚 API Documentation

Once the backend is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🎨 Project Structure

```
procurement/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── api/          # Route handlers
│   │   ├── core/         # Config, security, storage
│   │   ├── db/           # Database & migrations
│   │   ├── models/       # Pydantic models
│   │   └── main.py       # FastAPI app
│   └── requirements.txt
│
├── frontend/             # Next.js frontend
│   ├── components/       # React components
│   ├── hooks/           # Custom hooks
│   ├── lib/             # API client, utilities
│   ├── types/           # TypeScript types
│   ├── constants/       # App constants
│   └── src/app/         # Pages & routes
│
└── README.md
```

---

## 🚀 Next Steps After Setup

1. **Test the complete registration flow**
2. **Test admin review process**
3. **Configure email notifications** (SendGrid or SMTP)
4. **Set up production environment**
5. **Deploy to hosting** (Vercel for frontend, Railway/Fly.io for backend)

---

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review backend logs in the terminal
3. Check browser console for frontend errors
4. Verify all environment variables are set correctly

---

**You're all set! Start testing the application.** 🎉
