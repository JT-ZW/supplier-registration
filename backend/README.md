# Supplier Registration & Approval System - Backend

FastAPI backend for the procurement supplier registration and approval system.

## Features

- **Supplier Registration**: Guest users can register and upload documents
- **Admin Portal**: Authenticated admin can review and approve applications
- **Document Management**: Secure file uploads via presigned URLs to AWS S3
- **Analytics**: Comprehensive reporting and statistics
- **Audit Logging**: Track all admin actions
- **Email Notifications**: Automated emails for key events

## Tech Stack

- **Framework**: FastAPI
- **Database**: Supabase (PostgreSQL)
- **Storage**: AWS S3
- **Authentication**: JWT tokens
- **Email**: SendGrid / SMTP

## Setup

### 1. Create Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and update the values:

```powershell
Copy-Item .env.example .env
```

Required configuration:
- Supabase URL and keys
- AWS S3 credentials
- JWT secret key
- Email service credentials (SendGrid or SMTP)

### 4. Run Database Migrations

Execute the SQL migrations in Supabase:
1. Go to your Supabase dashboard
2. Navigate to SQL Editor
3. Run the migrations in order:
   - `app/db/migrations/001_initial_schema.sql`
   - `app/db/migrations/002_seed_data.sql`

### 5. Run the Application

```powershell
# Development mode with auto-reload
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: http://localhost:8000

API Documentation: http://localhost:8000/v1/docs

## Default Admin Credentials

After running the seed migration:
- Email: `admin@procurement.com`
- Password: `Admin123!`

**⚠️ Change this password immediately after first login!**

## API Endpoints

### Supplier Endpoints (Public)
- `POST /v1/supplier/register` - Create new supplier application
- `GET /v1/supplier/{id}` - Get supplier details
- `PUT /v1/supplier/{id}` - Update supplier information
- `POST /v1/supplier/{id}/submit` - Submit application for review
- `GET /v1/supplier/{id}/documents/status` - Check document upload status

### Document Endpoints (Public)
- `POST /v1/documents/upload-url` - Get presigned upload URL
- `POST /v1/documents/confirm-upload` - Confirm document uploaded
- `GET /v1/documents/{id}/download-url` - Get download URL
- `GET /v1/documents/{id}/view-url` - Get view URL

### Admin Endpoints (Authenticated)
- `POST /v1/admin/login` - Admin login
- `POST /v1/admin/refresh` - Refresh access token
- `GET /v1/admin/me` - Get current admin profile
- `GET /v1/admin/suppliers` - List all supplier applications
- `GET /v1/admin/suppliers/{id}` - Get supplier details
- `POST /v1/admin/suppliers/{id}/review` - Review application
- `POST /v1/admin/suppliers/{id}/request-info` - Request more info
- `POST /v1/admin/documents/{id}/verify` - Verify/reject document

### Analytics Endpoints (Authenticated)
- `GET /v1/analytics/overview` - Overview statistics
- `GET /v1/analytics/categories` - Category distribution
- `GET /v1/analytics/locations` - Location distribution
- `GET /v1/analytics/years-in-business` - Years in business stats
- `GET /v1/analytics/status-distribution` - Status distribution
- `GET /v1/analytics/monthly-trends` - Monthly trends
- `GET /v1/analytics/dashboard-summary` - Complete dashboard data

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py              # Dependencies (auth, etc.)
│   │   └── routes/
│   │       ├── supplier.py      # Supplier registration routes
│   │       ├── documents.py     # Document management routes
│   │       ├── admin.py         # Admin & review routes
│   │       └── analytics.py     # Analytics routes
│   ├── core/
│   │   ├── config.py            # Configuration settings
│   │   ├── security.py          # JWT & password hashing
│   │   ├── storage.py           # AWS S3 integration
│   │   └── email.py             # Email service
│   ├── db/
│   │   ├── supabase.py          # Database client
│   │   └── migrations/          # SQL migrations
│   ├── models/
│   │   ├── enums.py             # Enums and constants
│   │   ├── supplier.py          # Supplier models
│   │   ├── document.py          # Document models
│   │   ├── admin.py             # Admin models
│   │   ├── analytics.py         # Analytics models
│   │   └── common.py            # Common models
│   └── main.py                  # FastAPI app entry point
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## Development

### Run Tests

```powershell
pytest
```

### Code Formatting

```powershell
black app/
isort app/
```

### Type Checking

```powershell
mypy app/
```

## Deployment

### Environment Variables

Ensure all production environment variables are set:
- Set `APP_ENV=production`
- Set `DEBUG=false`
- Use strong `JWT_SECRET_KEY`
- Configure production database and storage

### Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Security Considerations

1. **JWT Tokens**: Short-lived access tokens (30 min) with refresh tokens
2. **Password Hashing**: Bcrypt with salt
3. **File Upload**: Presigned URLs to avoid direct uploads through backend
4. **Input Validation**: Pydantic models for all requests
5. **CORS**: Restricted to allowed origins
6. **Rate Limiting**: Consider adding rate limiting middleware
7. **SQL Injection**: Parameterized queries via Supabase client

## License

Proprietary - All Rights Reserved
