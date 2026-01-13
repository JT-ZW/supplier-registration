# SendGrid Email Setup Guide

## Step 1: Create SendGrid Account (5 minutes)

1. **Go to SendGrid**
   - Visit: https://signup.sendgrid.com/
   
2. **Fill in Registration Form**
   - Email: Your email address
   - Password: Create a strong password
   - Click "Create Account"

3. **Tell Us About Yourself** (Quick survey)
   - Select your role (e.g., "Developer")
   - Company: Your company name or "Personal Project"
   - Website: Can leave blank or use placeholder
   - How many emails: Select "Less than 40k"
   - Click "Get Started"

4. **Verify Your Email**
   - Check your inbox for SendGrid verification email
   - Click the verification link
   - You'll be redirected to SendGrid dashboard

---

## Step 2: Create API Key (3 minutes)

1. **Navigate to API Keys**
   - In SendGrid dashboard, click "Settings" in left sidebar
   - Click "API Keys"

2. **Create New API Key**
   - Click "Create API Key" button (top right)
   
3. **Configure API Key**
   - **API Key Name:** `Procurement System`
   - **API Key Permissions:** Select "Full Access" (or "Mail Send" if available)
   - Click "Create & View"

4. **SAVE YOUR API KEY** ⚠️
   - You'll see something like: `SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - **COPY IT NOW** - You cannot see it again!
   - Save it in a safe place (notepad, password manager)

5. **Click "Done"**

---

## Step 3: Verify Sender Identity (5 minutes)

SendGrid requires you to verify that you own the email address you're sending from.

### Option A: Single Sender Verification (Easiest - 5 min)

1. **Navigate to Sender Authentication**
   - Click "Settings" in left sidebar
   - Click "Sender Authentication"

2. **Verify Single Sender**
   - Under "Single Sender Verification", click "Get Started"
   - Click "Create New Sender"

3. **Fill in Sender Details**
   - **From Name:** `Procurement System` (or your company name)
   - **From Email Address:** Your email (e.g., `admin@yourcompany.com` or your Gmail)
   - **Reply To:** Same email as above (or different if you want)
   - **Company Address:** Your address
   - **City, State, Zip, Country:** Your location
   - Click "Create"

4. **Verify Email**
   - Check inbox for verification email from SendGrid
   - Click "Verify Single Sender"
   - You'll see "Sender Verified!" message

### Option B: Domain Authentication (Advanced - skip for now)
- This is for sending from your own domain (e.g., @yourcompany.com)
- Requires DNS configuration
- Can set up later if needed

---

## Step 4: Test SendGrid (Optional - 2 minutes)

1. **Send Test Email**
   - In SendGrid dashboard, go to "Email API" → "Integration Guide"
   - Select "SMTP Relay" or "Web API"
   - SendGrid will show you test code
   - You can test it if you want, or skip (we'll test via our app)

---

## Step 5: Provide Information to AI Assistant

Once you've completed steps 1-3 above, provide me with:

✅ **SendGrid API Key** (starts with `SG.`)
✅ **Verified Sender Email** (the email you verified in Step 3)
✅ **From Name** (e.g., "Procurement System")

I'll then:
1. Update your backend `.env` file
2. Configure email service
3. Create email templates
4. Test email notifications

---

## Important Notes

### ✅ **Free Tier Limits**
- 100 emails per day forever
- No credit card required
- Perfect for development and small-scale production

### 🔒 **Security**
- Keep your API key secret
- Never commit it to git
- It's like a password for sending emails

### 📧 **Email Deliverability**
- Emails might go to spam initially
- Recipients should mark as "Not Spam"
- Domain authentication (Option B) improves deliverability

### ⚠️ **Common Issues**

**"Email not verified"**
- Check spam folder for verification email
- Resend verification from SendGrid dashboard

**"API key invalid"**
- Make sure you copied the entire key (starts with `SG.`)
- No extra spaces or line breaks

**"Sender not verified"**
- Complete Step 3 (Single Sender Verification)
- Check that verification email was clicked

---

## Ready?

Start with **Step 1** and work through each step. Let me know when you have:
1. ✅ API Key
2. ✅ Verified sender email
3. ✅ From name

Then I'll configure everything for you! 🚀
