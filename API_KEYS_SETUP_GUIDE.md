# API Keys & Settings Setup Guide

## Quick Reference - All Required Keys & Where to Get Them

### Overview Table

| Service | Key Name | What It Does | Security | Where to Get | Renewal |
|---------|----------|-------------|----------|-------------|---------|
| **Firebase** | `FIREBASE_SERVICE_ACCOUNT_BASE64` | Backend auth & database | 🔐 Secret | GCP Console | Every 6 months |
| **Firebase** | `NEXT_PUBLIC_FIREBASE_*` | Frontend auth & database | 🟢 Public | Firebase Console | N/A |
| **PayTrust** | `PAYTRUST_API_KEY` | Payment processing | 🔐 Secret | PayTrust Dashboard | Every 90 days |
| **PayTrust** | `PAYTRUST_SIGNING_KEY` | Webhook verification | 🔐 Secret | PayTrust Dashboard | Every 90 days |
| **Replicate** | `REPLICATE_API_TOKEN` | AI video generation | 🔐 Secret | Replicate Dashboard | Every 90 days |
| **SendGrid** | `SENDGRID_API_KEY` | Email sending (optional) | 🔐 Secret | SendGrid Dashboard | Every 90 days |

---

## Step-by-Step Setup

### 1️⃣ FIREBASE BACKEND SETUP

**⏱️ Time needed**: 10-15 minutes

#### Step 1: Create Service Account Key

```bash
# 1. Go to: https://console.firebase.google.com/
# 2. Select your project
# 3. Click ⚙️ Settings (gear icon)
# 4. Go to "Service Accounts" tab
# 5. Click "Generate New Private Key"
# 6. Save the JSON file as: serviceAccountKey.json
```

#### Step 2: Encode to Base64

```bash
# On Mac/Linux:
cat serviceAccountKey.json | base64 > encoded_key.txt

# On Windows (PowerShell):
[System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes("serviceAccountKey.json")) | Out-File encoded_key.txt

# Copy the content of encoded_key.txt
cat encoded_key.txt  # Copy entire output
```

#### Step 3: Add to Backend Environment

**Backend `.env` file**:
```bash
# Firebase
FIREBASE_SERVICE_ACCOUNT_BASE64="<paste-entire-base64-string-here>"
FIREBASE_PROJECT_ID="your-project-id"
```

#### Step 4: Secure the JSON File

```bash
# CRITICAL: Never commit the JSON file
echo "serviceAccountKey.json" >> .gitignore
rm serviceAccountKey.json  # Delete from computer after encoding
```

---

### 2️⃣ FIREBASE FRONTEND SETUP

**⏱️ Time needed**: 5 minutes

#### Step 1: Get Firebase Web Config

```
1. Go to: https://console.firebase.google.com/
2. Select your project
3. Click ⚙️ Settings → Project Settings
4. Scroll to "Your apps" section
5. Click on your web app
6. Copy the firebaseConfig object
```

#### Step 2: Add to Frontend Environment

**Frontend `.env.local`**:
```bash
# Firebase Web Config (can be public - restricted in console)
NEXT_PUBLIC_FIREBASE_API_KEY="AIza..."
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
NEXT_PUBLIC_FIREBASE_PROJECT_ID="your-project-id"
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="your-project.appspot.com"
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="123456789"
NEXT_PUBLIC_FIREBASE_APP_ID="1:123456789:web:abcdef..."
NEXT_PUBLIC_FIREBASE_DATABASE_URL="https://your-project-id.firebaseio.com"
```

#### Step 3: Restrict API Key (Important!)

```
1. Go to: https://console.cloud.google.com/apis/credentials
2. Find your "Browser key" (API Key)
3. Click to edit
4. Go to "API restrictions" tab
5. Select "Restrict key" and choose:
   - Cloud Firestore API
   - Cloud Storage API
   - Firebase Authentication
6. Save changes
```

---

### 3️⃣ PAYTRUST PAYMENT SETUP

**⏱️ Time needed**: 10-15 minutes

#### Step 1: Get API Keys

```
1. Go to: https://dashboard.paytrust.eu/ (or your PayTrust provider)
2. Login to your account
3. Go to: Settings → API Keys (or similar)
4. You'll see:
   - Live API Key: pk_live_...
   - Test API Key: pk_test_...
   - Live Signing Key: sk_live_...
   - Test Signing Key: sk_test_...
5. Copy both Live keys for production, Test keys for development
```

#### Step 2: Add to Backend Environment

**Backend `.env` file**:
```bash
# PayTrust - Live keys for production
PAYTRUST_API_KEY="pk_live_..."  # Or pk_test_... for development
PAYTRUST_SIGNING_KEY="sk_live_..."  # Used for webhook verification
```

#### Step 3: Configure Webhook

