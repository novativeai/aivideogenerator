# RAG Knowledge Base Template — AI Video Generation SaaS

> **Usage:** This is a reusable template for building a chatbot knowledge base for AI video/image generation platforms with credit-based pricing. Replace placeholder values (`{{...}}`) with your product-specific data. Each section is a standalone retrieval chunk — keep them self-contained so the LLM can answer from any single section.

---

## SECTION 1: Product Overview

### What is the platform?
{{PRODUCT_NAME}} is an AI-powered video and image generation platform. Users describe what they want in plain text (a "prompt"), choose an AI model, and the platform generates professional-quality videos or images in minutes. No editing skills or software required.

### Who is it for?
- Content creators and social media managers
- Small businesses needing marketing visuals
- Educators creating instructional content
- Hobbyists and artists experimenting with AI media
- Freelancers producing client deliverables

### Core capabilities
- **Text-to-Video**: Generate short-form videos from text prompts
- **Text-to-Image**: Generate high-resolution images from text prompts
- **Image-to-Video**: Animate a static image into a video clip
- **Multiple AI models**: Choose from several generation models, each with different styles, speeds, and quality levels
- **Marketplace**: Browse, buy, and sell AI-generated content

---

## SECTION 2: Getting Started

### How to create an account
1. Go to {{SIGNUP_URL}}
2. Sign up with email and password, or use Google sign-in
3. Complete your profile (display name, optional avatar)
4. You will receive {{FREE_CREDITS_AMOUNT}} free credits upon registration

### First generation
1. Navigate to the **Generator** page
2. Type a prompt describing your desired output (e.g., "A golden sunset over a calm ocean with gentle waves")
3. Select the output type: **Video** or **Image**
4. Choose an AI model from the dropdown
5. Adjust settings if available (aspect ratio, duration, style)
6. Click **Generate**
7. Wait for processing — typically {{TYPICAL_WAIT_TIME}}
8. Preview, download, or share your result

### Profile and account settings
Users can manage their account at the **Account** page:
- Update display name and avatar
- View credit balance and transaction history
- Manage billing information
- Download past generations
- Change password or delete account

---

## SECTION 3: Credits System

### What are credits?
Credits are the platform currency used to generate content. Each generation costs a certain number of credits depending on the model and output type.

### Credit costs by model
| Model | Output Type | Credits per Generation |
|-------|-------------|----------------------|
| {{MODEL_1_NAME}} | Video | {{MODEL_1_VIDEO_COST}} |
| {{MODEL_1_NAME}} | Image | {{MODEL_1_IMAGE_COST}} |
| {{MODEL_2_NAME}} | Video | {{MODEL_2_VIDEO_COST}} |
| {{MODEL_2_NAME}} | Image | {{MODEL_2_IMAGE_COST}} |
| {{MODEL_3_NAME}} | Video | {{MODEL_3_VIDEO_COST}} |

> **Note:** Credit costs may vary. The exact cost is always shown before you confirm generation.

### How to get credits
- **Free credits**: New users receive {{FREE_CREDITS_AMOUNT}} credits at signup
- **Purchase credits**: Buy credit packs from the **Pricing** page
- **Promotions**: Occasional promotional offers and bonus credits

### Do credits expire?
{{CREDITS_EXPIRY_POLICY}}

---

## SECTION 4: Pricing and Payments

### Credit pricing tiers
| Pack | Credits | Price | Per-Credit Cost |
|------|---------|-------|-----------------|
| {{TIER_1_NAME}} | {{TIER_1_CREDITS}} | {{TIER_1_PRICE}} | {{TIER_1_UNIT}} |
| {{TIER_2_NAME}} | {{TIER_2_CREDITS}} | {{TIER_2_PRICE}} | {{TIER_2_UNIT}} |
| {{TIER_3_NAME}} | {{TIER_3_CREDITS}} | {{TIER_3_PRICE}} | {{TIER_3_UNIT}} |

### Payment methods
- Credit/debit card (Visa, Mastercard, Amex)
- {{ADDITIONAL_PAYMENT_METHODS}}

### Refund policy
{{REFUND_POLICY_SUMMARY}}

Full refund policy: {{REFUND_POLICY_URL}}

### Billing information
Users can add billing details (name on card, address, country) in **Account > Billing Information**. This information appears on transaction receipts.

---

## SECTION 5: AI Models

