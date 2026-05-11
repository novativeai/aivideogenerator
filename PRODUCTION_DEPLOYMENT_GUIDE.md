# Production Deployment Guide

## Required API Keys & Credentials

### 1. Firebase Configuration

**What it is**: Google's authentication and database service

**Where to get it**:
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to Project Settings (gear icon)
4. Download service account key as JSON

**Keys/Values needed**:
```
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com
FIREBASE_DATABASE_URL=https://your-project-id.firebaseio.com
```

**Security Notes**:
- ✅ NEVER commit the JSON file to git
- ✅ Store as base64 in environment: `FIREBASE_SERVICE_ACCOUNT_BASE64`
- ✅ Rotate credentials every 90 days
- ✅ Use separate service accounts for dev/staging/prod
- ✅ Backend only - never expose to frontend

**Setup Steps**:
```bash
# 1. Create service account key
# 2. Base64 encode it
cat serviceAccountKey.json | base64 > encoded_key.txt

# 3. Add to environment variables
export FIREBASE_SERVICE_ACCOUNT_BASE64="$(cat encoded_key.txt)"

# 4. Never commit serviceAccountKey.json
echo "serviceAccountKey.json" >> .gitignore
```

---

### 2. Firebase Frontend Configuration

**What it is**: Browser-side Firebase configuration for authentication and database access

**Where to get it**:
1. Firebase Console → Project Settings
2. Scroll to "Your apps" section
3. Click on web app
4. Copy config object

**Keys/Values needed**:
```javascript
NEXT_PUBLIC_FIREBASE_API_KEY=AIza...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project-id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=123456789
NEXT_PUBLIC_FIREBASE_APP_ID=1:123456789:web:abcdef...
NEXT_PUBLIC_FIREBASE_DATABASE_URL=https://your-project-id.firebaseio.com
```

**Security Notes**:
- ✅ SAFE to expose (already public in browser)
- ✅ Use Web API key with restrictions:
  - Restrict to "Cloud Firestore API" and "Cloud Storage API"
  - Don't use "Server" API key on frontend
- ✅ Can be in `.env.local` or environment variables

**Setup Steps**:
```bash
# Add to .env.local (frontend projects)
NEXT_PUBLIC_FIREBASE_API_KEY=AIza...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
# ... other keys
```

---

### 3. PayTrust (Payment Gateway) Configuration

**What it is**: Payment processor for handling marketplace transactions

