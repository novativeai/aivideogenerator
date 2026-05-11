# AI Video Generator - Financial Model

## Executive Summary

This document outlines the credit-based pricing model for Reelzila's AI video and image generation platform. The model is designed to cover API costs while maintaining healthy profit margins (40-110%) across all models.

---

## Credit System

**Credit Value:** 1 credit = $0.05 USD
- **User Purchase Rate:** $1 = 20 credits (rounded for simplicity)
- **Examples:**
  - $5 → 100 credits
  - $10 → 200 credits
  - $25 → 500 credits
  - $50 → 1,000 credits
  - $100 → 2,000 credits

---

## Per-Model Pricing Breakdown

### 1. **WAN 2.2 14B** (Budget Video)
- **API Cost:** $0.10 per 5-second video (720p)
- **Selling Price:** $0.15 per generation
- **Credits Required:** 3 credits
- **Profit Margin:** 50%
- **Notes:** Most affordable option, 480p-720p resolution

### 2. **FLUX 1.1 Pro Ultra** (High-Res Image)
- **API Cost:** $0.06 per image (4MP)
- **Selling Price:** $0.10 per generation
- **Credits Required:** 2 credits
- **Profit Margin:** 67%
- **Notes:** Ultra high-resolution image generation

### 3. **Kling 2.5 Turbo Pro** (Professional Video)
- **API Cost:** $0.35 per 5-second video (1080p)
- **Selling Price:** $0.50 per generation
- **Credits Required:** 10 credits
- **Profit Margin:** 43%
- **Notes:** Excellent motion quality, cinematic output

### 4. **Seedance-1 Pro** (Premium Video)
- **API Cost:** $0.60 per 5-second video (1080p)
- **Selling Price:** $1.00 per generation
- **Credits Required:** 20 credits
- **Profit Margin:** 67%
- **Notes:** Multi-shot storytelling, subject consistency

### 5. **VEO 3.1** (Premium+ Video)
- **API Cost:** $3.20 per 8-second video (1080p)
- **Selling Price:** $5.00 per generation
- **Credits Required:** 100 credits
- **Profit Margin:** 56%
- **Notes:** Native audio synthesis, longest video duration

---

## Pricing Comparison Table

| Model | Duration | Credits | USD | Margin | Quality |
|-------|----------|---------|-----|--------|---------|
| WAN 2.2 | 5s | 3 | $0.15 | 50% | 720p |
| FLUX 1.1 | - | 2 | $0.10 | 67% | 4MP |
| Kling 2.5 | 5s | 10 | $0.50 | 43% | 1080p |
| Seedance | 5s | 20 | $1.00 | 67% | 1080p |
| VEO 3.1 | 8s | 100 | $5.00 | 56% | 1080p+Audio |

---

## Revenue Examples

### Scenario A: User Purchases $10 (200 Credits)

**Budget Strategy:**
- 67 WAN videos (3 credits each)
- **Cost to Reelzila:** 67 × $0.10 = $6.70
- **Revenue:** $10.00
- **Profit:** $3.30 (33%)

**Premium Strategy:**
- 2 VEO 3.1 videos (100 credits each)
- **Cost to Reelzila:** 2 × $3.20 = $6.40
- **Revenue:** $10.00
- **Profit:** $3.60 (36%)

**Mixed Strategy:**
- 1 VEO 3.1 (100 credits) + 10 Kling videos (10 credits each)
- **Cost to Reelzila:** $3.20 + (10 × $0.35) = $6.70
- **Revenue:** $10.00
- **Profit:** $3.30 (33%)

### Scenario B: User Purchases $50 (1,000 Credits)

**Premium Strategy:**
- 10 VEO 3.1 videos (100 credits each)
- **Cost to Reelzila:** 10 × $3.20 = $32.00
- **Revenue:** $50.00
- **Profit:** $18.00 (36%)

**Mixed Strategy:**
- 5 VEO 3.1 (500 credits) + 25 Kling (250 credits) + 167 WAN (501 credits)
- **Cost to Reelzila:** (5 × $3.20) + (25 × $0.35) + (167 × $0.10) = $33.70
- **Revenue:** $50.00
- **Profit:** $16.30 (33%)

---

## Key Financial Metrics

### Average Profit Margin
- **Conservative (WAN-heavy):** 33-40%
- **Standard (Mixed):** 35-45%
- **Premium (VEO-heavy):** 36-50%

### Break-Even Analysis
- Minimum operating cost per user session: $0 (no infrastructure costs in shared multi-tenant model)
- Revenue exceeds costs immediately on first credit purchase
- All revenue is profit after API costs

### Pricing Strategy Rationale

1. **Consistent 40-70% margins** ensure healthy profitability while remaining competitive with alternatives
2. **Round numbers** (2, 3, 10, 20, 100 credits) make pricing transparent and easy to understand
3. **Credit value of $0.05** aligns with common pricing tiers ($5, $10, $25, $50, $100)
4. **Dynamic per-model costs** incentivize users to choose models based on quality/price tradeoff

---

## Implementation

All credit costs are defined in `src/lib/modelConfigs.ts`:

```typescript
interface ModelConfig {
  // ... other properties
  creditCost: number; // Credits required per generation
}
```

Models configured:
- `kling-2.5`: 10 credits
- `veo-3.1`: 100 credits
- `seedance-1-pro`: 20 credits
- `wan-2.2`: 3 credits
- `flux-1.1-pro-ultra`: 2 credits

Generator dynamically displays cost: `Generate Media (10 Credits)` changes based on selected model.

---

## Adjustments Over Time

### When to Revise Pricing

1. **API Cost Changes:** ±$0.05 from Replicate
   - Adjust individual model pricing ±1 credit
   - Maintain 40-70% margin band

2. **Market Competition:** If competitors lower prices
   - Reduce pricing tier-by-tier
   - Prioritize volume over margin

3. **Infrastructure Costs:** If platform costs rise
   - Increase margins proportionally
   - Consider tiered pricing for bulk purchases

4. **Model Performance:** New models or improvements
   - New model pricing based on cost + 50% margin
   - Adjust older model costs downward if applicable

---

## Notes

- All prices in USD
- All margins calculated on variable costs only (no fixed overhead allocation)
- Credits do not expire (perpetual purchase)
- No subscription model (pure pay-as-you-go)
- Refunds: Full refund if generation fails (deduct credits immediately on success only)

---

*Last Updated: December 2025*
*Financial Model Version: 1.0*
