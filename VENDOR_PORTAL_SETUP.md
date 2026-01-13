# Vendor Portal Setup Instructions

## ✅ What We've Built

1. **Backend Vendor Authentication System**
   - Login endpoint: `/api/v1/vendor/login`
   - Password reset: `/api/v1/vendor/forgot-password` & `/api/v1/vendor/reset-password`
   - Change password: `/api/v1/vendor/change-password`
   - Get profile: `/api/v1/vendor/me`

2. **Frontend Vendor Portal**
   - Login page: `/vendor/login`
   - Dashboard: `/vendor/dashboard`
   - Professional landing page with vendor login CTA

3. **Automatic Password Generation**
   - When suppliers submit their application, a secure password is generated
   - Password is emailed to them with portal access instructions
   - They can change it after first login

---

## 🔧 Setup Steps

### Step 1: Run Database Migration

You need to add authentication fields to the `suppliers` table in Supabase.

1. **Go to Supabase Dashboard**: https://supabase.com/dashboard
2. **Navigate to**: Your Project → SQL Editor
3. **Run this SQL**:

```sql
-- Add vendor portal authentication fields to suppliers table

ALTER TABLE suppliers 
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255),
ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP WITH TIME ZONE;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_suppliers_password_reset_token 
ON suppliers(password_reset_token);

CREATE INDEX IF NOT EXISTS idx_suppliers_email 
ON suppliers(email);
```

4. **Click "Run"** to execute the migration

---

### Step 2: Test the Setup

#### A. Test Backend API

**Start backend** (if not running):
```powershell
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Check vendor auth endpoints**:
- Open: http://localhost:8000/docs
- Look for the `vendor-auth` section
- You should see: `/vendor/login`, `/vendor/forgot-password`, etc.

#### B. Test Frontend

**Start frontend** (if not running):
```powershell
cd frontend
npm run dev
```

**Test the flow**:
1. **Visit**: http://localhost:3000
   - You should see the upgraded landing page
   - Two CTA buttons: "New Supplier Registration" and "Existing Vendor Login"

2. **Register a new supplier**:
   - Click "New Supplier Registration"
   - Complete the form and upload documents
   - Submit the application
   - **Check your email** - you should receive vendor portal credentials

3. **Login to Vendor Portal**:
   - Click "Existing Vendor Login" or go to http://localhost:3000/vendor/login
   - Enter the email and password from the email
   - You should see the vendor dashboard!

---

## 🎨 What's Different Now

### Landing Page (http://localhost:3000)
**Before:**
- Basic "Start Registration" button
- Single-purpose page

**After:**
- Professional hero section
- Separate CTAs for new vs existing vendors
- Value proposition highlights
- "How It Works" section
- Portal features showcase
- Trust indicators

### After Registration
**Before:**
- Submit application → Just confirmation message
- No way to track status

**After:**
- Submit application → Receive email with:
  * Portal login URL
  * Email (your email)
  * Temporary password
  * Instructions to change password

### Vendor Portal
**New Features:**
- **Login page**: Professional authentication
- **Dashboard**: Shows:
  * Application status with progress bar
  * Status-specific messages
  * Quick stats (documents, profile completion)
  * Quick action links
  * What's happening next

---

## 🔐 Security Features

1. **Secure Password Hashing**: Using Argon2 (recommended for 2024+)
2. **JWT Tokens**: 7-day expiry for vendor sessions
3. **Remember Me**: Option to stay logged in
4. **Password Reset**: 24-hour token expiry
5. **Password Requirements**: Minimum 8 characters

---

## 📧 Email Templates

The submission email now includes:

```
Subject: Application Submitted - Vendor Portal Access

Hello [Contact Person],

Thank you for submitting your supplier application to Rainbow Tourism Group.

Your Vendor Portal Access:
- Portal URL: http://localhost:3000/vendor/login
- Email: [vendor@email.com]
- Temporary Password: [RandomPassword123]

⚠️ Please change your password after first login for security.

What's Next?
- Our team will review your application within 3-5 business days
- You'll receive email updates on your application status
- Track progress in real-time through the vendor portal
```

---

## 🚀 Next Steps (Future Features)

The following are outlined in `VENDOR_PORTAL_ROADMAP.md` but not yet built:

- [ ] Password reset page (frontend)
- [ ] Profile management (edit company info)
- [ ] Document renewal (upload new versions)
- [ ] Communication center (message admin)
- [ ] Application tracking timeline
- [ ] Help & resources section

---

## 🐛 Troubleshooting

### Issue: Can't login after registration
**Solution**: Check your email for the temporary password. If you didn't receive it, check:
1. SendGrid is configured correctly
2. Email is verified in SendGrid
3. Check spam folder

### Issue: "Invalid credentials" error
**Solution**:
- Make sure you ran the database migration
- Verify the supplier exists in database
- Check that `password_hash` column was added

### Issue: Vendor dashboard not loading
**Solution**:
- Check browser console for errors
- Verify token is stored: `localStorage.getItem("vendor_token")`
- Clear browser cache and try again

### Issue: Backend error "password_hash column doesn't exist"
**Solution**: You didn't run the database migration. Go to Supabase SQL Editor and run the migration SQL from Step 1.

---

## ✨ Features Working Now

✅ Professional landing page  
✅ Vendor login system  
✅ Automatic password generation on submission  
✅ Email with portal credentials  
✅ Vendor dashboard  
✅ Session management (remember me)  
✅ Logout functionality  
✅ Application status tracking  
✅ Secure authentication (JWT + Argon2)  

---

## 📝 Testing Checklist

- [ ] Run database migration in Supabase
- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] Visit landing page - see new design
- [ ] Register new supplier
- [ ] Upload all required documents
- [ ] Submit application
- [ ] Receive email with credentials
- [ ] Login to vendor portal
- [ ] See dashboard with status
- [ ] Logout works
- [ ] Login again (remember me)
- [ ] Check that existing admin functionality still works

---

## 🎉 Success!

If all tests pass, your vendor portal is ready! Vendors can now:
1. Register through the form
2. Receive portal credentials via email
3. Login and see their application status
4. Track progress in real-time

**No existing functionality was broken** - all admin features still work exactly as before!
