# Backend Security Fixes - Test Plan

## Overview
This test plan validates the three critical backend security fixes:
1. Credit deduction race condition protection
2. Webhook idempotency
3. Credit refund safety with retry

---

## Prerequisites

### Test Environment Setup
```bash
# 1. Deploy to staging environment
git checkout main
git pull origin main

# 2. Verify dependencies installed
pip install -r requirements.txt

# 3. Verify Firestore collections exist
# - processed_webhooks
# - orphaned_payments
```

### Test Data
```javascript
// Create test user in Firestore
{
  "userId": "test-user-race-condition",
  "email": "test@example.com",
  "credits": 1,
  "createdAt": <timestamp>
}
```

---

## Test Suite 1: Credit Deduction Race Condition

### Test 1.1: Concurrent Credit Deduction - User with 1 Credit
**Objective**: Verify that only one request succeeds when user has 1 credit

**Setup**:
```javascript
// Set user credits to 1
db.collection('users').doc('test-user-race-condition').update({
  credits: 1
});
```

**Test Execution**:
```bash
# Terminal 1
curl -X POST https://your-api.com/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-race-condition",
    "model_id": "runway-gen3",
    "params": {"prompt": "test prompt 1"}
  }' &

# Terminal 2 (run immediately)
curl -X POST https://your-api.com/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-race-condition",
    "model_id": "runway-gen3",
    "params": {"prompt": "test prompt 2"}
  }' &

wait
```

**Expected Results**:
- ✅ One request returns HTTP 200 with video generation started
- ✅ One request returns HTTP 402 "Insufficient credits"
- ✅ User final credit balance = 0 (not negative)
- ✅ Logs show "Credit deducted for user test-user-race-condition, new balance: 0"

**Verification**:
```javascript
// Check final balance
db.collection('users').doc('test-user-race-condition').get()
  .then(doc => console.log('Credits:', doc.data().credits));
// Should be: 0
```

---

### Test 1.2: Concurrent Credit Deduction - User with 10 Credits
**Objective**: Verify transactions work correctly under load

**Setup**:
```javascript
db.collection('users').doc('test-user-race-condition').update({
  credits: 10
});
```

**Test Execution**:
```bash
# Run 20 concurrent requests (more than available credits)
for i in {1..20}; do
  curl -X POST https://your-api.com/generate-video \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": "test-user-race-condition",
      "model_id": "runway-gen3",
      "params": {"prompt": "test '$i'"}
    }' &
done

wait
```

**Expected Results**:
- ✅ Exactly 10 requests succeed (HTTP 200)
- ✅ Exactly 10 requests fail with HTTP 402 "Insufficient credits"
- ✅ User final credit balance = 0
- ✅ No negative balance at any point

---

### Test 1.3: Transaction Rollback on Firestore Error
**Objective**: Verify transaction rolls back if update fails

**Setup**:
```javascript
// Temporarily revoke write permissions (simulate error)
// Or use Firestore emulator to inject failures
```

**Test Execution**:
```bash
curl -X POST https://your-api.com/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-race-condition",
    "model_id": "runway-gen3",
    "params": {"prompt": "test"}
  }'
```

**Expected Results**:
- ✅ Request fails with HTTP 500 "Failed to process credit deduction"
- ✅ User credit balance unchanged (transaction rolled back)
- ✅ Log shows "Transaction failed"

---

## Test Suite 2: Webhook Idempotency

### Test 2.1: Duplicate Webhook - Same Transaction ID
**Objective**: Verify duplicate webhooks don't add credits twice

**Setup**:
```javascript
// Create payment record
db.collection('users').doc('test-user-webhook')
  .collection('payments').doc('payment-123').set({
    amount: 10.00,
    creditsPurchased: 100,
    status: 'pending',
    createdAt: admin.firestore.FieldValue.serverTimestamp()
  });

// Set initial credits
db.collection('users').doc('test-user-webhook').update({
  credits: 50
});
```

