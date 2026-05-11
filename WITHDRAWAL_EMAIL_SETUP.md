# Withdrawal Email Notification Setup Guide

This guide explains how to configure the automated email notification system for seller withdrawal requests.

## Overview

When a seller requests a withdrawal/payout, the system automatically:
1. Creates a withdrawal request in Firestore
2. Sends a detailed email notification to the admin with all necessary information
3. The admin can then manually process the PayPal transfer using the details provided in the email
4. When admin approves/rejects/completes a payout, the seller receives an email notification

## Requirements

- Resend account with API key (https://resend.com)
- Verified domain in Resend
- Admin email address configured
- Backend server running with environment variables set

## Environment Variables

### Backend (.env in video-generator-backend/)

Add these variables to your backend `.env` file:

```bash
# Resend Email Configuration
RESEND_API_KEY=re_your_resend_api_key_here
RESEND_FROM_EMAIL=notifications@reelzila.studio

# Admin Email (receives withdrawal notifications)
ADMIN_EMAIL=admin@reelzila.studio
```

### Frontend (.env.local in video-generator-frontend/)

Ensure this variable is set:

```bash
# Backend API URL
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
# For production:
# NEXT_PUBLIC_BACKEND_URL=https://your-backend-url.com
```

## Resend Setup

### 1. Create a Resend Account
1. Go to [Resend](https://resend.com/)
2. Sign up for a free account (100 emails/day free, 3,000/month)
3. Verify your email address

### 2. Create an API Key
1. Log in to Resend dashboard
2. Go to **API Keys** in the sidebar
3. Click **Create API Key**
4. Name it "reelzila-withdrawals"
5. Select permissions (Full access or Sending access)
6. Copy the API key (starts with `re_`)
7. Add it to your backend `.env` file as `RESEND_API_KEY`

### 3. Verify Your Domain (Recommended)
1. Go to **Domains** in the sidebar
2. Click **Add Domain**
3. Enter your domain (e.g., reelzila.studio)
4. Add the DNS records Resend provides (DKIM, SPF, DMARC)
5. Wait for verification (usually takes a few minutes)
6. Update `RESEND_FROM_EMAIL` to use your verified domain

## Email Template Features

The withdrawal notification email includes:

### Header Section
- Clear subject line: "💰 New Withdrawal Request - €X.XX from [Seller Name]"
- Eye-catching blue gradient header
- Alert badge for urgent action

### Withdrawal Details
- **Request ID**: Unique identifier for tracking
- **Seller Name**: Display name from user profile
- **Seller ID**: Firebase UID for reference
- **Seller Email**: User's email address
- **PayPal Email**: Where to send the payment
- **Amount**: €X.XX formatted
- **Status**: Pending
- **Timestamp**: When the request was received

### Processing Instructions
Step-by-step guide with copy-paste ready fields:
1. Log in to PayPal business account
2. Send payment to the PayPal email (pre-formatted)
3. Amount to send (pre-formatted)
4. Add note with request ID
5. Update admin dashboard after transfer

## How It Works

### User Flow
1. Seller navigates to their dashboard
2. Clicks "Request Withdrawal"
3. Enters amount and PayPal email
4. Submits withdrawal request

### System Flow
1. **Frontend** ([WithdrawalRequestModal.tsx:99-121](video-generator-frontend/src/components/WithdrawalRequestModal.tsx#L99-L121)):
   - Creates Firestore document in `users/{userId}/payout_requests`
   - Calls backend API endpoint `/seller/withdrawal-request-notification`
   - Passes: `requestId`, `amount`, `paypalEmail`

2. **Backend** ([main.py:1585-1656](video-generator-backend/main.py#L1585-L1656)):
   - Verifies user authentication
   - Fetches user details from Firestore
   - Generates HTML email from template
   - Sends email via SendGrid to `ADMIN_EMAIL`
   - Logs success/failure

3. **Email Delivered**:
   - Admin receives formatted email with all details
   - Can immediately process PayPal transfer
   - Updates admin dashboard after completion

## Testing the System

### 1. Backend Test (Recommended First)
```bash
cd video-generator-backend

# Make sure .env is configured with:
# SENDGRID_API_KEY=...
# SENDGRID_FROM_EMAIL=...
# ADMIN_EMAIL=...

# Start the backend
python main.py
```

### 2. Frontend Test
```bash
cd video-generator-frontend

# Make sure .env.local has:
# NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Start the frontend
npm run dev
```

### 3. End-to-End Test
1. Open browser to `http://localhost:3000`
2. Sign in as a seller account
3. Navigate to seller dashboard
4. Click "Request Withdrawal"
5. Enter test amount (e.g., €10.00)
6. Enter test PayPal email
7. Submit request
8. Check admin email inbox for notification

### Expected Result
You should receive an email at `ADMIN_EMAIL` with:
- Subject: "💰 New Withdrawal Request - €10.00 from [Your Name]"
- Fully formatted HTML email with all details
- Copy-paste ready PayPal email and amount

## Troubleshooting

### Email Not Received

**1. Check Resend API Key**
```bash
# In backend logs, look for:
"RESEND_API_KEY not configured - email notifications disabled"
```
→ Fix: Add `RESEND_API_KEY` to `.env`

**2. Check Admin Email**
```bash
# In backend logs, look for:
"ADMIN_EMAIL not configured - skipping withdrawal notification email"
```
→ Fix: Add `ADMIN_EMAIL` to `.env`

**3. Check Resend Domain Verification**
- Log in to Resend dashboard
- Go to Domains
- Ensure your domain is verified (green checkmark)
- Check Spam folder in admin email

**4. Check Backend Logs**
```bash
# Look for:
"Withdrawal notification email sent for request {id}"  # Success
"Failed to send withdrawal notification for request {id}"  # Failure
```

### Frontend Not Calling Backend

**1. Check Environment Variable**
```bash
# In browser console, check:
console.log(process.env.NEXT_PUBLIC_BACKEND_URL)
```
→ Should print: `http://localhost:8000` (or your backend URL)

**2. Check Backend is Running**
```bash
curl http://localhost:8000/health
```
→ Should return: `{"status":"healthy"}`

**3. Check CORS Configuration**
- Backend should allow requests from frontend origin
- Check backend logs for CORS errors

### Authentication Errors

**1. Invalid Token**
```bash
# In backend logs:
"Unauthorized" or "Invalid token"
```
→ User is not properly signed in, try signing out and back in

**2. Token Expired**
- Firebase tokens expire after 1 hour
- Sign out and sign in again to refresh

## Resend Email Limits

### Free Tier
- **100 emails/day** free
- **3,000 emails/month** free
- Perfect for testing and small volume

### Paid Tiers
If you need more:
- **Pro**: $20/month - 50,000 emails/month
- **Scale**: Custom pricing for higher volume

## Security Considerations

1. **Environment Variables**: Never commit `.env` files to git
2. **API Keys**: Rotate Resend API keys periodically
3. **Email Content**: Sensitive info is only sent to admin email
4. **HTTPS**: Use HTTPS in production for `NEXT_PUBLIC_BACKEND_URL`
5. **Rate Limiting**: Backend has rate limiting (10/minute for notification endpoint)

## Production Deployment

### 1. Update Environment Variables
```bash
# Backend production .env
RESEND_API_KEY=re_your_production_key
RESEND_FROM_EMAIL=notifications@yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com

# Frontend production .env.local
NEXT_PUBLIC_BACKEND_URL=https://api.yourdomain.com
```

### 2. Verify Domain (Highly Recommended)
For better deliverability:
1. Go to Resend Dashboard → Domains
2. Add your domain
3. Add DNS records (DKIM, SPF, DMARC)
4. Wait for verification

### 3. Monitor Email Delivery
- Resend Dashboard → Logs
- Track delivery rates and bounces
- Set up webhooks for delivery notifications

## Support

If you encounter issues:
1. Check backend logs for error messages
2. Verify all environment variables are set correctly
3. Test Resend API key in the Resend dashboard
4. Check Spam folder for test emails
5. Review this guide's troubleshooting section

## File References

- **Email Templates**: [email_templates.py](video-generator-backend/email_templates.py)
- **Backend Endpoint**: [main.py:1511-1632](video-generator-backend/main.py#L1511-L1632)
- **Frontend Integration**: [WithdrawalRequestModal.tsx:99-132](video-generator-frontend/src/components/WithdrawalRequestModal.tsx#L99-L132)

---

**Last Updated**: 2025-12-17
**Version**: 2.0 (Switched from SendGrid to Resend)
