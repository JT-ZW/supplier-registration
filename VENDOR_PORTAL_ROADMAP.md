# 🏢 Vendor Portal Transformation Roadmap

## Current State vs. Target State

### ❌ **Current State**
- One-time registration form only
- No vendor login or authentication
- No way to track application status
- No post-registration access
- Vendors must email/call for updates
- No self-service capabilities

### ✅ **Target State: Professional Vendor Portal**
- Dedicated vendor login system
- Personal dashboard with application status
- Real-time application tracking
- Profile self-service management
- Document renewal capability
- Communication center with admin
- Help & resources section

---

## 🎯 Implementation Phases

### **Phase 1: Landing Page Enhancement** ✅ COMPLETED
**Duration: Done**

**Improvements Made:**
- ✅ Professional hero section with value proposition
- ✅ Separate CTAs for new vs. existing vendors
- ✅ Feature showcase (6 key portal features)
- ✅ "How It Works" 4-step process
- ✅ Value proposition highlights
- ✅ Professional footer with contact info
- ✅ Trust badges and social proof

**Impact:**
- More professional first impression
- Clear user journey guidance
- Better conversion rate expected

---

### **Phase 2: Vendor Authentication System** 🔨 TO BUILD
**Duration: 2-3 days**
**Priority: HIGH**

#### **What to Build:**

**1. Vendor Login Page** `/vendor/login`
```tsx
Features:
- Email & password login form
- "Forgot password" link
- Link to registration for new vendors
- Remember me checkbox
- Professional design matching brand

Security:
- JWT token authentication
- Secure password requirements
- Rate limiting on failed attempts
- Session management
```

**2. Password Reset Flow** `/vendor/forgot-password`
```tsx
- Email input form
- Send reset link via email
- Reset password page with token validation
- Success confirmation
```

**3. Backend API Endpoints Needed:**
```python
POST /api/v1/vendor/login
POST /api/v1/vendor/forgot-password
POST /api/v1/vendor/reset-password
GET /api/v1/vendor/me  # Get current vendor profile
```

**4. Database Updates:**
```sql
-- Add to suppliers table:
ALTER TABLE suppliers ADD COLUMN password_hash VARCHAR(255);
ALTER TABLE suppliers ADD COLUMN last_login TIMESTAMP;
ALTER TABLE suppliers ADD COLUMN password_reset_token VARCHAR(255);
ALTER TABLE suppliers ADD COLUMN password_reset_expires TIMESTAMP;
```

**5. Registration Flow Update:**
- After form submission, create vendor account with password
- Send welcome email with login credentials
- Auto-login after first registration

---

### **Phase 3: Vendor Dashboard** 🔨 TO BUILD
**Duration: 3-4 days**
**Priority: HIGH**

#### **Dashboard Layout:** `/vendor/dashboard`

```
┌─────────────────────────────────────────────────────┐
│  Header: Vendor Name | Notifications | Logout       │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────────────────────────────────────┐   │
│  │  Application Status Card                     │   │
│  │  Status: Under Review                        │   │
│  │  Submitted: Jan 1, 2026                      │   │
│  │  Progress Bar: 60%                           │   │
│  │  [View Details] button                       │   │
│  └─────────────────────────────────────────────┘   │
│                                                       │
│  ┌─────────┬─────────┬─────────┐                   │
│  │ Docs    │ Messages│ Profile │                   │
│  │ 6/6     │ 2 unread│ 95%     │                   │
│  └─────────┴─────────┴─────────┘                   │
│                                                       │
│  Quick Actions:                                      │
│  [Upload Document] [Update Profile] [Contact Admin] │
│                                                       │
│  Recent Activity:                                    │
│  - Document verified: Tax Certificate               │
│  - Admin message received                           │
│  - Profile updated                                  │
│                                                       │
└─────────────────────────────────────────────────────┘
```

**Dashboard Widgets:**

1. **Application Status Card**
   - Current status badge (pending, under review, approved, rejected)
   - Progress indicator
   - Timeline of events
   - Next steps/actions required

2. **Document Status**
   - Count of uploaded documents
   - Expiring documents alert
   - Missing documents notice
   - Quick upload button

3. **Messages Center**
   - Unread message count
   - Latest message preview
   - Quick reply capability

4. **Profile Completion**
   - Percentage complete
   - Missing fields highlighted
   - Quick edit link

5. **Important Notices**
   - System announcements
   - Policy updates
   - Expiry alerts

---

### **Phase 4: Application Tracking Page** 🔨 TO BUILD
**Duration: 2 days**
**Priority: MEDIUM**

#### **Features:** `/vendor/application`

**Visual Timeline:**
```
○────────●────────●────────○────────○
   Submitted   Documents  Under      Approved
                Verified   Review
```

**Details Shown:**
- ✅ Application submitted (Jan 1, 2026 10:30 AM)
- ✅ Documents uploaded (Jan 1, 2026 11:15 AM)
- ✅ Initial review completed (Jan 2, 2026 2:45 PM)
- 🔄 Under detailed review (current)
- ⏳ Final approval (pending)

