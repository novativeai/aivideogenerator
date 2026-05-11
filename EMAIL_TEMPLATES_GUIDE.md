# Email Templates Guide

## Overview

The email notification system uses SendGrid to send professional, templated emails to sellers and admins about payout status changes.

---

## File Structure

```
video-generator-backend/
├── main.py                 # Main backend application
├── email_templates.py      # Email template definitions (NEW)
└── requirements.txt        # Dependencies (includes sendgrid)
```

---

## Email Templates

### 1. Payout Approved Template

**Function**: `get_payout_approved_email(seller_name, amount, paypal_email)`

**When sent**: When admin approves a payout request

**Recipient**: Seller

**Contents**:
- ✓ Header with "Payout Approved" message
- Personalized greeting
- Explanation that payout is being processed
- Box with payout details (amount, PayPal email, status)
- Timeline of what happens next (1-2 business days)
- Call-to-action button to view account
- Footer with links

**Email Subject**: `✓ Payout Approved: €{amount}`

**Example**:
```
✓ Payout Approved: €500.00

Hi John,

Great news! Your payout request has been approved and we're now
processing your PayPal transfer. You should receive the funds in
your PayPal account within 1-2 business days.

Payout Details
Amount: €500.00
PayPal Email: john@paypal.com
Status: Approved

What Happens Next?
1. We've approved your withdrawal request
2. We're processing your PayPal transfer
3. You'll receive the funds in your PayPal account within 1-2 business days
4. Check your PayPal account for the deposit

[View My Account Button]
```

---

### 2. Payout Completed Template

**Function**: `get_payout_completed_email(seller_name, amount)`

**When sent**: When admin marks payout as completed (after manual PayPal transfer)

**Recipient**: Seller

**Contents**:
- ✓ Green header with success message
- Celebration message
- Large amount display in green
- Success confirmation box
- Details of transaction
- Tip to keep earning/upload more videos
- Call-to-action button

**Email Subject**: `✓ Payout Completed: €{amount} Received!`

**Example**:
```
✓ Payout Completed!
Your funds have been transferred

Hi Sarah,

Excellent! Your payout has been completed and transferred to your
PayPal account. The funds should now be available in your PayPal wallet.

€500.00
✓ Successfully Completed

Status: Completed
Amount: €500.00
Check your PayPal: PayPal Account

💡 Pro Tip: Keep earning! The more you sell, the more you can withdraw.
Upload more videos to your marketplace to increase your earnings.

[View My Earnings Button]
```

---

### 3. Payout Rejected Template

**Function**: `get_payout_rejected_email(seller_name, amount)`

**When sent**: When admin rejects a payout request

**Recipient**: Seller

**Contents**:
- ✗ Red header with rejection message
- Empathetic explanation
- Alert box explaining funds return to balance
- Details of the rejected request
- Steps they can take to fix the issue
- Support contact button
- Professional footer

**Email Subject**: `Payout Rejected: €{amount}`

**Example**:
```
Payout Rejected
Your withdrawal request could not be processed

Hi Maria,

We've reviewed your payout request and unfortunately it was rejected.
This may be due to verification requirements or account issues.
Please contact our support team for more information.

Rejection Details
Your payout request for €200.00 has been rejected. Your balance
remains in your account and you can submit a new request after
addressing the issue.

Status: Rejected
Amount: €200.00
Refunded To: Your Account Balance

What Should You Do?
1. Check your PayPal email address is correct
2. Verify your account information
3. Ensure you meet our seller requirements
4. Contact support if you need assistance
5. Submit a new withdrawal request once issues are resolved

[Contact Support Button]
```

---

### 4. Admin Payout Ready Template

**Function**: `get_admin_payout_ready_email(seller_name, amount, paypal_email, seller_id)`

**When sent**: When admin approves payout (notification to admin only)

**Recipient**: Admin/Finance team

**Contents**:
- ✓ Orange header indicating action needed
- Clear call-to-action
- Large amount to transfer
- Seller details (name, PayPal email, ID)
- Step-by-step transfer instructions
- Direct link to admin dashboard

**Email Subject**: `[ACTION] Payout Approved: €{amount}`

**Example**:
```
✓ Payout Approved
Ready for PayPal transfer

A payout has been approved and is now ready for PayPal transfer.
Please process the transfer and mark as completed in the admin dashboard.

Action Required: Transfer to PayPal

€500.00

Send this amount to the PayPal email below, then mark as completed
in the admin dashboard.

Seller Name: John Smith
PayPal Email: john@paypal.com
Amount: €500.00
Seller ID: user_123456

Steps:
1. Log into PayPal business account
2. Send €500.00 to john@paypal.com
3. Return to admin dashboard
4. Click "Mark Completed" for this payout
5. Seller will receive completion email

[Go to Payouts Dashboard Button]
```

---

## Template Styling

### Design Features

All templates include:

**Header**:
- Gradient background (different color for each status)
- Clear, large heading
- Status indicator

**Body**:
- Professional sans-serif font
- Proper spacing and padding
- Color-coded elements (green for success, red for rejection, orange for action)
- Responsive design (works on mobile)

**Call-to-Action**:
- Prominent button
- Status-appropriate color
- Links to relevant page

**Footer**:
- Copyright info
- Privacy/Terms links
- Support contact info

### Color Scheme

- **Approved**: Purple/Blue gradient
- **Completed**: Green gradient
- **Rejected**: Red gradient
- **Admin Action**: Orange/Amber

---

## Usage in Code

### Basic Usage

```python
from email_templates import get_payout_email, get_admin_email

# Get HTML content for seller notification
html = get_payout_email(
    status="approved",
    seller_name="John Smith",
    amount=500.00,
    paypal_email="john@paypal.com"
)

# Get HTML content for admin notification
admin_html = get_admin_email(
    seller_name="John Smith",
    amount=500.00,
    paypal_email="john@paypal.com",
    seller_id="user_123"
)
```