**Test Execution**:
```bash
# Send webhook 1st time
curl -X POST https://your-api.com/paytrust-webhook \
  -H "X-PayTrust-Signature: YOUR_VALID_SIGNATURE" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "transaction-456",
    "transactionId": "transaction-456",
    "state": "COMPLETED",
    "amount": 10.00,
    "referenceId": "user_id=test-user-webhook;payment_id=payment-123"
  }'

# Send webhook 2nd time (duplicate)
curl -X POST https://your-api.com/paytrust-webhook \
  -H "X-PayTrust-Signature: YOUR_VALID_SIGNATURE" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "transaction-456",
    "transactionId": "transaction-456",
    "state": "COMPLETED",
    "amount": 10.00,
    "referenceId": "user_id=test-user-webhook;payment_id=payment-123"
  }'
```

**Expected Results**:
- ✅ First webhook returns `{"status": "processed", "transactionId": "transaction-456"}`
- ✅ Second webhook returns `{"status": "already_processed", "transactionId": "transaction-456"}`
- ✅ User credits = 150 (50 + 100, NOT 50 + 100 + 100)
- ✅ Payment status = "paid" (updated once)

**Verification**:
```javascript
// Check user credits
db.collection('users').doc('test-user-webhook').get()
  .then(doc => console.log('Credits:', doc.data().credits));
// Should be: 150

// Check processed_webhooks collection
db.collection('processed_webhooks').doc('transaction-456').get()
  .then(doc => {
    console.log('Status:', doc.data().status);  // Should be: "success"
    console.log('Processed at:', doc.data().processedAt);
  });
```

---

### Test 2.2: Amount Validation - Tampered Webhook
**Objective**: Verify amount validation prevents credit manipulation

**Setup**:
```javascript
// Create payment record
db.collection('users').doc('test-user-webhook')
  .collection('payments').doc('payment-789').set({
    amount: 5.00,  // User paid €5
    creditsPurchased: 50,
    status: 'pending',
    createdAt: admin.firestore.FieldValue.serverTimestamp()
  });
```

**Test Execution**:
```bash
# Send webhook with TAMPERED amount
curl -X POST https://your-api.com/paytrust-webhook \
  -H "X-PayTrust-Signature: YOUR_VALID_SIGNATURE" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "transaction-789",
    "transactionId": "transaction-789",
    "state": "COMPLETED",
    "amount": 100.00,  # TAMPERED: claiming €100 instead of €5
    "referenceId": "user_id=test-user-webhook;payment_id=payment-789"
  }'
```

**Expected Results**:
- ✅ Request fails with HTTP 500 "Webhook processing failed"
- ✅ Log shows CRITICAL error: "Amount mismatch - stored: 5.0, webhook: 100.0"
- ✅ User credits NOT increased
- ✅ Webhook marked as failed in `processed_webhooks`

**Verification**:
```javascript
// Check webhook status
db.collection('processed_webhooks').doc('transaction-789').get()
  .then(doc => {
    console.log('Status:', doc.data().status);  // Should be: "failed"
    console.log('Error:', doc.data().error);    // Should contain: "Amount validation failed"
  });
```

---

### Test 2.3: Orphaned Payment - Non-Existent User
**Objective**: Verify orphaned payments are tracked

**Test Execution**:
```bash
curl -X POST https://your-api.com/paytrust-webhook \
  -H "X-PayTrust-Signature: YOUR_VALID_SIGNATURE" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "transaction-orphan",
    "transactionId": "transaction-orphan",
    "state": "COMPLETED",
    "amount": 10.00,
    "referenceId": "user_id=NON_EXISTENT_USER;payment_id=payment-999"
  }'
```

**Expected Results**:
- ✅ Request fails with HTTP 500
- ✅ Log shows: "Webhook for non-existent user: NON_EXISTENT_USER"
- ✅ Orphaned payment recorded in `orphaned_payments` collection
- ✅ Webhook marked as failed

**Verification**:
```javascript
// Check orphaned_payments collection
db.collection('orphaned_payments')
  .where('transactionId', '==', 'transaction-orphan')
  .get()
  .then(snapshot => {
    console.log('Orphaned payment found:', !snapshot.empty);  // Should be: true
  });
```

---

### Test 2.4: Concurrent Webhook Requests
**Objective**: Verify "processing" status prevents concurrent processing

