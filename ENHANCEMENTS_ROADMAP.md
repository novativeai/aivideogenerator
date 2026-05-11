# Seller Payout System - Enhancements Roadmap

## Overview

This document details all enhancements being implemented for the seller payout system to bring it to production-ready status.

---

## ✅ COMPLETED Enhancements

### 1. Email Notifications for Payout Status Changes ✅ COMPLETE

**What was implemented**:
- SendGrid integration in backend
- Automatic email notifications when payout status changes (pending → approved → completed/rejected)
- Seller receives personalized emails with:
  - Status change notification
  - Amount being withdrawn
  - Action required (if any)
- Admin receives notifications when payouts are approved

**Code changes**:
- Added to: `video-generator-backend/main.py`
  - `send_email()`: Core email sending utility
  - `send_payout_notification()`: Seller notification template
  - `send_admin_notification()`: Admin notification template
  - Updated `approve_payout()`, `reject_payout()`, `complete_payout()` endpoints

**Files modified**:
- ✅ `video-generator-backend/main.py`: +60 lines
- ✅ `requirements.txt`: Added `sendgrid>=6.10.0`

**Setup needed before production**:
```bash
# Add to backend .env:
SENDGRID_API_KEY="SG.xxx..."
SENDGRID_FROM_EMAIL="noreply@yourdomain.com"
ADMIN_EMAIL="admin@yourdomain.com"  # Optional
```

**Test**:
```python
# Test email sending in backend
python -c "
from video_generator_backend.main import send_email
send_email('test@example.com', 'Test Subject', '<p>Test content</p>')
"
```

---

## ⏳ PENDING Enhancements

### 2. Seller Profile Settings Page

**Purpose**: Allow sellers to view and update their PayPal email address

**What needs to be built**:

#### Frontend (Next.js)
- New component: `SellerSettingsCard.tsx`
- Display current PayPal email
- Edit form with validation
- Save button with loading state
- Success/error messages

#### Backend
- Already have `POST /seller/profile` endpoint
- Just need to use it from frontend

**Implementation Steps**:
1. Create `SellerSettingsCard.tsx` component
2. Add form to update PayPal email
3. Call `POST /seller/profile` endpoint
4. Show confirmation message
5. Add to Seller tab in account page

**Estimated time**: 1-2 hours

**Code location**:
- Frontend: `video-generator-frontend/src/components/SellerSettingsCard.tsx`
- Already integrated in Account page

---

### 3. Seller Verification/Suspension System

**Purpose**: Admins can verify sellers and suspend accounts if needed

**What needs to be built**:

#### Database Schema
```javascript
// Add to users/{userId}/seller_profile
{
  "paypalEmail": "...",
  "status": "unverified|verified|suspended|banned",  // NEW
  "verificationDate": "timestamp",  // NEW
  "suspensionReason": "string",  // NEW if suspended
  "suspendedBy": "admin_id",  // NEW if suspended
  "suspendedAt": "timestamp"  // NEW if suspended
}
```

#### Backend Endpoints
- `POST /admin/seller/{id}/verify` - Mark seller as verified
- `POST /admin/seller/{id}/suspend` - Suspend seller account
- `POST /admin/seller/{id}/unsuspend` - Reactivate seller
- `GET /admin/seller/{id}/status` - Check seller status

#### Admin Frontend
- Add section to seller management
- List all sellers with status
- Verify/suspend/unsuspend buttons

**Implementation Steps**:
1. Update Firestore schema
2. Add backend endpoints with admin auth
3. Add admin UI components
4. Test suspension prevents payouts

**Estimated time**: 3-4 hours

---

### 4. Payment History Export (CSV/PDF)

**Purpose**: Allow sellers to export their transaction and payout history

**What needs to be built**:

#### Frontend
- Add "Export" button in Seller tab
- Two options: CSV or PDF format
- Show loading state while generating

#### Backend
- `GET /seller/transactions/export?format=csv|pdf` endpoint
- Generate CSV with all transactions
- Generate PDF with formatted report

**Implementation Steps**:
1. Add Python libraries: `pandas` for CSV, `reportlab` for PDF
2. Create export functions in backend
3. Add endpoint with rate limiting
4. Add download button in frontend
5. Test file generation and download