### Integration in Backend

The email templates are automatically integrated in the payout approval/completion/rejection flows:

```python
# In approve_payout endpoint
seller_email = user_doc.get('email')
seller_name = user_doc.get('displayName', 'Seller')
send_payout_notification(seller_email, 'approved', amount, seller_name, paypal_email)

# Admin also gets notified
admin_html = get_admin_email(seller_name, amount, paypal_email, user_id)
send_admin_notification(subject, admin_html)
```

---

## Customization

### Changing Sender Email

Update in backend `.env`:
```bash
SENDGRID_FROM_EMAIL="noreply@yourdomain.com"
```

### Changing Admin Email

Update in backend `.env`:
```bash
ADMIN_EMAIL="finance@yourdomain.com"
```

### Changing Domain URLs

Edit `email_templates.py` and replace all instances of:
- `https://yourdomain.com` - Main app domain
- `https://youradmin.com` - Admin dashboard domain

---

## Template Customization

### Editing Templates

To customize email content, edit `email_templates.py`:

```python
def get_payout_approved_email(seller_name: str, amount: float, paypal_email: str) -> str:
    """Customize this function to change the approved payout email"""
    return f"""
    <!DOCTYPE html>
    <html>
    <!-- Edit the HTML here -->
    </html>
    """
```

### Adding Custom Branding

**Logo**: Add in header:
```html
<img src="https://yourdomain.com/logo.png" alt="Logo" style="max-width: 100px;">
```

**Custom Colors**: Update gradient colors in style section:
```css
.header {{
    background: linear-gradient(135deg, #yourcolor1 0%, #yourcolor2 100%);
}}
```

**Custom Links**: Update footer/CTA links:
```html
<a href="https://yourdomain.com/your-custom-path">Your Text</a>
```

---

## Testing Emails

### Test in Development

1. Set up SendGrid API key in `.env`:
```bash
SENDGRID_API_KEY="SG_test_key..."
```

2. Test sending email:
```python
from email_templates import get_payout_email
from main import send_email

html = get_payout_email("approved", "Test Seller", 100.0, "test@paypal.com")
send_email("your-email@test.com", "Test Subject", html)
```

3. Check your email inbox

### SendGrid Dashboard

1. Go to [SendGrid Dashboard](https://app.sendgrid.com/)
2. Navigate to: Mail → Activity Feed
3. View all sent emails and their delivery status
4. Check bounce rate and engagement metrics

### Testing Checklist

- [ ] Approved email receives correct seller name
- [ ] Completed email shows correct amount
- [ ] Rejected email has proper rejection message
- [ ] Admin email has clear action steps
- [ ] All links in emails work
- [ ] Emails render correctly on mobile
- [ ] Sender email displays correctly
- [ ] No HTML encoding errors
- [ ] Images/colors load properly
- [ ] Reply-to address is correct

---

## Troubleshooting

### Email Not Sending

**Issue**: Email not received

**Solutions**:
1. Check `SENDGRID_API_KEY` is set correctly
2. Verify sender email is verified in SendGrid
3. Check spam folder
4. Review SendGrid Activity Log for bounce reason
5. Check backend logs for SendGrid errors

**Code to debug**:
```python
# In email_templates.py send_email function
try:
    response = sg.send(message)
    logger.info(f"Email sent successfully. Response: {response.status_code}")
except Exception as e:
    logger.error(f"SendGrid error: {str(e)}")
```

### Email Formatting Issues

**Issue**: HTML not rendering, text looks broken

**Solutions**:
1. Check all `{{` and `}}` are properly escaped
2. Verify CSS has no syntax errors
3. Test in different email clients (Gmail, Outlook, Apple Mail)
4. Use inline CSS instead of style tags for better compatibility
5. Test images are accessible via HTTPS

### Seller Name Not Appearing

**Issue**: Email shows "Seller" instead of actual name

**Solutions**:
1. Ensure `displayName` is set in user document
2. Verify Firestore query is working
3. Add fallback value in template call
4. Check user document structure

---

## Email Template Variables

### Available Variables in Templates

```python
# Seller Notification
seller_name     # User's display name
amount          # Payout amount in EUR
paypal_email    # Seller's PayPal email
status          # "approved", "completed", "rejected"

# Admin Notification
seller_name     # Seller's display name
amount          # Payout amount in EUR
paypal_email    # Seller's PayPal email
seller_id       # Seller's Firestore user ID
```

---

## Best Practices

### ✅ DO

- Use professional, clear language
- Include all relevant transaction details
- Provide next steps/timeline
- Add support contact information
- Test emails before production
- Monitor delivery rates
- Personalize with seller name
- Include call-to-action buttons

### ❌ DON'T

- Use overly casual language
- Send from personal email
- Include technical jargon
- Use all caps for emphasis
- Send test emails to production addresses
- Change email style without testing
- Forget to update links for new domains
- Include sensitive data in subject line

---

## Future Enhancements

Potential improvements:

- [ ] Email templating engine (Handlebars, Jinja2)
- [ ] A/B testing different templates
- [ ] Unsubscribe management
- [ ] Email preference center
- [ ] Localization/multi-language support
- [ ] Dynamic template based on seller preferences
- [ ] Email scheduling for different time zones
- [ ] SMS notifications as fallback
- [ ] Webhook integration for email events
- [ ] Email analytics dashboard

---

## Support

For issues or questions:

1. Check `main.py` for email sending logic
2. Review SendGrid documentation: https://docs.sendgrid.com/
3. Test email rendering: https://www.litmus.com/
4. Check logs for errors: `logger.error()`