**Test Execution**:
```bash
# Send same webhook from 2 terminals simultaneously
# Terminal 1
curl -X POST https://your-api.com/paytrust-webhook \
  -H "X-PayTrust-Signature: YOUR_VALID_SIGNATURE" \
  -d '{
    "transactionId": "concurrent-test",
    "state": "COMPLETED",
    "amount": 10.00,
    "referenceId": "user_id=test-user-webhook;payment_id=payment-concurrent"
  }' &

# Terminal 2 (run immediately)
curl -X POST https://your-api.com/paytrust-webhook \
  -H "X-PayTrust-Signature: YOUR_VALID_SIGNATURE" \
  -d '{
    "transactionId": "concurrent-test",
    "state": "COMPLETED",
    "amount": 10.00,
    "referenceId": "user_id=test-user-webhook;payment_id=payment-concurrent"
  }' &

wait
```

**Expected Results**:
- ✅ One webhook processes successfully
- ✅ Other webhook sees "processing" or "success" status and returns early
- ✅ Credits added only once

---

## Test Suite 3: Credit Refund Safety

### Test 3.1: Successful Refund After Generation Failure
**Objective**: Verify credit is refunded when generation fails

**Setup**:
```javascript
db.collection('users').doc('test-user-refund').update({
  credits: 5
});
```

**Test Execution**:
```bash
# Send request with invalid parameters to force failure
curl -X POST https://your-api.com/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-refund",
    "model_id": "runway-gen3",
    "params": {"invalid_param": "this will fail"}
  }'
```

**Expected Results**:
- ✅ Request fails with HTTP 500 "Video generation failed"
- ✅ Log shows: "Credit deducted for user test-user-refund, new balance: 4"
- ✅ Log shows: "Credit refunded for failed generation - user test-user-refund"
- ✅ Final user credits = 5 (refunded back)

**Verification**:
```javascript
db.collection('users').doc('test-user-refund').get()
  .then(doc => console.log('Credits:', doc.data().credits));
// Should be: 5 (back to original)
```

---

### Test 3.2: Refund Retry on Transient Error
**Objective**: Verify retry mechanism works on network errors

**Setup**:
```javascript
// Use Firestore emulator or mock to inject transient failures
// Simulate: First 2 attempts fail, 3rd succeeds
```

**Test Execution**:
```bash
# Trigger generation failure
curl -X POST https://your-api.com/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-refund",
    "model_id": "runway-gen3",
    "params": {"invalid_param": "fail"}
  }'
```

**Expected Results**:
- ✅ Refund retries up to 3 times
- ✅ Log shows retry attempts
- ✅ Eventually succeeds and refunds credit
- ✅ User credits restored

---

### Test 3.3: Critical Alert on Refund Failure
**Objective**: Verify CRITICAL log when all retries fail

**Setup**:
```javascript
// Revoke write permissions or kill Firestore connection
// Simulate: All 3 retry attempts fail
```

**Test Execution**:
```bash
curl -X POST https://your-api.com/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-refund",
    "model_id": "runway-gen3",
    "params": {"invalid_param": "fail"}
  }'
```

**Expected Results**:
- ✅ Log shows CRITICAL: "CRITICAL: Failed to refund credit for user test-user-refund - MANUAL INTERVENTION NEEDED"
- ✅ User credits NOT refunded (requires manual fix)
- ✅ Alert sent to admin (TODO: implement alerting)

**Manual Fix**:
```javascript
// Admin manually refunds credit
db.collection('users').doc('test-user-refund').update({
  credits: admin.firestore.FieldValue.increment(1)
});
```

---

## Test Suite 4: Integration Tests

### Test 4.1: End-to-End Payment Flow
**Objective**: Complete payment flow from webhook to credit addition

**Steps**:
1. User initiates payment (create payment record)
2. PayTrust processes payment
3. Webhook arrives
4. Credits added
5. User generates video
6. Credit deducted

**Expected**: Seamless flow with no duplicate credits or race conditions.

---

### Test 4.2: End-to-End Generation Flow
**Objective**: Complete generation flow from request to completion