**Estimated time**: 2-3 hours

---

### 5. Tax Form Collection

**Purpose**: Collect W-9 (US) or tax form equivalents for compliance

**What needs to be built**:

#### Database Schema
```javascript
{
  "taxFormType": "w9|1099|other",
  "taxFormUrl": "gcs-path-to-pdf",
  "uploadedAt": "timestamp",
  "verified": true/false
}
```

#### Frontend
- Tax form upload component
- Supported formats: PDF, image
- File size validation
- Upload progress

#### Backend
- `POST /seller/tax-form` endpoint
- Upload to Cloud Storage
- Scan for malicious files
- Store URL in Firestore

**Implementation Steps**:
1. Set up Cloud Storage bucket
2. Add file upload validation
3. Create backend endpoint
4. Add upload component to Seller Settings
5. Store in seller_profile

**Estimated time**: 4-5 hours

---

### 6. Real-Time Payout Status Updates

**Purpose**: Live updates of payout status without refreshing

**What needs to be built**:

#### Frontend Implementation
- Add Firestore listener in PayoutRequestsTable
- Real-time updates when status changes
- Toast notifications for status changes

**Code**:
```typescript
// In PayoutRequestsTable.tsx
useEffect(() => {
  if (!user) return;

  const q = query(
    collection(db, "users", user.uid, "payout_requests"),
    orderBy("createdAt", "desc")
  );

  const unsub = onSnapshot(q, (snapshot) => {
    const payouts = snapshot.docs.map(doc => ({
      id: doc.id,
      ...doc.data()
    }));
    setRequests(payouts);
  });

  return () => unsub();
}, [user]);
```

**Implementation Steps**:
1. Already have Firestore listener structure
2. Just add realtime listener to PayoutRequestsTable
3. Add toast notifications for changes
4. Test with real-time updates

**Estimated time**: 1-2 hours

---

### 7. Seller Account Suspension/Reactivation

**Purpose**: Admins can suspend or reactivate seller accounts

**What needs to be built**:

#### Features
- Suspend button in admin seller management
- Reason field for suspension
- Automatic email to seller
- Prevent payouts while suspended
- Reactivation process

#### Validation Logic
- Check `seller_profile.status` before allowing payouts
- Return 403 error if suspended

**Implementation Steps**:
1. Create suspension form in admin
2. Add backend suspension endpoint
3. Update payout endpoints to check status
4. Add email notification for suspension
5. Add reactivation button/process

**Estimated time**: 2-3 hours

---

### 8. Dispute Resolution System (Basic)

**Purpose**: Handle disputes between sellers and buyers

**What needs to be built**:

#### Database Schema
```javascript
// Collection: disputes
{
  "id": "dispute-123",
  "sellerId": "seller-id",
  "buyerId": "buyer-id",
  "transactionId": "transaction-id",
  "reason": "seller didn't deliver",
  "status": "open|investigating|resolved|refunded",
  "createdAt": "timestamp",
  "resolvedAt": "timestamp",
  "resolution": "full-refund|partial-refund|upheld"
}
```

#### Features
- User can file dispute
- Admin can review disputes
- Admin can approve/deny dispute
- Automatic refund if approved
- Email notifications

**Implementation Steps**:
1. Create disputes collection
2. Add file dispute endpoint
3. Add admin review endpoints
4. Create refund logic
5. Add admin UI for dispute management

**Estimated time**: 5-6 hours

---

## Implementation Priority

### Phase 1 (Critical - Do First)
1. ✅ Email Notifications - **DONE**
2. ⏳ Seller Verification System - **NEXT**
3. ⏳ Seller Profile Settings - **QUICK**

### Phase 2 (Important - Before Production)
4. ⏳ Account Suspension System
5. ⏳ Real-Time Status Updates - **EASY**
6. ⏳ Payment History Export

### Phase 3 (Nice to Have - Post-Launch)
7. ⏳ Tax Form Collection
8. ⏳ Dispute Resolution System

---

## Testing Checklist for Each Enhancement