**Status Explanations:**
- What each status means
- Estimated time for each stage
- Required actions (if any)

**Admin Feedback:**
- Comments from reviewers
- Requested information
- Rejection reasons (if applicable)

---

### **Phase 5: Profile Management** 🔨 TO BUILD
**Duration: 2-3 days**
**Priority: MEDIUM**

#### **Features:** `/vendor/profile`

**1. View/Edit Company Information**
```tsx
Tabs:
├─ Company Details (name, registration#, tax ID, years in business)
├─ Contact Information (person, title, email, phone, website)
├─ Address (street, city, state, postal, country)
└─ Banking Information (for approved suppliers only)

Features:
- Inline editing or edit mode toggle
- Validation on all fields
- Changes require admin approval
- Change history log
```

**2. Account Security**
```tsx
- Change password
- Two-factor authentication (future)
- Login history
- Active sessions management
```

**3. Notifications Preferences**
```tsx
Email notifications for:
☑ Application status changes
☑ New messages from admin
☑ Document expiry reminders
☑ System announcements
□ Marketing communications
```

---

### **Phase 6: Document Management** 🔨 TO BUILD
**Duration: 2-3 days**
**Priority: HIGH**

#### **Features:** `/vendor/documents`

**Document List View:**
```
┌─────────────────────────────────────────────────────┐
│ Document Type         | Status    | Expiry   | Actions│
├─────────────────────────────────────────────────────┤
│ Business Registration | ✅ Verified| 2027-01 | View   │
│ Tax Clearance        | ✅ Verified| 2026-03 | Renew  │
│ Insurance Certificate| ⚠️ Expiring| 2026-02 | Renew  │
│ Bank Statement       | 🔄 Pending | -       | View   │
└─────────────────────────────────────────────────────┘
```

**Features:**

1. **View Documents**
   - Thumbnail preview
   - Full document viewer (PDF, images)
   - Download option
   - Verification status

2. **Upload New/Renewed Documents**
   - Drag & drop interface
   - Progress indicators
   - Automatic expiry tracking
   - Version history

3. **Expiry Management**
   - Dashboard widget showing expiring docs
   - Email reminders (90/60/30/7 days)
   - One-click renewal upload
   - Auto-notification to admin on renewal

4. **Document History**
   - All versions uploaded
   - Verification history
   - Admin comments/feedback

---

### **Phase 7: Communication Center** 🔨 TO BUILD
**Duration: 2-3 days**
**Priority: MEDIUM**

#### **Features:** `/vendor/messages`

**Inbox Layout:**
```
┌────────────────────┬──────────────────────────────────┐
│ Message List       │  Message Detail                  │
│                    │                                  │
│ ● Admin: Welcome   │  From: RTG Procurement Team      │
│   Jan 1, 2026      │  Date: Jan 1, 2026 10:00 AM      │
│                    │                                  │
│ ○ Action Required  │  Welcome to RTG Supplier Portal! │
│   Jan 2, 2026      │                                  │
│                    │  Your application has been...    │
│ ○ Document Verified│                                  │
│   Jan 3, 2026      │  [Reply] [Mark as Read]          │
│                    │                                  │
└────────────────────┴──────────────────────────────────┘
```

**Features:**

1. **Inbox**
   - Unread message counter
   - Message preview
   - Search and filter
   - Archive/delete

2. **Compose**
   - Send message to admin
   - Attach documents
   - Subject categories (general, technical, billing, etc.)
   - Rich text editor

3. **Automated Messages**
   - Application status updates
   - Document verification results
   - Expiry reminders
   - Policy updates

4. **Message Types:**
   - System notifications (automated)
   - Admin messages (from procurement team)
   - Vendor messages (your sent messages)

---

### **Phase 8: Help & Resources** 🔨 TO BUILD
**Duration: 1-2 days**
**Priority: LOW**

#### **Features:** `/vendor/help`

**Sections:**

1. **FAQ**
```
Categories:
- Getting Started
- Document Requirements
- Application Process
- Profile Management
- Troubleshooting
- Contact Information
```

2. **User Guides**
   - How to register
   - How to upload documents
   - How to update profile
   - Video tutorials (future)

3. **Document Requirements**
   - List of required documents by category
   - Sample documents (redacted examples)
   - Acceptable formats
   - Quality guidelines

4. **Contact Support**
   - Email: procurement@rtg.com
   - Phone: +263 123 456 789
   - Hours: Mon-Fri 8AM-5PM
   - Ticketing system (future)

---

## 🚀 Quick Start Implementation Guide

### **To Build Vendor Authentication (Phase 2):**

#### **1. Backend - Add Vendor Auth Endpoints**

