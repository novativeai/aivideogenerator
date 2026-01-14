# Development Log

This is a living document that tracks project development progress. Claude should update this file after completing significant work.

---

## Current Sprint

**Focus**: Production stability and payment system

### Active Tasks
- [ ] Renew PayTrust API key (expired Jan 9, 2026)

### Completed This Sprint
- [x] Implement marketplace purchase payment endpoint
- [x] Fix security vulnerabilities (price manipulation, seller ID spoofing)
- [x] Add sellerBalance protection to Firestore rules
- [x] Create purchase success/cancel pages
- [x] Fix collection name mismatch (marketplace vs marketplace_listings)
- [x] Create functional-flow-verifier agent
- [x] Implement Claude memory system
- [x] Add YAML frontmatter to all skills for proper triggering
- [x] Create skill chain workflow (audit -> verify-flows -> dev)
- [x] Add auto-documentation rule (updates after ANY work, no trigger needed)

---

## Recent Changes

### 2026-01-14

#### Balance System Fixes and Admin Features (COMPLETED)
- Fixed critical balance calculation bugs in payout flow
- Updated frontend to use backend API for secure payout requests
- Added comprehensive admin marketplace management
- Added admin user deletion endpoint
- Added payment export functionality

##### Backend Balance Fixes:
- `main.py`: Fixed payout rejection to add funds back to `availableBalance` (not `pendingBalance`)
- `main.py`: Fixed payout completion to decrement `pendingBalance` when adding to `withdrawnBalance`
- `main.py`: Updated marketplace sale webhook to credit `availableBalance` instead of user-level `sellerBalance`
- `main.py`: Created `BankDetailsModel` for secure IBAN-based payout requests

##### Frontend Fixes:
- `WithdrawalRequestModal.tsx`: Now calls backend `/seller/payout-request` endpoint instead of direct Firestore write
- `SellerEarningsCard.tsx`: Updated to use `availableBalance` field, added `pendingBalance` display for in-progress payouts
- `account/page.tsx`: Updated to use `availableBalance` prop naming

##### Admin Endpoints Added:
- `GET /admin/marketplace/products` - List/filter all products
- `GET /admin/marketplace/products/{id}` - Get single product details
- `PUT /admin/marketplace/products/{id}` - Edit product (title, price, status, featured, notes)
- `DELETE /admin/marketplace/products/{id}` - Soft/permanent delete
- `POST /admin/marketplace/products/{id}/restore` - Restore soft-deleted products
- `DELETE /admin/users/{user_id}` - Soft/permanent user deletion
- `GET /admin/payments/export` - Export payments as JSON or CSV

##### Admin UI Updates:
- `marketplace/page.tsx`: Full rewrite with product list view, search, filtering, edit modal, delete/restore actions

##### Files Changed:
- `video-generator-backend/main.py` - Multiple endpoint additions and fixes
- `video-generator-frontend/src/lib/apiClient.ts` - Added payout request methods
- `video-generator-frontend/src/components/WithdrawalRequestModal.tsx` - API integration
- `video-generator-frontend/src/components/SellerEarningsCard.tsx` - Balance field updates
- `video-generator-frontend/src/app/account/page.tsx` - Prop updates
- `video-generator-admin/src/app/marketplace/page.tsx` - Full management UI

#### IBAN-Based Payout System (COMPLETED)
- Replaced PayPal payout system with IBAN bank transfer system
- Files changed:
  - `video-generator-frontend/src/components/SellerSettingsCard.tsx` - Full IBAN form with validation
  - `video-generator-frontend/src/components/WithdrawalRequestModal.tsx` - Bank details confirmation
  - `video-generator-frontend/src/components/PayoutRequestsTable.tsx` - Display IBAN details
  - `video-generator-admin/src/app/payouts/page.tsx` - Admin IBAN display with copy button
  - `video-generator-backend/main.py` - Updated payout endpoints for `payout_requests` collection
  - `video-generator-backend/email_templates.py` - Updated to bank account terminology

#### Features Added:
- IBAN validation (format, length, country code)
- IBAN formatting with spaces for readability
- IBAN masking for security (shows last 4 digits only)
- Bank details storage: IBAN, Account Holder, Bank Name, BIC/SWIFT
- Copy-to-clipboard for IBAN in admin dashboard
- Bank transfer workflow instructions for admin

#### Backend Changes:
- Changed collection from `withdrawalRequests` to `payout_requests`
- Updated balance tracking to use `seller_balance/current` subcollection
- Updated email notifications to reference bank transfers instead of PayPal

#### "Start Selling Videos" Link Fix (COMPLETED)
- Changed link from `/explore` to `/account?tab=seller`
- File: `video-generator-frontend/src/components/SellerEarningsCard.tsx`

### 2026-01-12