### Email Notifications ✅
- [ ] Test payout approved email sends
- [ ] Test payout completed email sends
- [ ] Test payout rejected email sends
- [ ] Test admin notification email sends
- [ ] Verify email contains correct amounts
- [ ] Verify email contains correct seller name
- [ ] Test with SendGrid disabled (should not crash)

### Seller Verification (When Implemented)
- [ ] Unverified seller cannot request payouts
- [ ] Admin can verify seller
- [ ] Verified seller can request payouts
- [ ] Admin can suspend seller
- [ ] Suspended seller cannot request payouts
- [ ] Admin can unsuspend seller

### Real-Time Updates (When Implemented)
- [ ] Open seller dashboard on two devices
- [ ] Approve payout on one device
- [ ] Other device updates instantly (no refresh needed)
- [ ] Toast notification appears on other device

---

## API Keys Required for Enhancements

### SendGrid (Email) ✅ ADDED
```bash
SENDGRID_API_KEY="SG.xxx..."
SENDGRID_FROM_EMAIL="noreply@yourdomain.com"
ADMIN_EMAIL="admin@yourdomain.com"
```

### Cloud Storage (Tax Forms)
```bash
# GCP already set up, just ensure Cloud Storage API enabled
```

### Stripe or Refund System (Disputes)
```bash
# If using Stripe for refunds:
STRIPE_API_KEY="sk_live_..."
STRIPE_WEBHOOK_SECRET="whsec_..."
```

---

## Deployment Steps for Enhancements

### Before Each Enhancement Launch

1. **Code Review**
   - [ ] Review changes
   - [ ] Check for security issues
   - [ ] Verify error handling

2. **Testing**
   - [ ] Run all test cases
   - [ ] Manual testing in staging
   - [ ] Performance testing

3. **Deployment**
   - [ ] Set required environment variables
   - [ ] Deploy backend (if changes)
   - [ ] Deploy frontend (if changes)
   - [ ] Verify in production

4. **Monitoring**
   - [ ] Check logs for errors
   - [ ] Monitor API response times
   - [ ] Track user adoption

---

## Known Limitations & Future Work

### Current Limitations
- ⚠️ Email notifications require SendGrid (fallback: no email)
- ⚠️ Seller verification is manual (future: automated KYC)
- ⚠️ Payouts manual (future: PayPal API integration)
- ⚠️ Tax forms stored manually (future: automated 1099 generation)

### Future Enhancements
- PayPal API integration for automatic payouts
- Automated KYC/AML verification
- Real-time PayPal transfer status via webhook
- Multi-currency support
- International tax form handling
- Chargeback protection
- Fraud detection
- Performance-based seller ratings

---

## Implementation Progress

```
[████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 13% Complete

✅ 1/9 enhancements complete
⏳ 8/9 enhancements pending
```

### Timeline Estimate
- **Current**: Email notifications complete
- **Next 1-2 weeks**: Seller verification + Settings page
- **Next 2-4 weeks**: Account suspension + Export functionality
- **Next 4-6 weeks**: Tax forms + Dispute resolution

---

## Support & Troubleshooting

### SendGrid Email Issues
**Problem**: Emails not sending
**Solution**:
1. Check SENDGRID_API_KEY is set
2. Verify sender email is verified in SendGrid
3. Check SendGrid quota (daily limits)
4. Review SendGrid activity log
5. Enable in-code logging: `logger.debug(f"Sending email to {email}")`

### Firestore Listener Issues
**Problem**: Real-time updates not working
**Solution**:
1. Verify Firestore security rules allow read access
2. Check browser console for errors
3. Verify onSnapshot is properly subscribed
4. Check network tab for Firestore requests

### Tax Form Upload Issues
**Problem**: File upload fails
**Solution**:
1. Check file size (max usually 10MB)
2. Verify file type (PDF, images only)
3. Check Cloud Storage permissions
4. Review backend upload logs

---

## Questions or Issues?

Refer to:
- `SECURITY_AUDIT_REPORT.md` - Security considerations
- `PRODUCTION_DEPLOYMENT_GUIDE.md` - Deployment instructions
- `API_KEYS_SETUP_GUIDE.md` - API key configuration
- `SELLER_PAYOUT_TEST_PLAN.md` - Testing procedures