**Where to get it**:
1. Go to [PayTrust Dashboard](https://dashboard.paytrust.eu/)
2. Login with your PayTrust account
3. Settings → API Keys

**Keys/Values needed**:
```
PAYTRUST_API_KEY=pk_live_...  (Live) or pk_test_... (Test)
PAYTRUST_SIGNING_KEY=sk_live_... (for webhook signature verification)
PAYTRUST_WEBHOOK_SECRET=whsk_... (alternative webhook secret)
```

**Security Notes**:
- ✅ KEEP SECRET - never expose in frontend or logs
- ✅ Use different keys for test/production
- ✅ Rotate keys regularly (every 90 days)
- ✅ Restrict API key permissions to minimum needed
- ✅ Store in backend environment only

**Setup Steps**:
```bash
# 1. Get keys from PayTrust dashboard
# 2. Add to backend .env file
export PAYTRUST_API_KEY="pk_live_..."
export PAYTRUST_SIGNING_KEY="sk_live_..."

# 3. Test webhook signature verification
# See SECURITY.md for webhook signature verification code
```

**Webhook Configuration**:
1. PayTrust Dashboard → Webhooks
2. Add endpoint: `https://your-backend-domain.com/paytrust-webhook`
3. Copy webhook signing key
4. Select events: `payment.completed`, `payment.failed`, `payment.refunded`

---

### 4. Replicate API (Video Generation)

**What it is**: API for AI video generation

**Where to get it**:
1. Go to [Replicate Dashboard](https://replicate.com/account/api-tokens)
2. Create API token
3. Copy token

**Keys/Values needed**:
```
REPLICATE_API_TOKEN=r8_...
```

**Security Notes**:
- ✅ KEEP SECRET - use in backend only
- ✅ Has rate limiting built-in
- ✅ Rotate token every 90 days
- ✅ Monitor API usage and costs
- ✅ Set spending limits in Replicate dashboard

**Setup Steps**:
```bash
# 1. Get token from Replicate dashboard
# 2. Add to backend .env file
export REPLICATE_API_TOKEN="r8_..."

# 3. Test that video generation works
```

---

### 5. SendGrid (Email Service) - OPTIONAL

**What it is**: Email service for notifications (not currently implemented but recommended)

**Where to get it**:
1. Go to [SendGrid](https://sendgrid.com/)
2. Sign up and create account
3. Settings → API Keys

**Keys/Values needed**:
```
SENDGRID_API_KEY=SG.xxx...
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
```

**Use Cases**:
- ✅ Payout status notifications
- ✅ Welcome emails
- ✅ Password reset emails
- ✅ Admin alerts

**Setup Steps** (when ready):
```bash
# 1. Get API key from SendGrid
# 2. Add to backend .env
export SENDGRID_API_KEY="SG.xxx..."
export SENDGRID_FROM_EMAIL="noreply@yourdomain.com"
```

---

### 6. Google Cloud Platform (GCP) - Firebase Hosting

**What it is**: Hosts your backend and frontend applications

**Where to get it**:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project
3. Enable required APIs
4. Create service account
5. Create credentials (JSON key)

**Services needed**:
```
- Cloud Run (backend hosting)
- Cloud Storage (video storage)
- Cloud Firestore (database)
- Cloud Logging (error tracking)
```

**Setup Steps**:
```bash
# 1. Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash

# 2. Initialize and authenticate
gcloud init
gcloud auth login

# 3. Set project
gcloud config set project PROJECT_ID

# 4. Deploy backend to Cloud Run
gcloud run deploy ai-video-backend --source .

# 5. Get backend URL for frontend
# Use this as NEXT_PUBLIC_BACKEND_URL
```

---

### 7. Environment Variables Setup

#### Backend (.env file) - KEEP SECRET

```bash
# === Firebase ===
FIREBASE_SERVICE_ACCOUNT_BASE64="base64-encoded-json-here"
FIREBASE_PROJECT_ID="your-project-id"

# === Payment Gateway ===
PAYTRUST_API_KEY="pk_live_..."
PAYTRUST_SIGNING_KEY="sk_live_..."

# === Video Generation ===
REPLICATE_API_TOKEN="r8_..."

# === Application ===
ENV="production"
BACKEND_URL="https://your-backend-domain.com"
ALLOWED_ORIGINS="https://app.yourdomain.com,https://admin.yourdomain.com"

# === Email (Optional) ===
SENDGRID_API_KEY="SG.xxx..."
SENDGRID_FROM_EMAIL="noreply@yourdomain.com"

# === Logging ===
LOG_LEVEL="info"  # 'debug' for development, 'info' for production
```

#### Frontend (.env.local) - CAN BE PUBLIC

```bash
# Firebase Frontend Config (can be public - restricted in console)
NEXT_PUBLIC_FIREBASE_API_KEY="AIza..."
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
NEXT_PUBLIC_FIREBASE_PROJECT_ID="your-project-id"
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="your-project.appspot.com"
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="123456789"
NEXT_PUBLIC_FIREBASE_APP_ID="1:123456789:web:abc..."
NEXT_PUBLIC_FIREBASE_DATABASE_URL="https://your-project-id.firebaseio.com"

# Backend URL
NEXT_PUBLIC_BACKEND_URL="https://your-backend-domain.com"

# Analytics (Optional)
NEXT_PUBLIC_GA_ID="G-XXXXXXXXXX"
```

#### Admin Dashboard (.env.local) - CAN BE PUBLIC

```bash
# Same Firebase config as main app
NEXT_PUBLIC_FIREBASE_API_KEY="AIza..."
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
NEXT_PUBLIC_FIREBASE_PROJECT_ID="your-project-id"
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="your-project.appspot.com"
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="123456789"
NEXT_PUBLIC_FIREBASE_APP_ID="1:123456789:web:abc..."
NEXT_PUBLIC_FIREBASE_DATABASE_URL="https://your-project-id.firebaseio.com"

# Backend URL
NEXT_PUBLIC_BACKEND_URL="https://your-backend-domain.com"

# Admin API endpoints
NEXT_PUBLIC_ADMIN_API_URL="https://your-backend-domain.com/admin"
```

---

## Firestore Security Rules Deployment

**What to do**:
```bash
# 1. Ensure firestore.rules is updated and committed
# 2. Deploy rules to production
firebase deploy --only firestore:rules

# 3. Verify in Firebase console
# Go to Firestore → Rules tab
```

**Current Rules Protection**:
- ✅ Users can only access their own data
- ✅ Admins can access admin resources
- ✅ Default deny-all policy
- ✅ Seller collections properly restricted

---

## Deployment Checklist

### Pre-Deployment (1 week before)

- [ ] **Credentials**
  - [ ] Request Firebase service account from GCP
  - [ ] Request PayTrust API keys
  - [ ] Request Replicate API token
  - [ ] Request SendGrid account (for emails)
  - [ ] Get Firebase web config

- [ ] **Code Review**
  - [ ] Security audit (see below)
  - [ ] Performance testing
  - [ ] Load testing
  - [ ] SQL injection testing
  - [ ] XSS testing
  - [ ] CORS testing

- [ ] **Database**
  - [ ] Deploy Firestore security rules
  - [ ] Create backup of current data
  - [ ] Test Firestore connection
  - [ ] Verify indexes exist

- [ ] **Documentation**
  - [ ] Document deployment steps
  - [ ] Document rollback procedure
  - [ ] Create runbooks for common issues
  - [ ] Document alert contacts

### Deployment Day

- [ ] **Backend Deployment**
  - [ ] Set production environment variables
  - [ ] Deploy to Cloud Run
  - [ ] Verify API endpoints respond
  - [ ] Test webhook signature verification
  - [ ] Monitor error logs for first hour

- [ ] **Frontend Deployment**
  - [ ] Build main app
  - [ ] Deploy to hosting provider
  - [ ] Test Firebase authentication
  - [ ] Test API connectivity
  - [ ] Smoke tests (login, generate, purchase)

- [ ] **Admin Dashboard Deployment**
  - [ ] Build admin dashboard
  - [ ] Deploy to hosting provider
  - [ ] Test admin authentication
  - [ ] Test payout management flows

- [ ] **Monitoring**
  - [ ] Enable error tracking
  - [ ] Set up uptime monitoring
  - [ ] Set up performance alerts
  - [ ] Configure log aggregation

### Post-Deployment (24 hours after)

- [ ] **Verification**
  - [ ] All API endpoints responding
  - [ ] No error spikes in logs
  - [ ] Database queries performing well
  - [ ] Payment processing working
  - [ ] Webhooks being received
  - [ ] Email notifications sending

- [ ] **Incident Response**
  - [ ] Team on-call for first 24 hours
  - [ ] Monitor error logs continuously
  - [ ] Have rollback plan ready
  - [ ] Document any issues encountered

---

## Security Hardening

### Environment Variables
```bash
# ✅ DO: Use environment-based secrets
export PAYTRUST_API_KEY="from-secure-vault"
export FIREBASE_SERVICE_ACCOUNT_BASE64="from-secure-vault"

# ❌ DON'T: Hardcode in code
const API_KEY = "sk_live_...";  // NEVER!
```

### API Key Rotation

**Schedule**:
- PayTrust keys: Every 90 days
- Firebase keys: Every 6 months
- Replicate token: Every 90 days
- SendGrid key: Every 90 days

**Process**:
1. Generate new key in service dashboard
2. Update environment variables (without deploying yet)
3. Deploy with new key
4. Wait 24 hours to ensure no issues
5. Revoke old key in service dashboard

### Rate Limiting

All endpoints have rate limiting:
```
- /seller/*: 5-30 requests/minute
- /admin/*: 10-30 requests/minute
- /generate-video: 30 requests/minute
- /paytrust-webhook: 100 requests/minute
```

### CORS Configuration

**Current Setup**:
```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
# Example: "https://app.yourdomain.com,https://admin.yourdomain.com"
```

**Security Features**:
- ✅ HTTP only allowed for localhost
- ✅ HTTPS enforced for production
- ✅ Only GET and POST allowed
- ✅ Only specific headers allowed
- ✅ Preflight cache 1 hour

### Webhook Security

**PayTrust Webhook Verification**:
```python
def verify_paytrust_signature(body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature"""
    signing_key = os.getenv("PAYTRUST_SIGNING_KEY")
    computed_signature = hmac.new(
        signing_key.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed_signature, signature)
```

---

## Monitoring & Logging

### What to Monitor

**Error Logs**:
```bash
# Check for errors every hour
gcloud logging read "resource.type=cloud_run_revision AND severity=ERROR" --limit 50

# Check for warnings
gcloud logging read "resource.type=cloud_run_revision AND severity=WARNING" --limit 50
```

**Performance**:
- Response times (should be <1s for most endpoints)
- Database query times (should be <100ms)
- API call success rates (should be >99%)

**Business Metrics**:
- Video generation success rate
- Payment completion rate
- Payout request volume
- Failed transactions

### Log Configuration

**Backend Logging** (Python):
```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # DEBUG for dev, INFO for prod

# Log format: timestamp | level | message
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO
)
```

**What to log**:
- ✅ API endpoint calls (without PII)
- ✅ Authentication attempts
- ✅ Payment events
- ✅ Payout approvals
- ✅ Errors (without stack traces to users)

**What NOT to log**:
- ❌ API keys
- ❌ Passwords
- ❌ Payment card info
- ❌ Personal email addresses
- ❌ Full request/response bodies
- ❌ Firebase credentials

---

## Disaster Recovery

### Backup Strategy

**Firestore Backups**:
```bash
# Automated daily backups
gcloud firestore backups create --instance=default

# Manual backup before major changes
gcloud firestore export gs://your-backup-bucket/backup-2024-01-15
```

**Recovery Process**:
1. If data corruption detected
2. Restore from backup via Firebase Console
3. Verify data integrity
4. Notify affected users

### Rollback Procedure

**If deployment goes wrong**:
1. Immediately disable new API endpoints
2. Revert environment variables to previous version
3. Redeploy previous version of code
4. Verify systems are working
5. Investigate root cause
6. Test fix
7. Deploy again

---

## Cost Optimization

### Firebase

**Pricing Model**:
- Firestore: $0.06 per 100K reads, $0.18 per 100K writes, $0.18 per 100K deletes
- Cloud Storage: $0.020 per GB stored
- Cloud Run: $0.40 per vCPU-hour, $0.00001667 per vCPU-second
- Cloud Functions: Free tier 2M invocations/month

**Cost Reduction**:
- Use Firestore indexes carefully
- Enable sharding for high-write collections
- Set data retention policies
- Use Cloud CDN for static assets

### PayTrust

**Pricing**: Per transaction + settlement fees
- Monitor transaction volume
- Negotiate volume discounts
- Track payment success rates

### Replicate

**Pricing**: Pay per API call
- Monitor video generation costs
- Implement rate limiting
- Consider caching results
- Set spending alerts

---

## Support & Escalation

**For Issues**:
1. Check application logs first
2. Check Firebase console (status, quotas)
3. Check service status pages:
   - [Firebase Status](https://status.firebase.google.com/)
   - [Google Cloud Status](https://status.cloud.google.com/)
   - [Replicate Status](https://status.replicate.com/)
4. Contact service provider support

**Critical Issues Contact**:
- Firebase: GCP support
- PayTrust: PayTrust support team
- Replicate: Replicate support
- Deployment: Your DevOps team

