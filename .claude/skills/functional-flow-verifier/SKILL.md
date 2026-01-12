# Functional Flow Verifier - Security-Functionality Balance Agent

## Description
Complements security audits by verifying that security implementations do not wrongly block legitimate user operations. Traces end-to-end user flows, detects functional gaps, and ensures the system works correctly for all user roles.

## When to Use
- After implementing security changes (Firestore rules, auth checks)
- Before deploying security-related updates
- When user reports "permission denied" errors
- To verify frontend-backend-database alignment
- To find missing pages, endpoints, or broken flows

## The 5 Verification Agents

Launch all agents in parallel using the Task tool with `subagent_type: "Explore"`.

---

### Agent 1: Frontend Flow Mapper

**Description:** Map frontend flows

**Prompt:**
Map all user flows in this frontend codebase. Find:
1. All page routes (app/*/page.tsx or pages/*.tsx)
2. All Firestore operations (getDoc, addDoc, setDoc, updateDoc, deleteDoc, onSnapshot)
3. All backend API calls (fetch, axios with BACKEND_URL)
4. All protected routes (auth checks, redirects)
5. All forms and their submission handlers

For each flow, document:
- Route/Component location
- Data source (Firestore collection or API endpoint)
- Required user state (guest, authenticated, admin, seller)
- Expected behavior

Report the complete flow map organized by feature area.

---

### Agent 2: Backend Endpoint Mapper

**Description:** Map backend endpoints

**Prompt:**
Map all API endpoints in this backend codebase. Find:
1. All route definitions (@app.get, @app.post, @app.put, @app.delete)
2. Authentication requirements (verify_id_token, admin checks)
3. Rate limiting applied
4. Firestore collections accessed
5. External service calls (payment gateways, email, etc.)

For each endpoint, document:
- Route path and method
- Required authentication
- Firestore operations performed
- Response format

Report complete endpoint map with authentication matrix.

---

### Agent 3: Firestore Rules Analyzer

**Description:** Analyze Firestore rules

**Prompt:**
Analyze all Firestore security rules in this codebase. For each collection:
1. List all rules (read, create, update, delete)
2. Identify blocking rules (allow: if false)
3. Identify conditional rules and their conditions
4. Check for over-blocking (legitimate operations blocked)
5. Check for under-blocking (sensitive operations allowed)

Create a matrix showing:
- Collection name
- Operation
- Rule condition
- Who can perform (guest/user/owner/admin/server-only)
- Potential issues

Report complete rules analysis with flagged concerns.

---

### Agent 4: Flow Integration Tester

**Description:** Test flow integration

**Prompt:**
Verify that frontend operations are properly supported by backend and Firestore rules. Check:
1. Every frontend Firestore query has matching rules that allow it
2. Every frontend API call has a matching backend endpoint
3. Success/error pages exist for all payment/purchase flows
4. All redirects point to existing routes
5. All collections used in frontend exist in rules

For each mismatch found:
- Frontend component/line
- Expected operation
- What is missing or blocking
- Impact on user

Report all integration gaps that would cause runtime errors.

---

### Agent 5: User Journey Validator

**Description:** Validate user journeys

**Prompt:**
Trace complete user journeys for these critical flows:
1. New user signup and onboarding
2. Credit purchase (pricing -> payment -> success)
3. Video generation (select model -> generate -> view history)
4. Marketplace listing (create -> publish -> manage)
5. Marketplace purchase (browse -> buy -> download)
6. Seller payout (request -> approval -> payment)

For each journey:
- List every step (frontend action, API call, DB operation)
- Verify each step is allowed by rules
- Check all success/error states handled
- Identify any broken links in the chain

Report journey validation results with any broken flows.

---

## Execution Steps

1. **Launch all 5 agents in parallel** using the Task tool
   - Use `subagent_type: "Explore"` for each agent
   - Each agent analyzes specific aspect of the system

2. **Wait for all agents to complete**
   - Each agent returns detailed findings
   - Findings include file locations and specific issues

3. **Compile findings into categories**
   - Blocking Issues (operations incorrectly blocked)
   - Missing Components (pages, endpoints, rules)
   - Integration Gaps (frontend-backend mismatches)
   - Incomplete Flows (broken user journeys)

4. **Generate Flow Verification Matrix**
   - Table showing all flows with status
   - Cross-reference frontend, backend, and rules
   - Highlight any mismatches

5. **Create action items**
   - Prioritize by user impact
   - Group by component (frontend/backend/rules)
   - Include fix suggestions

---

## Output Format

### Flow Verification Matrix

| Flow | Frontend | Backend | Firestore Rule | Status |
|------|----------|---------|----------------|--------|
| Browse marketplace | marketplace/page.tsx | N/A | marketplace_listings:read:true | OK |
| Purchase product | PurchaseModal.tsx | /marketplace/create-purchase-payment | marketplace_purchases:create:false (server) | OK |
| View purchases | marketplace/page.tsx | N/A | purchased_videos:read:uid | OK |

### Blocking Analysis

| Operation | Collection | Rule | Should Block? | Verdict |
|-----------|------------|------|---------------|---------|
| Client update credits | users | blocked | YES | CORRECT |
| Client update sellerBalance | users | blocked | YES | CORRECT |
| User read own data | users | uid match | NO | CORRECT |
| Server create purchase | marketplace_purchases | false (Admin SDK bypasses) | N/A | CORRECT |

### Functional Gaps Found

| Priority | Gap | Location | Impact | Fix |
|----------|-----|----------|--------|-----|
| HIGH | Missing success page | /marketplace/purchase/success | Users see 404 | Create page |
| HIGH | Missing purchased_videos | webhook handler | Purchases not shown | Add to webhook |
| MEDIUM | Missing cancel page | /marketplace/purchase/cancel | Poor UX on cancel | Create page |

### User Journey Status

| Journey | Steps | Status | Issues |
|---------|-------|--------|--------|
| Credit Purchase | 5 | OK | None |
| Marketplace Purchase | 7 | OK | Previously missing pages - fixed |
| Seller Payout | 4 | OK | None |

---

## Relationship to Security Audit Agent

| Aspect | Security Audit | Flow Verifier |
|--------|----------------|---------------|
| Focus | Vulnerabilities, attacks | Functionality, UX |
| Goal | Block malicious actions | Allow legitimate actions |
| Output | Security fixes | Integration fixes |
| Runs | Before security changes | After security changes |
| Finds | Under-blocking (attacks allowed) | Over-blocking (legit blocked) |

**Use Together:**
1. Run security audit to identify and implement protections
2. Run flow verifier to ensure protections do not break legitimate functionality
3. Iterate until both pass

---

## Example Usage

When user asks: "Verify nothing is blocked" or "Check flows work" or "Make sure security does not break anything"

1. Launch all 5 Task agents in parallel
2. Wait for all results
3. Cross-reference frontend operations with rules
4. Identify any gaps or blocking issues
5. Generate Flow Verification Matrix
6. Create prioritized fix list
7. Report findings to user

---

## Notes

- This agent complements, not replaces, security audits
- Focus is on false positives (legitimate actions wrongly blocked)
- Security agent focuses on false negatives (attacks wrongly allowed)
- Both should be run before production deployment
- Results should be cross-referenced for complete coverage
- All agents use `subagent_type: "Explore"` for thorough analysis