```
1. In PayTrust Dashboard → Webhooks
2. Click "Add Webhook"
3. Enter URL: https://your-backend-domain.com/paytrust-webhook
   (For development: use ngrok tunnel)
4. Select events:
   - payment.completed
   - payment.failed (optional)
   - refund.created (optional)
5. Save and copy the webhook signing key if provided
6. Test webhook with "Send Test Event" button
```

#### Step 4: Test Payment Flow

```bash
# Use test API keys to process test payment
# Card number: 4242 4242 4242 4242
# Expiry: 12/25
# CVC: 123
```

---

### 4️⃣ REPLICATE VIDEO GENERATION SETUP

**⏱️ Time needed**: 5 minutes

#### Step 1: Get API Token

```
1. Go to: https://replicate.com/account/api-tokens
2. Login or create account
3. Click "Create Token"
4. Copy the token (starts with r8_)
5. Save in secure location
```

#### Step 2: Add to Backend Environment

**Backend `.env` file**:
```bash
# Replicate API
REPLICATE_API_TOKEN="r8_..."
```

#### Step 3: Test Video Generation

```bash
# Backend should now be able to call Replicate API
# Test by generating a video with test prompt
```

---

### 5️⃣ SENDGRID EMAIL SETUP (Optional but Recommended)

**⏱️ Time needed**: 10 minutes

#### Step 1: Get API Key

```
1. Go to: https://sendgrid.com/
2. Create account or login
3. Go to: Settings → API Keys
4. Click "Create API Key"
5. Copy the key (starts with SG.)
```

#### Step 2: Add to Backend Environment

**Backend `.env` file**:
```bash
# SendGrid Email
SENDGRID_API_KEY="SG...."
SENDGRID_FROM_EMAIL="noreply@yourdomain.com"
```

#### Step 3: Verify Sender Email

```
1. In SendGrid → Settings → Sender Authentication
2. Add your sending email: noreply@yourdomain.com
3. Verify ownership of email address
4. Once verified, you can send from that email
```

---

### 6️⃣ BACKEND URL SETUP

**⏱️ Time needed**: 5 minutes (after deployment)

#### After Deploying Backend

```bash
# Backend .env
BACKEND_URL="https://your-backend-domain.com"  # For webhooks
ALLOWED_ORIGINS="https://app.yourdomain.com,https://admin.yourdomain.com"
ENV="production"
```

#### Frontend/Admin .env

```bash
# Frontend & Admin
NEXT_PUBLIC_BACKEND_URL="https://your-backend-domain.com"
```

---

## Complete Environment Variables Checklist

### ✅ Backend `.env` (KEEP SECRET)

```bash
# === CRITICAL - Firebase ===
FIREBASE_SERVICE_ACCOUNT_BASE64="<base64-encoded-json>"
FIREBASE_PROJECT_ID="your-project-id"

# === CRITICAL - Payments ===
PAYTRUST_API_KEY="pk_live_..."
PAYTRUST_SIGNING_KEY="sk_live_..."

# === CRITICAL - Video Generation ===
REPLICATE_API_TOKEN="r8_..."

# === Configuration ===
ENV="production"
BACKEND_URL="https://your-backend-domain.com"
ALLOWED_ORIGINS="https://app.yourdomain.com,https://admin.yourdomain.com"

# === Optional - Email ===
SENDGRID_API_KEY="SG...."
SENDGRID_FROM_EMAIL="noreply@yourdomain.com"

# === Logging ===
LOG_LEVEL="info"
```

### ✅ Frontend `.env.local` (CAN BE PUBLIC)

```bash
# === Firebase Web Config ===
NEXT_PUBLIC_FIREBASE_API_KEY="AIza..."
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
NEXT_PUBLIC_FIREBASE_PROJECT_ID="your-project-id"
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="your-project.appspot.com"
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="123456789"
NEXT_PUBLIC_FIREBASE_APP_ID="1:123456789:web:abc..."
NEXT_PUBLIC_FIREBASE_DATABASE_URL="https://your-project-id.firebaseio.com"

# === Backend Connection ===
NEXT_PUBLIC_BACKEND_URL="https://your-backend-domain.com"
```

### ✅ Admin Dashboard `.env.local` (CAN BE PUBLIC)

```bash
# Same Firebase config as main app
NEXT_PUBLIC_FIREBASE_API_KEY="AIza..."
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
NEXT_PUBLIC_FIREBASE_PROJECT_ID="your-project-id"
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="your-project.appspot.com"
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="123456789"
NEXT_PUBLIC_FIREBASE_APP_ID="1:123456789:web:abc..."
NEXT_PUBLIC_FIREBASE_DATABASE_URL="https://your-project-id.firebaseio.com"

# === Backend Connection ===
NEXT_PUBLIC_BACKEND_URL="https://your-backend-domain.com"
```

---

## Deployment Sequence

### Phase 1: Preparation (1 Week Before)