**Steps**:
1. User has 1 credit
2. User submits generation request
3. Credit deducted (transactional)
4. Generation succeeds
5. Credit NOT refunded

**Expected**: User ends with 0 credits, video generated successfully.

---

### Test 4.3: End-to-End Failure Flow
**Objective**: Complete failure flow with refund

**Steps**:
1. User has 5 credits
2. User submits generation request
3. Credit deducted (transactional)
4. Generation fails (Replicate error)
5. Credit refunded (with retry)

**Expected**: User ends with 5 credits (refunded), no video generated.

---

## Performance Tests

### Test P1: High Concurrency - 100 Concurrent Requests
**Objective**: System handles high load without race conditions

```bash
# Use Apache Bench or similar
ab -n 100 -c 100 -p request.json -T application/json \
  https://your-api.com/generate-video
```

**Expected**:
- ✅ All transactions succeed or fail cleanly
- ✅ No negative credit balances
- ✅ Response time < 2 seconds per request

---

### Test P2: Webhook Burst - 50 Webhooks in 1 Second
**Objective**: Idempotency handles webhook storms

```bash
for i in {1..50}; do
  curl -X POST https://your-api.com/paytrust-webhook \
    -H "X-PayTrust-Signature: SIGNATURE" \
    -d '{"transactionId": "unique-'$i'", ...}' &
done
wait
```

**Expected**:
- ✅ All webhooks processed successfully
- ✅ No duplicate credit additions
- ✅ `processed_webhooks` collection has 50 entries

---

## Regression Tests

### Test R1: Existing Functionality Still Works
**Checklist**:
- [ ] User registration
- [ ] Credit purchase (one-time)
- [ ] Subscription creation
- [ ] Marketplace purchase
- [ ] Video generation (normal flow)
- [ ] Payout requests
- [ ] Admin endpoints

---

## Security Tests

### Test S1: Invalid Webhook Signature
```bash
curl -X POST https://your-api.com/paytrust-webhook \
  -H "X-PayTrust-Signature: INVALID_SIGNATURE" \
  -d '{"transactionId": "test", "state": "COMPLETED", ...}'
```

**Expected**: HTTP 401 "Invalid webhook signature"

---

### Test S2: Missing Transaction ID
```bash
curl -X POST https://your-api.com/paytrust-webhook \
  -H "X-PayTrust-Signature: VALID_SIGNATURE" \
  -d '{"state": "COMPLETED", "amount": 10.00}'  # No transactionId
```

**Expected**: HTTP 400 "Missing transaction ID"

---

## Sign-Off Criteria

All tests must pass with:
- ✅ 100% success rate for expected behavior
- ✅ No race conditions detected
- ✅ No duplicate credit additions
- ✅ All refunds successful or logged as CRITICAL
- ✅ Response times within acceptable limits
- ✅ No breaking changes to existing functionality

---

## Test Report Template

```markdown
# Test Execution Report

**Date**: YYYY-MM-DD
**Tester**: [Name]
**Environment**: [Staging/Production]

## Test Results

| Test Suite | Tests Run | Passed | Failed | Notes |
|------------|-----------|--------|--------|-------|
| Race Condition | 3 | 3 | 0 | ✅ |
| Webhook Idempotency | 4 | 4 | 0 | ✅ |
| Credit Refund | 3 | 3 | 0 | ✅ |
| Integration | 3 | 3 | 0 | ✅ |
| Performance | 2 | 2 | 0 | ✅ |
| Regression | 7 | 7 | 0 | ✅ |
| Security | 2 | 2 | 0 | ✅ |

**Overall**: ✅ PASS

## Issues Found
- None

## Recommendations
- Deploy to production
- Monitor logs for 24 hours
- Set up automated testing for future changes
```

---

## Automated Testing

### Setup CI/CD Pipeline
```yaml
# .github/workflows/test.yml
name: Backend Security Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run security tests
        run: |
          pytest tests/test_race_condition.py
          pytest tests/test_webhook_idempotency.py
          pytest tests/test_refund_safety.py
```

---

## Conclusion

This test plan ensures comprehensive validation of all backend security fixes. All tests should be executed before production deployment to guarantee system reliability and security.
