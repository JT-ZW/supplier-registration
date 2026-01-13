# Supplier Registration & Approval System

A comprehensive procurement system for managing supplier registrations, document uploads, and admin approvals.

## 📋 Overview

This system allows suppliers to register as guest users, upload required documents, and submit applications for review. Procurement administrators can review applications, verify documents, and approve or reject suppliers through a dedicated admin portal with analytics and reporting.

## 🏗️ Architecture

### Backend (FastAPI)
- **Framework**: FastAPI with Python 3.11+
- **Database**: Supabase (PostgreSQL)
- **Storage**: AWS S3 with presigned URLs
- **Authentication**: JWT tokens (admin only)
- **Email**: SendGrid / SMTP

### Frontend (Next.js)
- **Framework**: Next.js 14+ with App Router
- **UI**: React + Tailwind CSS
- **State Management**: TanStack Query (React Query)
- **Forms**: React Hook Form + Zod validation
- **Charts**: Recharts

## 📁 Project Structure

```
procurement/
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── api/         # API routes
│   │   ├── core/        # Core utilities (security, storage, email)
│   │   ├── db/          # Database client and migrations
│   │   ├── models/      # Pydantic models
│   │   └── main.py      # App entry point
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
└── frontend/            # Next.js application
    ├── app/            # Next.js app routes
    ├── components/     # React components
    ├── lib/           # Utilities and API client
    ├── types/         # TypeScript types
    ├── constants/     # Constants and enums
    ├── hooks/         # Custom React hooks
    ├── package.json
    ├── .env.example
    └── README.md
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **PostgreSQL** (via Supabase account)
- **AWS Account** (for S3 storage)
- **SendGrid Account** (optional, for emails)

### 1. Clone the Repository

```powershell
git clone <repository-url>
cd procurement
```

### 2. Backend Setup

#### a. Create Virtual Environment

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### b. Install Dependencies

```powershell
pip install -r requirements.txt
```

#### c. Configure Environment

```powershell
Copy-Item .env.example .env
```

Update `.env` with your credentials:
- Supabase URL and keys
- AWS S3 configuration
- JWT secret key
- Email service credentials

#### d. Run Database Migrations

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Open SQL Editor
3. Execute migrations in order:
   - `app/db/migrations/001_initial_schema.sql`
   - `app/db/migrations/002_seed_data.sql`

#### e. Start Backend Server

```powershell
python -m app.main
```

Backend runs at: **http://localhost:8000**  
API Docs: **http://localhost:8000/v1/docs**

### 3. Frontend Setup

#### a. Install Dependencies

```powershell
cd ..\frontend
npm install
```

#### b. Configure Environment

```powershell
Copy-Item .env.example .env.local
```

Update `.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/v1
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
```

#### c. Start Development Server

```powershell
npm run dev
```

Frontend runs at: **http://localhost:3000**

## 🔐 Default Admin Credentials

After running database migrations:

- **Email**: `admin@procurement.com`
- **Password**: `Admin123!`

⚠️ **Important**: Change this password immediately after first login!

## 📚 Key Features

### Supplier Portal (Guest Users)
- ✅ Multi-step registration form
- ✅ Business category selection
- ✅ Dynamic document requirements based on category
- ✅ Secure file uploads (up to 20MB per file)
- ✅ Real-time document upload tracking
- ✅ Application submission with validation
- ✅ Email notifications

### Admin Portal (Authenticated)
- ✅ Secure JWT authentication
- ✅ Dashboard with analytics and charts
- ✅ Supplier application review
- ✅ Document verification (approve/reject)
- ✅ Request additional information
- ✅ Approve/reject applications
- ✅ Audit logging
- ✅ Filtering and search
- ✅ Export reports

### Document Management
- ✅ AWS S3 storage with presigned URLs
- ✅ Mandatory documents (all suppliers):
  - Company Profile
  - Certificate of Incorporation
  - CR14 or CR6
  - VAT Certificate
  - Tax Clearance Certificate
  - FDMS Compliance Proof

- ✅ Category-specific documents (based on business type):
  - Health Certificate
  - ISO 9001, ISO 45001, ISO 14000
  - Internal QMS / SHEQ Policy

### Analytics & Reporting
- ✅ Overview statistics
- ✅ Suppliers by category
- ✅ Suppliers by location
- ✅ Status distribution
- ✅ Monthly trends
- ✅ Years in business analysis

## 🔄 Status Lifecycle

Supplier applications move through these statuses:

1. **INCOMPLETE** - Started but not submitted
2. **SUBMITTED** - Awaiting admin review
3. **UNDER_REVIEW** - Admin is reviewing
4. **NEED_MORE_INFO** - Additional info requested
5. **APPROVED** - Application approved
6. **REJECTED** - Application rejected

## 🛠️ Development

### Backend Development

```powershell
# Run with auto-reload
python -m app.main

# Run tests
pytest

# Format code
black app/
isort app/

# Type checking
mypy app/
```

### Frontend Development

```powershell
# Development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint
npm run lint
```

## 📦 Deployment

### Backend Deployment

**Recommended platforms**: Railway, Render, AWS Lambda (with Mangum)

1. Set all environment variables
2. Set `APP_ENV=production` and `DEBUG=false`
3. Run migrations on production database
4. Deploy application

### Frontend Deployment

**Recommended platform**: Vercel (optimal for Next.js)

1. Connect your repository to Vercel
2. Set environment variables
3. Deploy automatically on push to main

## 🔒 Security Features

- ✅ JWT authentication for admin users
- ✅ Password hashing with bcrypt
- ✅ Presigned URLs for secure file uploads/downloads
- ✅ Input validation with Pydantic/Zod
- ✅ CORS protection
- ✅ SQL injection prevention
- ✅ Rate limiting (recommended to add)
- ✅ Audit logging for all admin actions
- ✅ Automatic rejected application cleanup (30 days)

## 📧 Email Notifications

Automated emails are sent for:
- Supplier registration submitted
- Application approved
- Application rejected
- More information requested

## 🐛 Troubleshooting

### Backend Issues

**Database connection error**:
- Verify Supabase URL and keys in `.env`
- Check if migrations ran successfully

**S3 upload error**:
- Verify AWS credentials
- Check S3 bucket permissions and CORS config

**Email sending fails**:
- Check SendGrid API key or SMTP credentials
- Verify sender email is verified

### Frontend Issues

**API calls failing**:
- Ensure backend is running
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Check browser console for CORS errors

**Authentication not working**:
- Clear localStorage
- Check JWT token expiration settings
- Verify admin credentials

## 📞 Support

For issues or questions:
1. Check the README files in `backend/` and `frontend/` directories
2. Review API documentation at `/v1/docs`
3. Check application logs

## 📝 License

Proprietary - All Rights Reserved

---

**Built with ❤️ using FastAPI and Next.js**
