# Seller Payout System - End-to-End Test Plan

## Overview
This document outlines the complete testing flow for the seller payout system, covering earnings tracking, withdrawal requests, and admin management.

## System Architecture

### Data Flow
```
Marketplace Purchase → PayTrust Webhook → Seller Earnings Recorded
                                       ↓
                          Seller Dashboard Shows Earnings
                                       ↓
                          User Requests Withdrawal (PayPal Email)
                                       ↓
                          Admin Reviews Pending Payouts
                                       ↓
                          Admin Approves/Rejects
                                       ↓
                          Admin Manually Transfers via PayPal
                                       ↓
                          Admin Marks as Completed
                                       ↓
                          Seller Balance Updated
```

## Test Scenarios

### Phase 1: Earnings Tracking

#### Test 1.1: Record Marketplace Sale
**Objective**: Verify that marketplace purchases are properly recorded as seller earnings

**Steps**:
1. Create two test accounts: Seller (A) and Buyer (B)
2. Upload a video to marketplace as Seller A
3. Set a test price (e.g., €10.00)
4. Sign in as Buyer B
5. Purchase the video from Seller A
6. Complete PayTrust payment

**Expected Results**:
- ✅ Payment completes successfully
- ✅ Seller A's `seller_transactions` collection gets new transaction record:
  - `videoId`: matches uploaded video
  - `buyerId`: matches Buyer B's ID
  - `amount`: €10.00
  - `status`: "completed"
  - `timestamp`: current timestamp
- ✅ Seller A's `seller_balance` document updates:
  - `totalEarned`: increased by €10.00
  - `pendingBalance`: increased by €10.00
  - `lastTransactionDate`: updated

**How to Verify**:
```
Firebase Console → Firestore
Path: users/{sellerId}/seller_transactions/{transactionId}
Path: users/{sellerId}/seller_balance/current
```

---

#### Test 1.2: Multiple Sales Accumulation
**Objective**: Verify that multiple sales correctly accumulate in seller balance

**Steps**:
1. From Phase 1.1, Seller A has €10.00 pending
2. Repeat purchase process 2 more times (different buyers)
3. Each purchase is €10.00

**Expected Results**:
- ✅ After 2nd purchase: `pendingBalance` = €20.00, `totalEarned` = €20.00
- ✅ After 3rd purchase: `pendingBalance` = €30.00, `totalEarned` = €30.00
- ✅ All transactions appear in `seller_transactions` collection (3 total)

---

### Phase 2: Seller Dashboard

#### Test 2.1: View Earnings Card
**Objective**: Verify seller dashboard displays correct earnings information

**Steps**:
1. Sign in as Seller A (from Phase 1.2 with €30.00 pending)
2. Navigate to Account → Seller tab
3. Observe SellerEarningsCard component

**Expected Results**:
- ✅ Total Earned: €30.00
- ✅ Pending Withdrawal: €30.00
- ✅ Withdrawn: €0.00
- ✅ "Withdraw €30.00" button is visible and enabled

---

#### Test 2.2: View Sales History
**Objective**: Verify transaction history displays correctly

**Steps**:
1. Still on Seller A's dashboard
2. Scroll to "Sales History" section
3. Observe SellerTransactions component

**Expected Results**:
- ✅ 3 transactions listed (from Phase 1.2)
- ✅ Each shows:
  - Buyer ID (first 8 characters)
  - Amount (€10.00)
  - Status badge (green "completed")
  - Date of sale

---

#### Test 2.3: Empty State
**Objective**: Verify empty state message appears when no earnings exist

**Steps**:
1. Create new test account: Seller C
2. Sign in as Seller C
3. Navigate to Account → Seller tab

**Expected Results**:
- ✅ Shows empty state: "No earnings yet"
- ✅ Displays link to "selling videos" on marketplace
- ✅ No withdraw button visible

---

### Phase 3: Withdrawal Request Modal

#### Test 3.1: Open Modal
**Objective**: Verify withdrawal modal opens and displays correct balance

**Steps**:
1. Sign in as Seller A (with €30.00 pending)
2. Navigate to Seller tab
3. Click "Withdraw €30.00" button

**Expected Results**:
- ✅ Modal opens with overlay
- ✅ Available Balance shows: €30.00
- ✅ Amount field is pre-filled: 30.00
- ✅ PayPal Email field is empty (or filled if previously saved)

---

#### Test 3.2: Submit Withdrawal Request
**Objective**: Verify withdrawal request is created successfully

**Steps**:
1. In open modal from Test 3.1
2. Enter PayPal email: `test@paypal.com`
3. Click "Request €30.00"

**Expected Results**:
- ✅ Success message appears
- ✅ Modal closes after 2 seconds
- ✅ New payout request created in Firestore:
  - `status`: "pending"
  - `amount`: 30.00
  - `paypalEmail`: "test@paypal.com"
  - `createdAt`: current timestamp
- ✅ Seller dashboard still shows €30.00 pending (not deducted yet)