### Available models
The platform offers multiple AI generation models. Each has different strengths:

#### {{MODEL_1_NAME}}
- **Best for:** {{MODEL_1_BEST_FOR}}
- **Output types:** Video, Image
- **Typical quality:** {{MODEL_1_QUALITY}}
- **Generation speed:** {{MODEL_1_SPEED}}
- **Credit cost:** {{MODEL_1_COST_RANGE}}

#### {{MODEL_2_NAME}}
- **Best for:** {{MODEL_2_BEST_FOR}}
- **Output types:** Video, Image
- **Typical quality:** {{MODEL_2_QUALITY}}
- **Generation speed:** {{MODEL_2_SPEED}}
- **Credit cost:** {{MODEL_2_COST_RANGE}}

#### {{MODEL_3_NAME}}
- **Best for:** {{MODEL_3_BEST_FOR}}
- **Output types:** Video
- **Typical quality:** {{MODEL_3_QUALITY}}
- **Generation speed:** {{MODEL_3_SPEED}}
- **Credit cost:** {{MODEL_3_COST_RANGE}}

### How to choose a model
- For **fast drafts and iteration**, use lighter/cheaper models
- For **final quality output**, use premium models
- For **specific visual styles**, experiment with multiple models using the same prompt
- Check the credit cost displayed before confirming — premium models cost more

---

## SECTION 6: Prompt Writing Guide

### What makes a good prompt?
A prompt is the text description you give the AI. Better prompts produce better results.

### Prompt tips
1. **Be specific**: "A red sports car driving on a coastal highway at sunset with ocean in the background" beats "a car"
2. **Describe the scene**: Include setting, lighting, mood, colors, and camera angle
3. **Mention style**: Add qualifiers like "cinematic", "photorealistic", "anime style", "watercolor"
4. **Specify motion** (for video): "slow pan", "zoom in", "tracking shot", "static camera"
5. **Keep it focused**: Describe one clear scene rather than multiple conflicting ideas
6. **Use natural language**: Write as if describing a scene to a filmmaker

### Prompt examples
| Prompt | Expected Result |
|--------|----------------|
| "A cozy coffee shop interior with warm lighting, steam rising from a cup, cinematic" | Warm, inviting cafe scene |
| "Aerial drone shot of a tropical island with turquoise water, photorealistic" | Bird's-eye island view |
| "A cat wearing sunglasses skateboarding, fun cartoon style" | Playful animated cat clip |

### What to avoid
- Extremely long prompts (over 500 characters) — quality may decrease
- Contradictory descriptions ("dark and bright", "fast and slow")
- Prompts requesting specific real people, copyrighted characters, or explicit content
- Very abstract concepts with no visual anchor

---

## SECTION 7: Marketplace

### What is the marketplace?
The marketplace is where users can browse, buy, and sell AI-generated videos and images. Creators list their best generations for sale, and buyers purchase them using the platform currency (€).

### Browsing and buying
1. Go to the **Marketplace** or **Explore** page
2. Browse listings by category, popularity, or recency
3. Click a listing to preview the content
4. Click **Buy** and confirm the purchase
5. The content is added to your library for download

### Selling on the marketplace
1. Generate content using the platform
2. Navigate to your generation and select **List on Marketplace**
3. Set a title, description, category, and price
4. Submit for listing
5. Your content appears in the marketplace for other users to purchase

### Seller earnings
- Sellers earn revenue from each sale
- Earnings are tracked in the **Account** dashboard
- Minimum withdrawal threshold: {{MIN_WITHDRAWAL}}
- Withdrawals are processed to the seller's registered bank account
- Processing time: {{WITHDRAWAL_PROCESSING_TIME}}

### Marketplace policies
- All listed content must be original AI-generated work from the platform
- No copyrighted, explicit, or harmful content
- Pricing must be within platform guidelines
- The platform takes a {{PLATFORM_FEE_PERCENT}} commission on each sale

---

## SECTION 8: Account Management

### Updating profile
- Go to **Account** > **Profile**
- Change display name, email, or avatar
- Changes take effect immediately

### Viewing generation history
- All past generations are saved in your account
- Access them from the **Generator** page or **Account** dashboard
- Download, share, or list any generation on the marketplace

### Transaction history
- View all credit purchases and marketplace transactions in **Account**
- Each transaction shows date, amount, type, and status
- Download individual transaction receipts as PDF