- [ ] **Firebase**: Set up project, create service account, get web config
- [ ] **PayTrust**: Create account, get API keys, test payment gateway
- [ ] **Replicate**: Create account, get API token, test video generation
- [ ] **SendGrid**: Create account (optional), verify sender email
- [ ] **GCP**: Set up Cloud Run, Cloud Storage, configure permissions

### Phase 2: Local Development

- [ ] Create `.env` file in backend directory with test keys
- [ ] Create `.env.local` in frontend directory with web config
- [ ] Test backend API endpoints locally
- [ ] Test frontend authentication flow
- [ ] Test payment processing with test keys

### Phase 3: Production Deployment

- [ ] Get production API keys from all services
- [ ] Set environment variables in deployment platform
- [ ] Deploy backend to Cloud Run
- [ ] Deploy frontend to hosting
- [ ] Test all flows in production
- [ ] Monitor logs for 24 hours

### Phase 4: Post-Deployment

- [ ] Verify all endpoints responding
- [ ] Test payment flow end-to-end
- [ ] Test video generation
- [ ] Confirm webhooks received
- [ ] Enable monitoring and alerts

---

## API Key Rotation Schedule

| Service | Frequency | Next Rotation | Notes |
|---------|-----------|---------------|-------|
| Firebase | Every 6 months | Jan 2025 | Service account key |
| PayTrust | Every 90 days | Feb 2025 | Both API and signing key |
| Replicate | Every 90 days | Feb 2025 | API token |
| SendGrid | Every 90 days | Feb 2025 | API key |

### Rotation Process

```bash
# 1. Generate new key in service dashboard
# 2. Update environment variables (don't deploy yet)
# 3. Test with new key
# 4. Deploy with new key
# 5. Wait 24 hours for stability
# 6. Revoke old key
# 7. Document rotation in change log
```

---

## Troubleshooting

### "Firebase authentication failed"
- Check `FIREBASE_SERVICE_ACCOUNT_BASE64` is valid base64
- Verify Firebase project ID matches
- Check service account has correct permissions

### "Payment failed"
- Verify `PAYTRUST_API_KEY` is correct (pk_live_ for production)
- Check webhook endpoint URL is accessible
- Verify `PAYTRUST_SIGNING_KEY` for signature verification

### "Video generation not working"
- Check `REPLICATE_API_TOKEN` is valid
- Verify account has API credits
- Check Replicate API status page

### "Webhook not received"
- Verify webhook URL is accessible from internet
- Check `ALLOWED_ORIGINS` includes webhook source
- Verify `PAYTRUST_SIGNING_KEY` is correct

---

## Security Reminders

🔐 **DO**:
- ✅ Store secret keys in environment variables
- ✅ Rotate keys every 90 days
- ✅ Use different keys for dev/test/prod
- ✅ Restrict API key permissions in dashboards
- ✅ Enable HTTPS for webhook endpoints
- ✅ Verify webhook signatures

⚠️ **DON'T**:
- ❌ Commit `.env` files to git
- ❌ Share API keys via email/chat
- ❌ Hardcode keys in source code
- ❌ Use same keys across environments
- ❌ Log API keys or sensitive data
- ❌ Commit `serviceAccountKey.json`

---

## Support Resources

### Firebase
- [Firebase Console](https://console.firebase.google.com/)
- [Firebase Docs](https://firebase.google.com/docs)
- [Firebase Community](https://stackoverflow.com/questions/tagged/firebase)

### PayTrust
- [PayTrust Dashboard](https://dashboard.paytrust.eu/)
- [PayTrust Documentation](https://docs.paytrust.eu/)
- Support Email: support@paytrust.eu

### Replicate
- [Replicate Dashboard](https://replicate.com/)
- [Replicate Documentation](https://replicate.com/docs)
- [Replicate Community](https://github.com/replicate/replicate-python)

### SendGrid
- [SendGrid Dashboard](https://sendgrid.com/)
- [SendGrid Documentation](https://docs.sendgrid.com/)
- [SendGrid Support](https://support.sendgrid.com/)

### GCP
- [Google Cloud Console](https://console.cloud.google.com/)
- [GCP Documentation](https://cloud.google.com/docs)
- [GCP Support](https://cloud.google.com/support)

---

## Final Checklist Before Production Launch

- [ ] All API keys obtained and validated
- [ ] Environment variables configured in deployment platform
- [ ] Backend deployed and tested
- [ ] Frontend deployed and tested
- [ ] Payment gateway tested with test cards
- [ ] Webhooks configured and tested
- [ ] Firestore security rules deployed
- [ ] HTTPS enabled on all endpoints
- [ ] CORS properly configured
- [ ] Rate limiting active
- [ ] Error tracking enabled
- [ ] Monitoring and alerts set up
- [ ] Backups configured
- [ ] Incident response plan documented
- [ ] Team trained on deployment process

✅ **Ready to launch!**
