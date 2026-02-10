# Audit Logs Fix - Deployment Guide

## Issue
The audit logging system is failing with the error:
```
Could not find the 'admin_email' column of 'audit_logs' in the schema cache
```

This occurs because the `audit_logs` table in the database is missing the `admin_email` column that the application code expects.

## Root Cause
There's a mismatch between the database schema and the application code:
- The application's `AuditService` (in `app/services/audit_service.py`) expects an `admin_email` column
- The current database table may be missing this column

## Solution

### Step 1: Run the Migration
Execute the migration file `015_fix_audit_logs_schema.sql` in your Supabase database.

**Option A: Using Supabase Dashboard (Recommended)**
1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Create a new query
4. Copy the entire contents of `backend/app/db/migrations/015_fix_audit_logs_schema.sql`
5. Paste into the SQL editor
6. Click **Run** or press `Ctrl+Enter`

**Option B: Using Supabase CLI**
```bash
# From the backend directory
supabase db push
```

### Step 2: Verify the Migration
After running the migration, verify the schema:

```sql
-- Check that all required columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'audit_logs'
ORDER BY ordinal_position;
```

Expected columns should include:
- `id` (UUID)
- `admin_id` (UUID)
- `admin_email` (VARCHAR) ← This should now exist
- `action` (VARCHAR)
- `target_type` (VARCHAR)
- `target_id` (UUID)
- `details` (JSONB)
- `ip_address` (INET)
- `created_at` (TIMESTAMP WITH TIME ZONE)

### Step 3: Test the Fix
1. Restart your backend server (if running)
2. Log in to the admin dashboard
3. Navigate to **Audit Activity** page
4. The audit logs should now be visible
5. Check the terminal - the errors should be gone:
   - No more "Could not find the 'admin_email' column" errors
   - No more "Audit logging error" messages

### Step 4: Verify Audit Logs Are Being Created
Perform some actions and verify they're logged:

**Actions to test:**
1. **Login**: Log in to admin dashboard
2. **View Analytics**: Navigate to dashboard and view charts
3. **View Suppliers**: Go to suppliers list page
4. **View Supplier Details**: Click on a supplier

**Check logs in database:**
```sql
SELECT 
    id,
    admin_email,
    action,
    target_type,
    created_at
FROM audit_logs
ORDER BY created_at DESC
LIMIT 10;
```

**Check logs in UI:**
1. Navigate to admin dashboard
2. Look for "Audit Activity" or "Audit Logs" section
3. Verify recent actions appear in the list

## What This Migration Does

The migration script (`015_fix_audit_logs_schema.sql`):

1. **Adds Missing Column**: Adds the `admin_email` column if it doesn't exist
2. **Handles Multiple Schema Versions**: Detects which migration version you're using and adapts accordingly
3. **Migrates Existing Data**: If you have the 004 migration structure, it copies `user_email` → `admin_email`
4. **Ensures Compatibility**: Makes sure all required columns exist for the application code
5. **Makes Column Nullable**: Sets `admin_email` to allow NULL (for system actions)
6. **Adds Index**: Creates an index on `admin_email` for faster queries
7. **Sets Defaults**: Ensures `created_at` has a default timestamp

## Troubleshooting

### If migration fails with "column already exists"
This is safe to ignore - it means the column was already added. The migration uses `IF NOT EXISTS` checks.

### If you still see errors after migration
1. **Clear Supabase cache**:
   ```sql
   NOTIFY pgrst, 'reload schema';
   ```
   Or restart your Supabase project (in dashboard: Settings → General → Restart project)

2. **Verify the migration ran**:
   ```sql
   SELECT * FROM information_schema.columns 
   WHERE table_name = 'audit_logs' AND column_name = 'admin_email';
   ```
   Should return 1 row if the column exists.

3. **Check for RLS policies blocking inserts**:
   ```sql
   SELECT * FROM pg_policies WHERE tablename = 'audit_logs';
   ```

4. **Restart backend server**: Stop and restart the Python backend to clear any cached schemas.

### If audit logs still don't appear in UI
1. Check the browser console for errors (F12 → Console tab)
2. Check the Network tab (F12 → Network) when loading audit logs page
3. Verify the API endpoint returns data:
   ```
   GET /api/v1/audit/logs?limit=50&offset=0
   ```

## Expected Behavior After Fix

✅ **No errors in terminal** when performing admin actions
✅ **Audit logs visible** in the admin dashboard UI
✅ **All actions logged**:
   - Login/logout events
   - Analytics access (dashboard views, chart interactions)
   - Supplier actions (view, approve, reject)
   - Document actions (view, verify, download)
   - User management actions
   - Message actions

## Audit Log Coverage

After the fix, the following activities will be logged:

| Activity | Action Constant | Logged When |
|----------|----------------|-------------|
| Login | `LOGIN` | User successfully logs in |
| Logout | `LOGOUT` | User logs out |
| Failed Login | `LOGIN_FAILED` | Login attempt fails |
| View Analytics | `ANALYTICS_ACCESSED` | Dashboard or charts viewed |
| View Supplier List | `VENDOR_LIST_VIEWED` | Suppliers page loaded |
| View Supplier | `VENDOR_VIEWED` | Supplier details page opened |
| Approve Supplier | `VENDOR_APPROVED` | Supplier status changed to approved |
| Reject Supplier | `VENDOR_REJECTED` | Supplier status changed to rejected |
| Document Upload | `DOCUMENT_UPLOADED` | File uploaded |
| Document View | `DOCUMENT_VIEWED` | Document downloaded or viewed |

## Files Modified
- ✅ Created: `backend/app/db/migrations/015_fix_audit_logs_schema.sql`
- ℹ️ Existing: `backend/app/services/audit_service.py` (no changes needed)
- ℹ️ Existing: `backend/app/api/routes/analytics.py` (already has audit logging)

## Next Steps
After confirming the fix works:
1. Monitor audit logs for a few days
2. Consider adding more audit points if needed
3. Set up audit log retention policy (archive old logs after 1+ year)
4. Add reporting/dashboard for audit analytics