#### Marketplace Purchase Flow (COMPLETED)
- Added `/marketplace/create-purchase-payment` endpoint
- Created `MarketplacePurchaseRequest` Pydantic model
- Fixed security: Use verified DB values, not client-provided
- Added webhook amount verification
- Created `purchased_videos` records in webhook handler
- Fixed collection name: `marketplace` -> `marketplace_listings`

#### Frontend Pages (COMPLETED)
- Created `/marketplace/purchase/success/page.tsx`
- Created `/marketplace/purchase/cancel/page.tsx`
- Added retry logic for pending webhook processing

#### Security Fixes (COMPLETED)
- **Price Manipulation**: Now fetches price from database
- **Seller ID Spoofing**: Verifies sellerId from product document
- **Video URL Tampering**: Uses verified videoUrl from database
- **Firestore Rules**: Added sellerBalance to blocked fields

#### Claude Memory System (COMPLETED)
- Created `.claude/CLAUDE.md` (project overview)
- Created `.claude/docs/PROJECT_STRUCTURE.md` (detailed organigram)
- Created `.claude/docs/DEVELOPMENT_LOG.md` (this file)
- Created modular rules in `.claude/rules/`

#### Memory System Chain Fixes (COMPLETED)
- Added YAML frontmatter to all skill files (name, description, triggers)
- Added `related_skills` cross-references between agents
- Added "Next Steps" workflow guidance to each skill
- Created circular workflow: audit -> verify-flows -> dev -> verify-flows
- Fixed @file reference syntax in CLAUDE.md
- Added Skills section to CLAUDE.md with trigger documentation

#### Auto-Documentation Rule (COMPLETED)
- Added "Auto-Documentation (ALWAYS)" section to CLAUDE.md
- Documents progress after ANY work without specific trigger
- Includes format template for consistent logging
- Covers: bug fixes, features, security, config, issues

### 2026-01-11

#### Footer and UI Updates
- Updated footer layout
- Added company information
- Submodule updates for frontend

### 2026-12-17

#### Withdrawal Email Setup
- Configured withdrawal email notifications
- Added email templates for payout requests

### 2026-12-10

#### Production Audit
- Ran comprehensive 9-agent audit
- Generated PRODUCTION_AUDIT_REPORT.md
- Created financial model documentation

### 2026-12-06

#### Backend Security Overhaul
- Implemented comprehensive security fixes
- Created security documentation suite
- Added deployment checklist

---

## Feature Status

| Feature | Status | Last Updated | Notes |
|---------|--------|--------------|-------|
| User Authentication | COMPLETE | Nov 2025 | Firebase Auth |
| Video Generation | COMPLETE | Nov 2025 | Fal AI integration |
| Credit System | COMPLETE | Dec 2025 | Server-only |
| Credit Purchase | BLOCKED | Jan 2026 | PayTrust API expired |
| Marketplace Browse | COMPLETE | Jan 2026 | Public access |
| Marketplace Purchase | BLOCKED | Jan 2026 | PayTrust API expired |
| Seller Dashboard | COMPLETE | Jan 2026 | IBAN payouts, availableBalance |
| Payout System | COMPLETE | Jan 2026 | IBAN-based, backend API |
| Admin Dashboard | COMPLETE | Jan 2026 | Full marketplace mgmt |
| Admin Marketplace Mgmt | COMPLETE | Jan 2026 | List/edit/delete products |
| Admin User Deletion | COMPLETE | Jan 2026 | Soft/permanent delete |
| Admin Payment Export | COMPLETE | Jan 2026 | JSON/CSV export |
| Student Verification | COMPLETE | Nov 2025 | Discount eligibility |

---

## Known Issues

| ID | Severity | Component | Description | Status |
|----|----------|-----------|-------------|--------|
| ISS-001 | CRITICAL | Payments | PayTrust API key expired | OPEN |
| ISS-002 | LOW | Frontend | Some console warnings | OPEN |

---

## Technical Debt

| Item | Priority | Effort | Description |
|------|----------|--------|-------------|
| Test Coverage | MEDIUM | 2-3 days | Increase to 80%+ |
| Error Boundaries | LOW | 1 day | Add React error boundaries |
| Logging | LOW | 1 day | Standardize logging format |

---

## Deployment History

| Date | Component | Version | Notes |
|------|-----------|---------|-------|
| 2026-01-12 | Backend | - | Marketplace purchase fix |
| 2026-01-11 | Frontend | - | Footer updates |
| 2026-12-17 | Backend | - | Withdrawal emails |
| 2026-12-10 | All | - | Security audit fixes |

---

## Session Notes

### How to Update This Log

Claude should update this document after:
1. Completing a feature or bug fix
2. Discovering a new issue
3. Making significant code changes
4. Starting/ending a development session

Update format:
```markdown
### YYYY-MM-DD

#### [Feature/Fix Name] (STATUS)
- What was done
- Files changed
- Any follow-up needed
```

### Quick Commands

```bash
# Check current status
git status

# View recent commits
git log --oneline -10

# Run tests
cd video-generator-backend && pytest
cd video-generator-frontend && pnpm test
```