**How to Verify**:
```
Firebase Console → Firestore
Path: users/{sellerId}/payout_requests/{requestId}
```

---

#### Test 3.3: Partial Withdrawal
**Objective**: Verify partial withdrawal request is possible

**Steps**:
1. Sign in as Seller A (still €30.00 pending)
2. Click "Withdraw €30.00"
3. Change amount to: 15.00
4. Enter PayPal email: `partial@paypal.com`
5. Click "Request €15.00"

**Expected Results**:
- ✅ Request created with amount: €15.00
- ✅ Seller A still shows €30.00 pending (approval deducts it)
- ✅ New transaction record in `payout_requests` collection

---

#### Test 3.4: Validation Errors
**Objective**: Verify form validation works correctly

**Test Cases**:

**3.4a - Invalid Amount (too high)**:
- Try to withdraw €100.00 (balance is only €30.00)
- Expected: Error message "Amount exceeds your pending balance"

**3.4b - Invalid Amount (zero/negative)**:
- Try to withdraw €0.00 or €-5.00
- Expected: Error message "Please enter a valid amount"

**3.4c - Invalid Email**:
- Try to submit with email: "invalid-email"
- Expected: Error message "Please enter a valid email address"

**3.4d - Empty Email**:
- Try to submit without PayPal email
- Expected: Error message "Please enter your PayPal email"

---

### Phase 4: Admin Payout Management

#### Test 4.1: View Pending Payouts
**Objective**: Verify admin dashboard shows pending withdrawal requests

**Steps**:
1. Sign in as admin
2. Navigate to Dashboard → Seller Payouts
3. Observe "Pending Approval" section

**Expected Results**:
- ✅ Shows both payout requests from Phase 3 (€30.00 and €15.00)
- ✅ Each displays:
  - PayPal Email
  - Amount (€30.00, €15.00)
  - Pending status (yellow badge with clock icon)
  - Approve and Reject buttons
  - User ID (first 12 characters)

---

#### Test 4.2: Approve Payout
**Objective**: Verify payout approval updates statuses and balances

**Steps**:
1. In admin payout dashboard
2. Click "Approve" on the €30.00 payout
3. Confirm alert message

**Expected Results**:
- ✅ Loading spinner shows during request
- ✅ Success alert: "Payout approved! Processing PayPal transfer..."
- ✅ Payout moves from "Pending Approval" to "History" section
- ✅ Status badge changes to blue "Approved"
- ✅ "Mark Completed" button appears
- ✅ Seller A's balance in Firestore updated:
  - `pendingBalance`: 0.00 (was 30.00)
  - `totalEarned`: still 30.00

---

#### Test 4.3: Reject Payout
**Objective**: Verify payout rejection updates status correctly

**Steps**:
1. Approve the €15.00 payout first (from Test 3.3)
2. Click "Reject" on one of the pending payouts
3. Confirm alert

**Expected Results**:
- ✅ Payout moves to History with red "Rejected" status
- ✅ Seller A's `pendingBalance` restored:
  - If €15.00 was rejected: pendingBalance = 30.00 + 15.00 = 45.00

---

#### Test 4.4: Mark as Completed
**Objective**: Verify manual completion flow after PayPal transfer

**Steps**:
1. In History section, locate the approved payouts (blue "Approved" badge)
2. After manually transferring funds via PayPal, click "Mark Completed"
3. Confirm action

**Expected Results**:
- ✅ Status badge changes to green "Completed"
- ✅ "Mark Completed" button disappears
- ✅ Seller A's balance updated:
  - `withdrawnBalance`: incremented by payout amount
  - Example: If €30.00 approved and completed:
    - `totalEarned`: 30.00 (unchanged)
    - `withdrawnBalance`: 30.00 (was 0.00)
    - `pendingBalance`: 0.00

---

#### Test 4.5: View Payout History
**Objective**: Verify all historical payouts are displayed correctly

**Steps**:
1. On admin dashboard, scroll to "History" section
2. Verify all processed payouts appear

**Expected Results**:
- ✅ Shows all approved/completed/rejected payouts
- ✅ Each displays:
  - PayPal email
  - Amount
  - Appropriate status badge with icon
  - "Mark Completed" button only for "Approved" status

---

### Phase 5: Real-Time Updates

#### Test 5.1: Live Balance Updates
**Objective**: Verify real-time balance updates across devices

**Steps**:
1. Open Seller A dashboard on Device 1 (or Browser 1)
2. Open another browser window (Device 2) with same Seller A account
3. Make a new marketplace purchase from Device 1
4. Observe Device 2's dashboard

**Expected Results**:
- ✅ Device 2 dashboard updates in real-time
- ✅ Earnings card updates within 1-2 seconds
- ✅ New transaction appears in history immediately

---

#### Test 5.2: Status Updates Propagate
**Objective**: Verify seller sees payout status updates in real-time

