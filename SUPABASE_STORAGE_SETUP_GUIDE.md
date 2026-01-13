# Supabase Storage Setup Guide

## Step 1: Create Storage Bucket (3 minutes)

1. **Go to Supabase Dashboard**
   - Visit: https://supabase.com/dashboard
   - Select your project: `zlihidqygautsseqatfq`

2. **Navigate to Storage**
   - Click "Storage" in the left sidebar (bucket icon)
   - You'll see the Storage page

3. **Create New Bucket**
   - Click "New bucket" button (top right)
   
4. **Configure Bucket**
   - **Name:** `supplier-documents`
   - **Public bucket:** Toggle OFF (keep it private/secure)
   - Click "Create bucket"

---

## Step 2: Set Up Storage Policies (2 minutes)

After creating the bucket, you need to set access policies.

1. **Click on your bucket** (`supplier-documents`)

2. **Go to Policies Tab**
   - Click "Policies" button at the top

3. **Add Policies** (Click "New Policy")

### Policy 1: Allow Service Role to Upload

Click "Create a new policy" and use this:

```sql
CREATE POLICY "Service role can upload"
ON storage.objects FOR INSERT
TO service_role
WITH CHECK (bucket_id = 'supplier-documents');
```

### Policy 2: Allow Service Role to Read

```sql
CREATE POLICY "Service role can read"
ON storage.objects FOR SELECT
TO service_role
USING (bucket_id = 'supplier-documents');
```

### Policy 3: Allow Service Role to Update

```sql
CREATE POLICY "Service role can update"
ON storage.objects FOR UPDATE
TO service_role
USING (bucket_id = 'supplier-documents');
```

### Policy 4: Allow Service Role to Delete

```sql
CREATE POLICY "Service role can delete"
ON storage.objects FOR DELETE
TO service_role
USING (bucket_id = 'supplier-documents');
```

**Alternative (Easier):** Just add ONE policy with full access:

```sql
CREATE POLICY "Service role full access"
ON storage.objects
TO service_role
USING (bucket_id = 'supplier-documents')
WITH CHECK (bucket_id = 'supplier-documents');
```

---

## Step 3: Test (Optional)

1. **Try uploading a test file**
   - In the Storage page, click on your bucket
   - Click "Upload file"
   - Upload any test PDF or image
   - If successful, storage is working!

2. **Delete test file** (optional)
   - Select the file and delete it

---

## What You Need to Provide Me

Once you complete the steps above, just confirm:
- ✅ Bucket `supplier-documents` created
- ✅ Policies added

I already have your Supabase credentials, so I'll immediately update the backend code!

---

## Benefits of Supabase Storage

✅ **Automatic CDN** - Fast file delivery  
✅ **Presigned URLs** - Secure temporary access  
✅ **Image transformations** - Resize/optimize on the fly  
✅ **Resumable uploads** - For large files  
✅ **RLS Security** - Fine-grained access control  
✅ **Free tier** - 1GB storage included  

---

Let me know when you've created the bucket and I'll update the code immediately!