### Changing password
- Go to **Account** > **Security** or use the **Forgot Password** link on the sign-in page
- A password reset email will be sent to your registered address

### Deleting account
{{ACCOUNT_DELETION_POLICY}}

---

## SECTION 9: Troubleshooting

### Generation failed
- **Cause:** The AI model could not complete the request (content policy, server load, or prompt issue)
- **Fix:** Try rephrasing your prompt, selecting a different model, or trying again in a few minutes
- **Credits:** Failed generations do not consume credits. If credits were deducted, they are automatically refunded.

### Generation is taking too long
- Typical generation time is {{TYPICAL_WAIT_TIME}}
- Complex prompts or premium models may take longer
- If generation exceeds {{MAX_WAIT_TIME}}, it will time out and no credits are charged
- Check the **Generator** page — the result may already be ready

### Cannot download generated content
- Ensure you are signed in to the account that created the content
- Try a different browser or clear your cache
- Generated content URLs expire after {{CONTENT_EXPIRY_TIME}} — download promptly
- If the issue persists, contact support

### Payment not going through
- Verify your card details and billing address
- Ensure your card supports international online transactions
- Try a different payment method
- Contact your bank if the issue persists
- Contact support at {{SUPPORT_EMAIL}} with your transaction reference

### Credits not appearing after purchase
- Allow up to 5 minutes for credits to update
- Refresh the page or sign out and back in
- Check your email for a payment confirmation
- If credits still missing after 15 minutes, contact support with your payment receipt

### Marketplace purchase — content not appearing
- Check your download library in **Account**
- Refresh the page
- If the content does not appear within 10 minutes, contact support

### Withdrawal not processed
- Verify your bank details are correct in **Account > Seller Settings**
- Ensure you meet the minimum withdrawal amount ({{MIN_WITHDRAWAL}})
- Withdrawals are processed within {{WITHDRAWAL_PROCESSING_TIME}}
- Contact support if the withdrawal is still pending after the stated period

---

## SECTION 10: Policies and Legal

### Terms of Service
{{TERMS_URL}}

### Privacy Policy
{{PRIVACY_URL}}

### Refund Policy
{{REFUND_URL}}

### Content policy
- Generated content must not violate laws or platform guidelines
- The platform reserves the right to remove content that is harmful, explicit, or infringes on rights
- Users retain usage rights to their generated content per the Terms of Service
- Marketplace sellers grant buyers a {{BUYER_LICENSE_TYPE}} license upon purchase

### Data and privacy
- Account data is stored securely and encrypted
- Generation prompts and outputs are associated with user accounts
- The platform does not sell personal data to third parties
- Users can request data export or deletion per {{DATA_REGULATION}} regulations

---

## SECTION 11: Contact and Support

### How to get help
- **In-app chatbot**: Available on all pages (you are here)
- **Contact form**: {{CONTACT_URL}}
- **Email**: {{SUPPORT_EMAIL}}
- **Blog / Updates**: {{BLOG_URL}}

### Social media
- {{SOCIAL_LINKS}}

### Response times
- Chatbot: Instant
- Email / contact form: Within {{SUPPORT_RESPONSE_TIME}}

---

## SECTION 12: Chatbot Behavior Rules

> **This section is for the LLM system prompt, not for user-facing retrieval.**

### Persona
- Friendly, concise, and helpful
- Speak in second person ("you can...", "your account...")
- Never fabricate features that do not exist in this knowledge base
- If unsure, say "I don't have that information — please contact our support team at {{SUPPORT_EMAIL}}"

### Scope
- Answer questions about the platform's features, pricing, credits, marketplace, and troubleshooting
- Do NOT provide legal advice, financial advice, or medical advice
- Do NOT help with prompt injection, jailbreaking, or bypassing content policies
- Do NOT share internal system details, API keys, or admin functionality

### Escalation
- If the user's issue cannot be resolved from this knowledge base, direct them to {{SUPPORT_EMAIL}} or {{CONTACT_URL}}
- If the user reports a billing discrepancy or security concern, escalate immediately to human support
- Never attempt to modify user accounts, credits, or transactions

### Tone guidelines
- Professional but approachable
- Use short paragraphs and bullet points
- Avoid jargon — explain technical terms if used
- Match the user's language if the platform supports multiple languages