**Steps**:
1. Seller A has a pending payout request
2. Open Seller A's dashboard with real-time listeners
3. In admin panel, approve the payout
4. Observe seller dashboard

**Expected Results**:
- ✅ Pending balance decreases in real-time
- ✅ Payout appears in "Withdrawal Requests" table with "Approved" status
- ✅ Changes appear within 1-2 seconds

---

### Phase 6: Edge Cases & Error Handling

#### Test 6.1: Request Without PayPal Email
**Objective**: Verify system handles missing seller PayPal email

**Steps**:
1. Create seller with earnings
2. Submit withdrawal request
3. Don't set email in seller_profile

**Expected Results**:
- ✅ Modal allows entering email during request
- ✅ Request created successfully with provided email
- ✅ No cascading errors

---

#### Test 6.2: Concurrent Requests
**Objective**: Verify system handles multiple simultaneous withdrawal requests

**Steps**:
1. Seller A submits 2 withdrawal requests quickly (€15 + €15)
2. Admin approves both simultaneously

**Expected Results**:
- ✅ Both process successfully
- ✅ Pending balance correctly deducted (€30)
- ✅ No race conditions or balance inconsistencies

---

#### Test 6.3: Zero Pending Balance
**Objective**: Verify behavior when pending balance is zero

**Steps**:
1. Seller has €30 pending
2. Request and approve withdrawal of €30
3. Try to request another withdrawal

**Expected Results**:
- ✅ "Withdraw €0.00" button is disabled
- ✅ Empty state message appears
- ✅ No errors in console

---

#### Test 6.4: Amount Precision
**Objective**: Verify decimal handling for currency amounts

**Steps**:
1. Make marketplace sales with amounts: €9.99, €0.01, €100.00
2. Request withdrawals with odd amounts: €50.25, €59.75
3. Verify totals and calculations

**Expected Results**:
- ✅ All amounts stored with correct decimal precision
- ✅ No rounding errors in calculations
- ✅ Display shows 2 decimal places (€X.XX)

---

## Testing Checklist

### Pre-Testing Setup
- [ ] Create 3+ test seller accounts
- [ ] Create 3+ test buyer accounts
- [ ] Have admin account ready
- [ ] Clear Firestore payout_requests collection (or use test data)
- [ ] Verify PayTrust webhook is active

### Execution
- [ ] Phase 1: Earnings Tracking (Tests 1.1-1.2)
- [ ] Phase 2: Seller Dashboard (Tests 2.1-2.3)
- [ ] Phase 3: Withdrawal Modal (Tests 3.1-3.4)
- [ ] Phase 4: Admin Management (Tests 4.1-4.5)
- [ ] Phase 5: Real-Time Updates (Tests 5.1-5.2)
- [ ] Phase 6: Edge Cases (Tests 6.1-6.4)

### Browser/Device Testing
- [ ] Chrome/Chromium
- [ ] Firefox
- [ ] Safari
- [ ] Mobile (iOS Safari, Chrome Mobile)
- [ ] Tablet

### Performance Testing
- [ ] Dashboard loads within 2 seconds
- [ ] Real-time updates propagate within 2 seconds
- [ ] Admin operations respond within 3 seconds

### Security Testing
- [ ] Users cannot access other users' earnings data
- [ ] Admin endpoints require authentication
- [ ] Firestore rules enforce access control
- [ ] No sensitive data in console logs

---

## Expected Error Scenarios

### What Should Never Happen
- ❌ Negative balances
- ❌ Double-spending of pending balance
- ❌ Loss of transaction history
- ❌ Unapproved payouts becoming "completed"
- ❌ Cross-user balance manipulation
- ❌ Admin operations without authentication

### Recovery Procedures
If any of the above occurs:
1. Check Firestore for data integrity
2. Review backend logs for errors
3. Check for race conditions in concurrent requests
4. Verify webhook signature validation
5. Inspect Firestore security rules

---

## Deployment Validation

Before deploying to production:
- [ ] All tests from this plan pass
- [ ] No console errors or warnings
- [ ] Firestore rules are deployed
- [ ] Backend endpoints are rate-limited
- [ ] Admin authentication is working
- [ ] PayPal email validation works correctly
- [ ] Real-time listeners are active
- [ ] No sensitive data logged

---

## Notes

### Manual vs Automated Payouts
Currently using **manual PayPal transfer** workflow:
- Admin approves withdrawal in dashboard
- Admin manually transfers funds via PayPal.com
- Admin clicks "Mark Completed" in dashboard

To integrate automated PayPal transfers in future:
- Add PayPal SDK to backend
- Call PayPal Transfer API in approve_payout endpoint
- Handle webhook from PayPal to auto-mark as "completed"
- Add PayPal account linking in seller settings

### Future Enhancements
- [ ] Email notifications for status changes
- [ ] PayPal API integration for automatic transfers
- [ ] Tax form collection (W-9, etc.)
- [ ] Payment history exports
- [ ] Bulk payout operations
- [ ] Failed payment retry logic
- [ ] Dispute resolution system
