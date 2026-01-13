# AWS S3 Setup Guide for Procurement System

## Prerequisites
- AWS Account (if you don't have one, go to https://aws.amazon.com and click "Create an AWS Account")

---

## Step 1: Create an S3 Bucket

1. **Log in to AWS Console**
   - Go to https://console.aws.amazon.com
   - Sign in with your credentials

2. **Navigate to S3**
   - In the search bar at the top, type "S3"
   - Click on "S3" from the results

3. **Create New Bucket**
   - Click the orange "Create bucket" button
   
4. **Configure Bucket Settings:**

   **General Configuration:**
   - **Bucket name:** `procurement-documents-prod` (must be globally unique)
     - If taken, try: `procurement-docs-yourname` or `procurement-docs-2025`
   - **AWS Region:** Choose closest to you (e.g., `us-east-1` for US East, `eu-west-1` for Ireland)
     - **IMPORTANT:** Note down your region - you'll need it later!

   **Object Ownership:**
   - Keep default: "ACLs disabled (recommended)"

   **Block Public Access settings:**
   - Keep ALL checkboxes CHECKED (Block all public access)
   - This is correct - documents should NOT be publicly accessible

   **Bucket Versioning:**
   - Keep "Disable" selected (optional - you can enable if you want version history)

   **Default encryption:**
   - Keep default: "Server-side encryption with Amazon S3 managed keys (SSE-S3)"

   **Advanced settings:**
   - Keep defaults

5. **Create the Bucket**
   - Scroll down and click "Create bucket"
   - You should see a success message

---

## Step 2: Create IAM User with S3 Permissions

1. **Navigate to IAM**
   - In the search bar, type "IAM"
   - Click on "IAM" from the results

2. **Go to Users**
   - In the left sidebar, click "Users"
   - Click "Create user" button

3. **Specify User Details**
   - **User name:** `procurement-app-user`
   - Click "Next"

4. **Set Permissions**
   - Select "Attach policies directly"
   - In the search box, type "S3"
   - Find and CHECK the box for **"AmazonS3FullAccess"**
     - (For production, you'd create a custom policy with only necessary permissions, but this is fine for now)
   - Click "Next"

5. **Review and Create**
   - Review the settings
   - Click "Create user"

---

## Step 3: Generate Access Keys

1. **Click on the User**
   - From the Users list, click on `procurement-app-user`

2. **Create Access Key**
   - Click the "Security credentials" tab
   - Scroll down to "Access keys" section
   - Click "Create access key"

3. **Select Use Case**
   - Select "Application running outside AWS"
   - Check the confirmation checkbox at the bottom
   - Click "Next"

4. **Description (Optional)**
   - Add description: "Procurement System Backend"
   - Click "Create access key"

5. **SAVE YOUR CREDENTIALS** ⚠️
   - You'll see:
     - **Access key ID** (looks like: AKIAIOSFODNN7EXAMPLE)
     - **Secret access key** (looks like: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY)
   
   - **IMPORTANT:** 
     - Click "Download .csv file" to save these credentials
     - OR copy them somewhere safe NOW
     - You CANNOT view the secret key again after closing this page!

6. **Click "Done"**

---

## Step 4: Test S3 Access (Optional but Recommended)

1. **Go back to S3**
   - Search for "S3" and go to your bucket

2. **Upload a Test File**
   - Click on your bucket name
   - Click "Upload"
   - Click "Add files" and select any small file
   - Click "Upload"
   - If successful, S3 is working!

---

## Step 5: Update Backend Configuration

You'll need these values:
- ✅ AWS Access Key ID
- ✅ AWS Secret Access Key
- ✅ S3 Bucket Name (e.g., `procurement-documents-prod`)
- ✅ AWS Region (e.g., `us-east-1`, `eu-west-1`, `ap-southeast-1`)

Once you have all these, let me know and I'll update your `.env` file!

---

## Common AWS Regions:

| Region Name | Region Code |
|------------|-------------|
| US East (N. Virginia) | us-east-1 |
| US East (Ohio) | us-east-2 |
| US West (N. California) | us-west-1 |
| US West (Oregon) | us-west-2 |
| Europe (Ireland) | eu-west-1 |
| Europe (London) | eu-west-2 |
| Europe (Frankfurt) | eu-central-1 |
| Asia Pacific (Singapore) | ap-southeast-1 |
| Asia Pacific (Sydney) | ap-southeast-2 |
| Asia Pacific (Tokyo) | ap-northeast-1 |
| Africa (Cape Town) | af-south-1 |

---

## Troubleshooting

**"Bucket name already taken"**
- Bucket names must be globally unique across ALL AWS accounts
- Try adding your name or random numbers: `procurement-docs-john-2025`

**"Access Denied" errors**
- Make sure the IAM user has `AmazonS3FullAccess` policy
- Check that you're using the correct Access Key and Secret Key

**"Region" errors**
- Make sure the region in your `.env` matches where you created the bucket

---

## Security Notes

✅ **DO:**
- Keep your access keys secret
- Never commit them to git
- Use environment variables (`.env` file)
- Block public access on your bucket

❌ **DON'T:**
- Share your access keys
- Make your bucket public
- Commit `.env` to version control

---

## Next Steps

After completing all steps above, provide me with:
1. Your S3 bucket name
2. Your AWS region code
3. Your Access Key ID
4. Your Secret Access Key

I'll help you configure the backend!