```python
# backend/app/api/routes/vendor_auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from app.core.security import hash_password, verify_password, create_access_token
from app.db.supabase import get_supabase_client
import secrets
from datetime import datetime, timedelta

router = APIRouter(prefix="/vendor", tags=["vendor-auth"])
security = HTTPBearer()

class VendorLoginRequest(BaseModel):
    email: EmailStr
    password: str

class VendorLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    supplier: dict

@router.post("/login")
async def vendor_login(credentials: VendorLoginRequest):
    """Vendor login endpoint"""
    supabase = get_supabase_client()
    
    # Get supplier by email
    result = supabase.table("suppliers").select("*").eq("email", credentials.email).execute()
    
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    supplier = result.data[0]
    
    # Verify password
    if not verify_password(credentials.password, supplier.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Update last login
    supabase.table("suppliers").update({
        "last_login": datetime.utcnow().isoformat()
    }).eq("id", supplier["id"]).execute()
    
    # Create access token
    token = create_access_token({"sub": supplier["id"], "type": "vendor"})
    
    # Remove sensitive data
    supplier.pop("password_hash", None)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "supplier": supplier
    }

@router.post("/forgot-password")
async def forgot_password(email: EmailStr):
    """Send password reset email"""
    supabase = get_supabase_client()
    
    result = supabase.table("suppliers").select("id, email, company_name").eq("email", email).execute()
    
    if result.data:
        supplier = result.data[0]
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)
        
        # Save token
        supabase.table("suppliers").update({
            "password_reset_token": reset_token,
            "password_reset_expires": expires.isoformat()
        }).eq("id", supplier["id"]).execute()
        
        # Send email (use your email service)
        # send_password_reset_email(email, reset_token)
    
    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a reset link has been sent"}

@router.get("/me")
async def get_current_vendor(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current logged-in vendor"""
    # Decode and validate token
    # Return vendor profile
    pass
```

#### **2. Frontend - Vendor Login Page**

```tsx
// frontend/src/app/vendor/login/page.tsx

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Input from "@/components/shared/Input";
import Button from "@/components/shared/Button";
import toast from "react-hot-toast";

export default function VendorLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/v1/vendor/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) throw new Error("Invalid credentials");

      const data = await response.json();
      
      // Store token
      localStorage.setItem("vendor_token", data.access_token);
      localStorage.setItem("vendor_data", JSON.stringify(data.supplier));
      
      toast.success("Welcome back!");
      router.push("/vendor/dashboard");
    } catch (error) {
      toast.error("Login failed. Please check your credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
          Vendor Portal Login
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          Or{" "}
          <Link href="/register" className="font-medium text-indigo-600 hover:text-indigo-500">
            register as a new supplier
          </Link>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <form className="space-y-6" onSubmit={handleLogin}>
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <input
                  id="remember-me"
                  name="remember-me"
                  type="checkbox"
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-900">
                  Remember me
                </label>
              </div>

              <div className="text-sm">
                <Link href="/vendor/forgot-password" className="font-medium text-indigo-600 hover:text-indigo-500">
                  Forgot your password?
                </Link>
              </div>
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
```

---

## 📊 Feature Priority Matrix

| Feature | User Value | Implementation Effort | Priority |
|---------|-----------|----------------------|----------|
| Landing Page | High | Low | ✅ Done |
| Vendor Login | Critical | Medium | 🔴 Phase 2 |
| Dashboard | Critical | Medium | 🔴 Phase 3 |
| Document Management | High | Medium | 🟡 Phase 6 |
| Application Tracking | Medium | Low | 🟢 Phase 4 |
| Profile Management | Medium | Medium | 🟢 Phase 5 |
| Communication Center | Medium | Medium | 🟢 Phase 7 |
| Help & Resources | Low | Low | 🔵 Phase 8 |

---

## 🎯 Success Metrics

**Portal Effectiveness:**
- Vendor login rate > 70% of registered suppliers
- Dashboard engagement > 80% of logged-in vendors
- Self-service document uploads > 60%
- Reduction in support emails by 50%

**User Satisfaction:**
- Portal ease-of-use rating > 4/5
- Application status visibility improvement
- Faster response time perception

**Operational Efficiency:**
- Admin time saved on status inquiries
- Reduced back-and-forth email communication
- Faster document renewal process

---

## 🔧 Technical Requirements

**Backend:**
- Add vendor authentication endpoints
- Add password hashing/verification
- JWT token management
- Password reset flow
- Vendor-specific middleware

**Frontend:**
- Vendor authentication context
- Protected vendor routes
- Dashboard components
- Profile management forms
- Document upload interface

**Database:**
- Add password fields to suppliers table
- Add last_login tracking
- Add password reset tokens
- Add communication/messages table

---

## 📝 Next Steps

1. ✅ **Landing page enhancement** - COMPLETED
2. **Build vendor authentication** - Start here next
3. **Create vendor dashboard** - Core portal experience
4. **Add document management** - High-value feature
5. **Implement remaining features** - Based on priority

Would you like me to start building Phase 2 (Vendor Authentication System)?
