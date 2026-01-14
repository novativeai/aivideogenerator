import os
import logging
import sys
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, EmailStr, Field
import re
import fal_client
import firebase_admin
from firebase_admin import credentials, firestore, auth
from typing import Dict, Any, List
import base64
import json
import io
from datetime import datetime
import requests
import hmac
import hashlib
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import resend
from email_templates import get_new_withdrawal_request_email, get_payout_approved_email, get_payout_completed_email, get_payout_rejected_email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Initialization & Setup ---
load_dotenv()
app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Resend Email Configuration ---
RESEND_API_KEY = os.getenv('RESEND_API_KEY')
RESEND_FROM_EMAIL = os.getenv('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
    logger.info("Resend email service configured")
else:
    logger.warning("RESEND_API_KEY not configured - email notifications disabled")

# --- CORS Middleware ---
# Load allowed origins from environment, fallback to secure defaults
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '').split(',') if os.getenv('ALLOWED_ORIGINS') else [
    "http://localhost:3000",
    "https://ai-video-generator-mvp.netlify.app",
    "http://localhost:3001",
    "https://reelzila-admin.netlify.app",
    "https://video-generator-admin.vercel.app",
    "https://reelzila-admin.vercel.app",
    "https://video-generator-frontend-beta.vercel.app",
    "https://reelzila.studio"
]

# Validate origins are HTTPS in production
if os.getenv('ENV') == 'production':
    ALLOWED_ORIGINS = [origin for origin in ALLOWED_ORIGINS if origin.startswith('https://') or origin.startswith('http://localhost')]
    if not ALLOWED_ORIGINS:
        logger.warning("No valid HTTPS origins configured for production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PayTrust Configuration ---
PAYTRUST_API_KEY = os.getenv("PAYTRUST_API_KEY")
PAYTRUST_PROJECT_ID = os.getenv("PAYTRUST_PROJECT_ID")  # Your PayTrust Project ID
PAYTRUST_API_URL = os.getenv("PAYTRUST_API_URL", "https://engine-sandbox.paytrust.io/api/v1")  # Use production URL when ready
PAYTRUST_SIGNING_KEY = os.getenv("PAYTRUST_SIGNING_KEY")  # For webhook signature verification

# Price ID to Credits Mapping (configure based on your pricing tiers)
PRICE_ID_TO_CREDITS = {
    "price_YOUR_PRO_PLAN_PRICE_ID": {"credits": 250, "planName": "Creator"},
    "price_YOUR_TEAM_PLAN_PRICE_ID": {"credits": 1000, "planName": "Pro"}
}

# --- Firebase Admin SDK Setup ---
db = None
firebase_init_error = None

try:
    logger.info("Starting Firebase Initialization")

    firebase_secret_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
    if not firebase_secret_base64:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 environment variable not found.")

    logger.debug(f"Environment variable found (length: {len(firebase_secret_base64)})")

    try:
        decoded_secret = base64.b64decode(firebase_secret_base64).decode('utf-8')
        logger.debug("Base64 decoding successful")
    except Exception as decode_error:
        raise ValueError(f"Failed to decode base64: {decode_error}")

    try:
        service_account_info = json.loads(decoded_secret)
        logger.info(f"Firebase project: {service_account_info.get('project_id', 'UNKNOWN')}")
    except Exception as json_error:
        raise ValueError(f"Failed to parse JSON: {json_error}")

    # Make storage bucket optional
    bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
    if bucket_name:
        logger.info(f"Storage bucket: {bucket_name}")
    else:
        logger.warning("Storage bucket not configured (optional)")

    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_info)
        # Initialize with or without storage bucket
        init_config = {'storageBucket': bucket_name} if bucket_name else {}
        firebase_admin.initialize_app(cred, init_config)
        logger.info("Firebase Admin SDK initialized")

    db = firestore.client()
    logger.info("Firebase initialization complete - Firestore client ready")

except Exception as e:
    firebase_init_error = str(e)
    logger.critical(f"Firebase initialization failed: {e}", exc_info=True)

# --- Pydantic Models with Validation ---
class VideoRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    model_id: str = Field(..., min_length=1, max_length=64)
    params: Dict[str, Any]

    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v.strip()

class PaymentRequest(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)
    customAmount: int = Field(..., ge=1, le=1000, description="Amount in EUR (1-1000)")

    @validator('customAmount')
    def validate_amount(cls, v):
        if v is None:
            raise ValueError('Payment amount is required')
        if v < 1:
            raise ValueError('Minimum payment is €1')
        if v > 1000:
            raise ValueError('Maximum payment is €1,000')
        return v

class SubscriptionRequest(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)
    priceId: str = Field(..., min_length=1, max_length=64)

class PortalRequest(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)

class MarketplacePurchaseRequest(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)
    productId: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=200)
    videoUrl: str = Field(..., min_length=1, max_length=2000)
    thumbnailUrl: str | None = Field(None, max_length=2000)
    price: float = Field(..., gt=0, le=10000, description="Price in EUR")
    sellerName: str = Field(..., min_length=1, max_length=100)
    sellerId: str = Field(..., min_length=1, max_length=128)

class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

class AdminUserUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None

class AdminCreditRequest(BaseModel):
    amount: int = Field(..., ge=1, le=10000, description="Credits to gift (1-10000)")

class AdminTransactionRequest(BaseModel):
    date: str = Field(..., pattern=r'^\d{2}/\d{2}/\d{4}$', description="Date in DD/MM/YYYY format")
    amount: int = Field(..., ge=0, le=100000)
    type: str = Field(..., min_length=1, max_length=50)
    status: str = Field(..., min_length=1, max_length=20)

class AdminBillingUpdateRequest(BaseModel):
    nameOnCard: str = Field(..., min_length=1, max_length=100)
    address: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    validTill: str = Field(..., pattern=r'^\d{2}/\d{2}$', description="Expiry in MM/YY format")

# --- fal.ai Model Mapping ---
# Each model has t2v (text-to-video), i2v (image-to-video), or t2i (text-to-image) endpoints
FAL_MODELS = {
    "veo-3.1": {
        "t2v": "fal-ai/veo3.1",
        "i2v": "fal-ai/veo3.1/reference-to-video",
        "image_param": "image_url"
    },
    "sora-2": {
        "t2v": "fal-ai/sora-2/text-to-video",
        "i2v": "fal-ai/sora-2/image-to-video/pro",
        "image_param": "image_url"
    },
    "kling-2.6": {
        "t2v": "fal-ai/kling-video/v2.6/pro/text-to-video",
        "i2v": "fal-ai/kling-video/v2.6/pro/image-to-video",
        "image_param": "image_url"
    },
    "ltx-2": {
        "t2v": "fal-ai/ltx-video",
        "i2v": "fal-ai/ltx-video/image-to-video",
        "image_param": "image_url"
    },
    "hailuo-2.3-pro": {
        "t2v": "fal-ai/minimax/hailuo-2.3/pro/text-to-video",
        "i2v": "fal-ai/minimax/hailuo-2.3/pro/image-to-video",
        "image_param": "image_url"
    },
    "nano-banana-pro": {
        "t2i": "fal-ai/nano-banana-pro",
        "image_param": None  # Text-to-image only, no image input
    }
}

# --- Dynamic Credit Pricing Configuration ---
# Based on fal.ai pricing: ~10 credits = $1.00
MODEL_CREDIT_PRICING = {
    # VEO 3.1: $0.40/sec with audio, $0.20/sec without
    "veo-3.1": {
        "base": 32,
        "modifiers": [
            {
                "param": "duration",
                "values": {"4": 16, "6": 24, "8": 32},
                "type": "set"
            },
            {
                "param": "generate_audio",
                "values": {"false": 0.5},
                "type": "multiply"
            }
        ]
    },
    # Sora 2: ~$0.10/sec
    "sora-2": {
        "base": 4,
        "modifiers": [
            {
                "param": "duration",
                "values": {"4": 4, "8": 8, "12": 12},
                "type": "set"
            }
        ]
    },
    # Kling 2.6 Pro: ~$0.10/sec
    "kling-2.6": {
        "base": 5,
        "modifiers": [
            {
                "param": "duration",
                "values": {"5": 5, "10": 10},
                "type": "set"
            }
        ]
    },
    # LTX 2: Very affordable ~$0.02/video
    "ltx-2": {
        "base": 1
    },
    # Hailuo 2.3 Pro: ~$0.08/sec
    "hailuo-2.3-pro": {
        "base": 4,
        "modifiers": [
            {
                "param": "duration",
                "values": {"5": 4, "10": 8},
                "type": "set"
            }
        ]
    },
    # Nano Banana Pro: $0.15/image (1K), $0.30 (4K)
    "nano-banana-pro": {
        "base": 2,
        "modifiers": [
            {
                "param": "resolution",
                "values": {"1K": 2, "2K": 3, "4K": 4},
                "type": "set"
            }
        ]
    }
}

def calculate_credits(model_id: str, params: Dict[str, Any]) -> int:
    """
    Calculate credits for a generation based on model and parameters.

    Raises:
        ValueError: If model_id is invalid or pricing configuration is malformed
    """
    # VALIDATION: Check if model exists
    if not model_id:
        logger.warning("calculate_credits called with empty model_id")
        raise ValueError("model_id cannot be empty")

    if model_id not in MODEL_CREDIT_PRICING:
        logger.warning(f"calculate_credits called with unknown model_id: {model_id}")
        raise ValueError(f"Unknown model: {model_id}. Valid models: {list(MODEL_CREDIT_PRICING.keys())}")

    pricing = MODEL_CREDIT_PRICING[model_id]

    # VALIDATION: Check base credits exist
    if "base" not in pricing:
        logger.error(f"Invalid pricing config for {model_id}: missing 'base' field")
        raise ValueError(f"Invalid pricing configuration for {model_id}: missing 'base' field")

    credits = pricing["base"]

    # VALIDATION: Ensure credits is a positive number
    if not isinstance(credits, (int, float)) or credits < 0:
        logger.error(f"Invalid base credits for {model_id}: {credits}")
        raise ValueError(f"Invalid base credits for {model_id}: must be non-negative number")

    # Apply modifiers
    modifiers = pricing.get("modifiers", [])
    for modifier in modifiers:
        param_name = modifier.get("param")
        param_value = params.get(param_name)

        if param_value is not None:
            param_value_str = str(param_value)
            modifier_values = modifier.get("values", {})
            modifier_value = modifier_values.get(param_value_str)

            if modifier_value is not None:
                # VALIDATION: Ensure modifier is numeric
                if not isinstance(modifier_value, (int, float)):
                    logger.error(f"Invalid modifier value for {model_id}.{param_name}={param_value_str}: {modifier_value}")
                    raise ValueError(f"Invalid modifier value type")

                modifier_type = modifier.get("type", "set")
                if modifier_type == "multiply":
                    credits *= modifier_value
                elif modifier_type == "add":
                    credits += modifier_value
                elif modifier_type == "set":
                    credits = modifier_value
                else:
                    logger.warning(f"Unknown modifier type: {modifier_type} for {model_id}")
            else:
                # Unknown parameter value - log warning but continue
                logger.warning(f"Unknown parameter value for {model_id}.{param_name}={param_value_str}. Using base credits.")
        else:
            # Parameter not provided - use base credits or next modifier
            logger.debug(f"Parameter {param_name} not provided for {model_id}")

    # Final validation: ensure result is valid
    final_credits = round(credits)
    if final_credits < 0:
        logger.error(f"calculate_credits returned negative value: {final_credits} for {model_id}")
        raise ValueError("Credit calculation resulted in negative credits")

    if final_credits == 0:
        logger.warning(f"calculate_credits returned 0 credits for {model_id} with params {params}")

    return final_credits

# --- Security Dependency for Admin Routes ---
async def check_is_admin(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    id_token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        user_doc = db.collection('users').document(uid).get()
        if user_doc.exists and user_doc.to_dict().get('isAdmin') is True:
            return uid
        else:
            raise HTTPException(status_code=403, detail="User is not an admin")
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Authentication check failed: {e}")

admin_dependency = Depends(check_is_admin)

# =========================
# === PUBLIC ENDPOINTS ===
# =========================

@app.get("/health")
async def health_check():
    """Public health check for load balancers and monitoring"""
    # Get Firebase project ID for debugging
    firebase_project = None
    try:
        firebase_secret = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
        if firebase_secret:
            decoded = base64.b64decode(firebase_secret).decode('utf-8')
            service_info = json.loads(decoded)
            firebase_project = service_info.get('project_id')
    except Exception:
        firebase_project = "error_reading"

    return {
        "status": "healthy" if db else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "firebase_project": firebase_project
    }

@app.get("/admin/health-detailed", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def health_check_detailed(request: Request):
    """Detailed health check for administrators only"""
    return {
        "status": "healthy" if db else "unhealthy",
        "database": "initialized" if db else "not initialized",
        "firebase_error": firebase_init_error,
        "environment": {
            "has_firebase_secret": bool(os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')),
            "has_storage_bucket": bool(os.getenv('FIREBASE_STORAGE_BUCKET')),
            "has_paytrust_key": bool(os.getenv('PAYTRUST_API_KEY')),
            "has_signing_key": bool(os.getenv('PAYTRUST_SIGNING_KEY')),
            "has_fal_key": bool(os.getenv('FAL_KEY')),
            "env_mode": os.getenv('ENV', 'development')
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/create-payment")
@limiter.limit("5/minute")
async def create_payment(request: Request, payment_request: PaymentRequest):
    """Create a one-time payment for credits using PayTrust"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    logger.info(f"Create Payment Request for user {payment_request.userId}")

    user_ref = db.collection('users').document(payment_request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")

    user_data = user_doc.to_dict()

    # Note: Amount validation handled by Pydantic (1-1000 EUR)
    amount = payment_request.customAmount
    credits_to_add = payment_request.customAmount * 10

    logger.info(f"Amount: €{amount}, Credits: {credits_to_add}")
    
    # Create pending payment record in Firestore
    payment_ref = user_ref.collection('payments').document()
    payment_id = payment_ref.id
    payment_ref.set({
        "amount": amount,
        "creditsPurchased": credits_to_add,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "status": "pending",
        "type": "Purchase"
    })
    
    logger.info(f"Payment record created: {payment_id}", extra={"user_id": payment_request.userId, "amount": amount})

    # Prepare PayTrust payment request - simplified for one-time purchase
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {PAYTRUST_API_KEY}"
    }
    
    backend_url = os.getenv('BACKEND_URL', 'https://aivideogenerator-production.up.railway.app')
    
    # Simplified payload matching your example
    payload = {
        "paymentType": "DEPOSIT",
        "amount": amount,
        "currency": "EUR",
        "returnUrl": f"https://ai-video-generator-mvp.netlify.app/payment/success?payment_id={payment_id}",
        "errorUrl": f"https://ai-video-generator-mvp.netlify.app/payment/cancel?payment_id={payment_id}",
        "webhookUrl": f"{backend_url}/paytrust-webhook",
        "referenceId": f"payment_id={payment_id};user_id={payment_request.userId}",
        "customer": {
            "referenceId": payment_request.userId,
            "firstName": user_data.get("name", "").split()[0] if user_data.get("name") else "User",
            "lastName": user_data.get("name", "").split()[-1] if user_data.get("name") and len(user_data.get("name", "").split()) > 1 else "Customer",
            "email": user_data.get("email", "customer@example.com")
        }
    }

    logger.debug(f"PayTrust API request for one-time payment {payment_id}")

    try:
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers)

        logger.debug(f"PayTrust response status: {response.status_code} for payment {payment_id}")

        response.raise_for_status()
        payment_data = response.json()

        logger.debug(f"PayTrust payment data received for payment {payment_id}")

        # PayTrust wraps response in a "result" object
        result = payment_data.get("result", payment_data)

        # Update payment record with PayTrust payment ID
        payment_ref.update({
            "paytrustPaymentId": result.get("id"),
            "paytrustTransactionId": result.get("transactionId")
        })

        # Get redirect URL from result object
        redirect_url = result.get("redirectUrl") or result.get("redirect_url") or result.get("paymentUrl")

        if not redirect_url:
            logger.error(f"No redirect URL in PayTrust response for payment {payment_id}")
            raise HTTPException(status_code=500, detail=f"PayTrust did not return a payment URL. Response: {payment_data}")

        logger.info(f"Payment URL obtained for payment {payment_id}")
        return {"paymentUrl": redirect_url}

    except requests.exceptions.HTTPError as e:
        error_detail = f"PayTrust API Error ({e.response.status_code}): {e.response.text}"
        logger.error(error_detail, extra={"payment_id": payment_id})
        raise HTTPException(status_code=500, detail=error_detail)
    except requests.exceptions.RequestException as e:
        error_detail = f"Request failed: {str(e)}"
        logger.error(error_detail, extra={"payment_id": payment_id})
        raise HTTPException(status_code=500, detail=error_detail)
    except Exception as e:
        error_detail = f"Unexpected error: {str(e)}"
        logger.error(error_detail, extra={"payment_id": payment_id})
        raise HTTPException(status_code=500, detail=error_detail)

@app.post("/create-subscription")
@limiter.limit("3/minute")
async def create_subscription(request: Request, sub_request: SubscriptionRequest):
    """Create a recurring subscription using PayTrust"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    logger.info(f"Create Subscription Request for user {sub_request.userId}")

    user_ref = db.collection('users').document(sub_request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")

    user_data = user_doc.to_dict()

    # Get subscription details from price ID
    subscription_info = PRICE_ID_TO_CREDITS.get(sub_request.priceId)
    if not subscription_info:
        raise HTTPException(status_code=400, detail="Invalid price ID.")

    amount = 22 if subscription_info["planName"] == "Creator" else 49
    credits_per_month = subscription_info["credits"]
    plan_name = subscription_info["planName"]

    logger.info(f"Plan: {plan_name}, Amount: ${amount}, Credits/month: {credits_per_month}")

    # Create subscription record in Firestore
    subscription_ref = user_ref.collection('subscriptions').document()
    subscription_id = subscription_ref.id
    subscription_ref.set({
        "priceId": sub_request.priceId,
        "planName": plan_name,
        "amount": amount,
        "creditsPerMonth": credits_per_month,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "status": "pending"
    })
    
    logger.info(f"Subscription record created: {subscription_id}", extra={"user_id": sub_request.userId, "plan": plan_name})

    # Prepare PayTrust recurring payment request
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {PAYTRUST_API_KEY}"
    }
    
    # Calculate next billing date (1 month from now)
    from datetime import timedelta
    next_billing = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    
    backend_url = os.getenv('BACKEND_URL', 'https://aivideogenerator-production.up.railway.app')
    
    payload = {
        "paymentType": "DEPOSIT",
        "amount": amount,
        "currency": "EUR",
        "returnUrl": f"https://ai-video-generator-mvp.netlify.app/payment/success?subscription_id={subscription_id}",
        "errorUrl": f"https://ai-video-generator-mvp.netlify.app/payment/cancel?subscription_id={subscription_id}",
        "webhookUrl": f"{backend_url}/paytrust-webhook",
        "startRecurring": True,
        "subscription": {
            "frequencyUnit": "MONTH",
            "frequency": 1,
            "amount": amount,
            "startTime": next_billing
        },
        "referenceId": f"subscription_id={subscription_id};user_id={sub_request.userId};price_id={sub_request.priceId}",
        "customer": {
            "referenceId": sub_request.userId,
            "firstName": user_data.get("name", "").split()[0] if user_data.get("name") else "User",
            "lastName": user_data.get("name", "").split()[-1] if user_data.get("name") and len(user_data.get("name", "").split()) > 1 else "Customer",
            "email": user_data.get("email", "customer@example.com")
        },
        "paymentMethod": "BASIC_CARD"
    }

    logger.debug(f"PayTrust API request for subscription {subscription_id}")

    try:
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers)

        logger.debug(f"PayTrust response status: {response.status_code} for subscription {subscription_id}")

        response.raise_for_status()
        payment_data = response.json()

        logger.debug(f"PayTrust payment data received for subscription {subscription_id}")

        # PayTrust wraps response in a "result" object
        result = payment_data.get("result", payment_data)

        # Update subscription record with PayTrust IDs
        subscription_ref.update({
            "paytrustPaymentId": result.get("id"),
            "paytrustTransactionId": result.get("transactionId")
        })

        # Get redirect URL from result object
        redirect_url = result.get("redirectUrl") or result.get("redirect_url") or result.get("paymentUrl")

        if not redirect_url:
            logger.error(f"No redirect URL in PayTrust response for subscription {subscription_id}")
            raise HTTPException(status_code=500, detail=f"PayTrust did not return a payment URL. Response: {payment_data}")

        logger.info(f"Subscription payment URL obtained for subscription {subscription_id}")
        return {"paymentUrl": redirect_url}

    except requests.exceptions.HTTPError as e:
        error_detail = f"PayTrust API Error ({e.response.status_code}): {e.response.text}"
        logger.error(error_detail, extra={"subscription_id": subscription_id})
        raise HTTPException(status_code=500, detail=error_detail)
    except requests.exceptions.RequestException as e:
        error_detail = f"Request failed: {str(e)}"
        logger.error(error_detail, extra={"subscription_id": subscription_id})
        raise HTTPException(status_code=500, detail=error_detail)
    except Exception as e:
        error_detail = f"Unexpected error: {str(e)}"
        logger.error(error_detail, extra={"subscription_id": subscription_id})
        raise HTTPException(status_code=500, detail=error_detail)

@app.post("/paytrust-webhook")
@limiter.limit("100/minute")
async def paytrust_webhook(request: Request):
    """
    Handle webhook notifications from PayTrust
    PayTrust sends notifications for payment events like:
    - Payment successful
    - Payment failed
    - Subscription payment (recurring)
    - Refunds

    Security: Verifies webhook signature using HMAC-SHA256
    """
    try:
        body = await request.body()

        # --- Webhook Signature Verification ---
        signature = request.headers.get("X-PayTrust-Signature") or request.headers.get("X-Signature")

        if PAYTRUST_SIGNING_KEY:
            if signature:
                expected_signature = hmac.new(
                    PAYTRUST_SIGNING_KEY.encode('utf-8'),
                    body,
                    hashlib.sha256
                ).hexdigest()

                if not hmac.compare_digest(signature, expected_signature):
                    logger.warning(f"Invalid webhook signature received from {request.client.host if request.client else 'unknown'}")
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")
            elif os.getenv('ENV') == 'production':
                logger.warning(f"Webhook received without signature in production from {request.client.host if request.client else 'unknown'}")
                raise HTTPException(status_code=401, detail="Missing webhook signature")

        payload = json.loads(body)

        # --- Idempotency Check ---
        webhook_id = payload.get("id") or payload.get("result", {}).get("id")
        if webhook_id and db:
            webhook_ref = db.collection('processed_webhooks').document(str(webhook_id))
            if webhook_ref.get().exists:
                logger.info(f"Webhook {webhook_id} already processed, skipping")
                return {"status": "already_processed", "webhook_id": webhook_id}

        logger.info(f"WEBHOOK RECEIVED: {datetime.now()}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

        # Extract event data from PayTrust response
        # PayTrust may send data in different structures, handle both
        if "result" in payload:
            event_data = payload.get("result", {})
        else:
            event_data = payload
        
        state = event_data.get("state") or payload.get("state")
        transaction_id = event_data.get("transactionId") or event_data.get("id")
        payment_id = event_data.get("id")
        reference_id = event_data.get("referenceId", "")
        amount = event_data.get("amount")
        payment_type = event_data.get("paymentType")
        
        logger.info(f"Webhook received - State: {state}", extra={
            "transaction_id": transaction_id,
            "reference_id": reference_id,
            "amount": amount
        })
        
        # Parse referenceId to extract metadata
        metadata = {}
        if reference_id:
            for pair in reference_id.split(";"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    metadata[key] = value
        
        user_id = metadata.get("user_id")
        payment_doc_id = metadata.get("payment_id")
        subscription_doc_id = metadata.get("subscription_id")
        price_id = metadata.get("price_id")
        marketplace_purchase_id = metadata.get("marketplace_purchase_id")
        seller_id = metadata.get("seller_id")
        product_id = metadata.get("product_id")

        logger.debug(f"Extracted webhook metadata", extra={"metadata": metadata})

        if not user_id:
            logger.warning("No user_id in webhook payload")
            return {"status": "received", "warning": "No user_id found"}
        
        user_ref = db.collection('users').document(user_id)
        
        # Handle different payment states
        # PayTrust uses: COMPLETED (success), FAILED, DECLINED, PENDING, CHECKOUT
        if state == "COMPLETED" or state == "SUCCESS":
            logger.info(f"Processing successful payment for user {user_id}")

            # Check if this is a subscription payment or one-time payment
            if subscription_doc_id or price_id:
                logger.info(f"Subscription payment detected for user {user_id}")

                # This is a subscription payment (initial or recurring)
                subscription_info = PRICE_ID_TO_CREDITS.get(price_id) if price_id else None
                credits_to_add = subscription_info["credits"] if subscription_info else 250  # Default to Creator plan
                plan_name = subscription_info["planName"] if subscription_info else "Creator"

                logger.info(f"Adding {credits_to_add} subscription credits for {plan_name} plan", extra={"user_id": user_id})
                
                # Update user credits and subscription status
                user_ref.update({
                    "credits": firestore.Increment(credits_to_add),
                    "activePlan": plan_name,
                    "subscriptionStatus": "active"
                })
                
                # Update subscription document if it exists
                if subscription_doc_id:
                    sub_ref = user_ref.collection('subscriptions').document(subscription_doc_id)
                    sub_doc = sub_ref.get()
                    if sub_doc.exists:
                        sub_ref.update({
                            "status": "active",
                            "lastPaymentDate": firestore.SERVER_TIMESTAMP,
                            "paytrustTransactionId": transaction_id
                        })
                        logger.info(f"Updated subscription document: {subscription_doc_id}")
                    else:
                        logger.warning(f"Subscription document not found: {subscription_doc_id}")
                
                # Create payment record for this subscription payment
                user_ref.collection('payments').add({
                    "amount": amount,
                    "creditsPurchased": credits_to_add,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "status": "paid",
                    "type": "Subscription",
                    "paytrustPaymentId": payment_id,
                    "paytrustTransactionId": transaction_id,
                    "paidAt": firestore.SERVER_TIMESTAMP
                })
                
                logger.info(f"Subscription payment successful for user {user_id}. Added {credits_to_add} credits.")

            elif payment_doc_id:
                logger.info(f"One-time payment detected: {payment_doc_id}")
                
                # This is a one-time payment
                payment_ref = user_ref.collection('payments').document(payment_doc_id)
                payment_doc = payment_ref.get()
                
                if payment_doc.exists:
                    payment_data = payment_doc.to_dict()
                    credits_to_add = payment_data.get("creditsPurchased", 0)

                    logger.debug(f"Payment status before update: {payment_data.get('status')}")
                    logger.info(f"Adding {credits_to_add} credits from one-time purchase", extra={"user_id": user_id, "payment_id": payment_doc_id})
                    
                    # ✅ CRITICAL: Update payment status from pending to paid
                    payment_ref.update({
                        "status": "paid",
                        "paidAt": firestore.SERVER_TIMESTAMP,
                        "paytrustTransactionId": transaction_id
                    })
                    
                    # Verify status was updated
                    updated_payment = payment_ref.get().to_dict()
                    logger.debug(f"Payment status after update: {updated_payment.get('status')}")
                    
                    # Add credits to user
                    user_ref.update({
                        "credits": firestore.Increment(credits_to_add)
                    })
                    
                    # Verify credits were added
                    updated_user = user_ref.get().to_dict()
                    new_credit_balance = updated_user.get("credits", 0)
                    
                    logger.info(f"One-time payment successful for user {user_id}", extra={
                        "credits_added": credits_to_add,
                        "new_balance": new_credit_balance,
                        "payment_id": payment_doc_id
                    })
                else:
                    logger.error(f"Payment document not found: {payment_doc_id}")

            elif marketplace_purchase_id:
                # This is a marketplace purchase
                logger.info(f"Marketplace purchase detected: {marketplace_purchase_id}")

                purchase_ref = db.collection('marketplace_purchases').document(marketplace_purchase_id)
                purchase_doc = purchase_ref.get()

                if purchase_doc.exists:
                    purchase_data = purchase_doc.to_dict()

                    # Prevent double-processing
                    if purchase_data.get('status') == 'completed':
                        logger.info(f"Marketplace purchase {marketplace_purchase_id} already completed, skipping")
                    elif purchase_data.get('status') == 'failed':
                        logger.warning(f"Marketplace purchase {marketplace_purchase_id} already failed, skipping")
                    else:
                        # SECURITY: Verify webhook amount matches expected purchase amount
                        expected_amount = purchase_data.get('price', 0)
                        webhook_amount = amount
                        if webhook_amount and expected_amount and abs(float(webhook_amount) - float(expected_amount)) > 0.01:
                            logger.error(f"Amount mismatch for purchase {marketplace_purchase_id}: expected {expected_amount}, got {webhook_amount}")
                            purchase_ref.update({
                                "status": "amount_mismatch",
                                "expectedAmount": expected_amount,
                                "receivedAmount": webhook_amount,
                                "failedAt": firestore.SERVER_TIMESTAMP
                            })
                            return {"status": "error", "message": "Amount mismatch"}

                        seller_id_from_purchase = purchase_data.get('sellerId')
                        seller_earnings = purchase_data.get('sellerEarnings', 0)
                        product_title = purchase_data.get('title', 'Unknown Product')
                        buyer_id = purchase_data.get('buyerId')

                        # 1. Update purchase status to completed
                        purchase_ref.update({
                            "status": "completed",
                            "completedAt": firestore.SERVER_TIMESTAMP,
                            "paytrustTransactionId": transaction_id
                        })

                        # 2. Credit seller's balance
                        seller_ref = db.collection('users').document(seller_id_from_purchase)
                        seller_doc = seller_ref.get()
                        if seller_doc.exists:
                            seller_ref.update({
                                "sellerBalance": firestore.Increment(seller_earnings)
                            })
                            logger.info(f"Credited seller {seller_id_from_purchase} with €{seller_earnings}")

                            # 3. Create transaction record for seller
                            seller_ref.collection('seller_transactions').add({
                                "type": "sale",
                                "amount": seller_earnings,
                                "productId": purchase_data.get('productId'),
                                "productTitle": product_title,
                                "buyerId": buyer_id,
                                "purchaseId": marketplace_purchase_id,
                                "createdAt": firestore.SERVER_TIMESTAMP
                            })

                        # 4. Update product sales count in marketplace_listings
                        product_ref = db.collection('marketplace_listings').document(purchase_data.get('productId'))
                        product_doc_check = product_ref.get()
                        if product_doc_check.exists:
                            product_ref.update({
                                "salesCount": firestore.Increment(1)
                            })

                        # 5. Create purchased_videos record for buyer (for frontend display)
                        buyer_ref = db.collection('users').document(buyer_id)
                        buyer_ref.collection('purchased_videos').add({
                            "productId": purchase_data.get('productId'),
                            "title": product_title,
                            "videoUrl": purchase_data.get('videoUrl'),
                            "thumbnailUrl": purchase_data.get('thumbnailUrl'),
                            "price": purchase_data.get('price'),
                            "sellerName": purchase_data.get('sellerName'),
                            "sellerId": seller_id_from_purchase,
                            "purchaseId": marketplace_purchase_id,
                            "purchasedAt": firestore.SERVER_TIMESTAMP
                        })
                        logger.info(f"Created purchased_videos record for buyer {buyer_id}")

                        logger.info(f"Marketplace purchase {marketplace_purchase_id} completed successfully", extra={
                            "buyer_id": buyer_id,
                            "seller_id": seller_id_from_purchase,
                            "seller_earnings": seller_earnings
                        })
                else:
                    logger.error(f"Marketplace purchase document not found: {marketplace_purchase_id}")

            else:
                logger.warning(f"No payment_id, subscription_id, or marketplace_purchase_id found in metadata for user {user_id}")
        
        elif state == "FAIL" or state == "FAILED" or state == "DECLINED":
            logger.warning(f"Payment FAILED or DECLINED for user {user_id}")
            
            # Handle failed payments
            if payment_doc_id:
                payment_ref = user_ref.collection('payments').document(payment_doc_id)
                payment_doc = payment_ref.get()
                if payment_doc.exists:
                    payment_ref.update({
                        "status": "failed",
                        "failedAt": firestore.SERVER_TIMESTAMP
                    })
                    logger.info(f"Updated payment status to failed: {payment_doc_id}")
            
            if subscription_doc_id:
                sub_ref = user_ref.collection('subscriptions').document(subscription_doc_id)
                sub_doc = sub_ref.get()
                if sub_doc.exists:
                    sub_ref.update({
                        "status": "failed",
                        "failedAt": firestore.SERVER_TIMESTAMP
                    })
                    logger.info(f"Updated subscription status to failed: {subscription_doc_id}")

            if marketplace_purchase_id:
                purchase_ref = db.collection('marketplace_purchases').document(marketplace_purchase_id)
                purchase_doc = purchase_ref.get()
                if purchase_doc.exists:
                    purchase_ref.update({
                        "status": "failed",
                        "failedAt": firestore.SERVER_TIMESTAMP
                    })
                    logger.info(f"Updated marketplace purchase status to failed: {marketplace_purchase_id}")

            logger.info(f"Payment failed for user {user_id}")

        elif state == "PENDING" or state == "CHECKOUT":
            # Payment is still processing
            logger.info(f"Payment pending/checkout for user {user_id}")
        
        else:
            logger.warning(f"Unknown payment state: {state}")

        # --- Mark webhook as processed for idempotency ---
        if webhook_id and db:
            db.collection('processed_webhooks').document(str(webhook_id)).set({
                "processedAt": firestore.SERVER_TIMESTAMP,
                "state": state,
                "userId": user_id
            })

        logger.info(f"Webhook processed successfully for user {user_id}")
        return {"status": "received"}

    except HTTPException:
        # Re-raise HTTP exceptions (signature validation failures)
        raise
    except Exception as e:
        logger.error(f"WEBHOOK ERROR: {e}", exc_info=True)
        # Return 200 even on errors to prevent PayTrust from retrying
        return {"status": "error", "message": str(e)}

@app.get("/payment-status/{payment_id}")
@limiter.limit("30/minute")
async def check_payment_status(request: Request, payment_id: str, user_id: str):
    """Allow frontend to check payment status"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")
    
    payment_ref = db.collection('users').document(user_id).collection('payments').document(payment_id)
    payment_doc = payment_ref.get()
    
    if not payment_doc.exists:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment_data = payment_doc.to_dict()
    return {
        "status": payment_data.get("status"),
        "amount": payment_data.get("amount"),
        "creditsPurchased": payment_data.get("creditsPurchased")
    }

@app.post("/create-customer-portal-session")
@limiter.limit("5/minute")
async def create_customer_portal(request: Request, portal_request: PortalRequest):
    """
    Note: PayTrust may not have a built-in customer portal like Stripe.
    You may need to build your own subscription management UI.
    This endpoint is kept for compatibility but may need custom implementation.
    """
    user_ref = db.collection('users').document(portal_request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")

    # For now, redirect to your own account management page
    return {"portalUrl": "https://ai-video-generator-mvp.netlify.app/account"}


# --- fal.ai Image Upload Helper ---
def upload_image_to_fal(base64_data: str) -> str | None:
    """
    Upload base64 image data to fal.ai and return the URL.
    fal.ai requires image URLs, not raw base64 data.
    """
    if not base64_data or not isinstance(base64_data, str) or not base64_data.startswith("data:image"):
        return None

    try:
        # Extract the base64 content after the data URI prefix
        _header, encoded_data = base64_data.split(",", 1)
        image_bytes = base64.b64decode(encoded_data)

        # Determine content type from header
        content_type = "image/png"
        if "jpeg" in _header or "jpg" in _header:
            content_type = "image/jpeg"
        elif "webp" in _header:
            content_type = "image/webp"
        elif "gif" in _header:
            content_type = "image/gif"

        # Upload to fal.ai file storage
        file_url = fal_client.upload(image_bytes, content_type=content_type)
        logger.info(f"Image uploaded to fal.ai: {file_url[:50]}...")
        return file_url
    except Exception as e:
        logger.error(f"Failed to upload image to fal.ai: {e}")
        return None


@app.post("/generate-video")
@limiter.limit("10/minute")
async def generate_media(request: Request, video_request: VideoRequest):
    if not db:
        raise HTTPException(status_code=500, detail="Firestore database not initialized.")

    user_ref = db.collection('users').document(video_request.user_id)

    # Get fal.ai model configuration
    model_config = FAL_MODELS.get(video_request.model_id)
    if not model_config:
        raise HTTPException(status_code=400, detail=f"Invalid model ID: {video_request.model_id}. Valid models: {list(FAL_MODELS.keys())}")

    # Calculate credits dynamically based on model and parameters
    try:
        credits_to_deduct = calculate_credits(video_request.model_id, video_request.params)
    except ValueError as e:
        logger.error(f"Credit calculation failed for model {video_request.model_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid model configuration: {e}")

    # Generate a unique transaction ID for audit trail
    transaction_id = db.collection('generation_transactions').document().id
    transaction_ref = db.collection('generation_transactions').document(transaction_id)

    # --- ATOMIC CREDIT DEDUCTION WITH FIRESTORE TRANSACTION ---
    @firestore.transactional
    def deduct_credits_atomically(transaction, user_ref, credits_to_deduct):
        """
        Atomically check and deduct credits to prevent race conditions.
        Returns the user's credits before deduction for verification.
        """
        user_snapshot = user_ref.get(transaction=transaction)

        if not user_snapshot.exists:
            raise ValueError("User not found")

        user_data = user_snapshot.to_dict()
        current_credits = user_data.get('credits', 0)

        if current_credits < credits_to_deduct:
            raise ValueError(f"Insufficient credits. Required: {credits_to_deduct}, Available: {current_credits}")

        # Atomically update credits
        new_credits = current_credits - credits_to_deduct
        transaction.update(user_ref, {'credits': new_credits})

        return current_credits

    try:
        # Create pending transaction record BEFORE deduction
        transaction_ref.set({
            'userId': video_request.user_id,
            'modelId': video_request.model_id,
            'creditsDeducted': credits_to_deduct,
            'status': 'pending',
            'createdAt': firestore.SERVER_TIMESTAMP,
            'params': {k: v for k, v in video_request.params.items() if k != 'image' and not (isinstance(v, str) and v.startswith('data:'))}
        })

        # Execute atomic credit deduction
        transaction = db.transaction()
        credits_before = deduct_credits_atomically(transaction, user_ref, credits_to_deduct)
        logger.info(f"Atomically deducted {credits_to_deduct} credits from user {video_request.user_id}. Before: {credits_before}, After: {credits_before - credits_to_deduct}")

        # Update transaction status to processing
        transaction_ref.update({
            'status': 'processing',
            'creditsBefore': credits_before,
            'creditsAfter': credits_before - credits_to_deduct,
            'processedAt': firestore.SERVER_TIMESTAMP
        })

    except ValueError as e:
        # Update transaction as failed before deduction
        transaction_ref.update({
            'status': 'failed_validation',
            'error': str(e),
            'failedAt': firestore.SERVER_TIMESTAMP
        })
        error_message = str(e)
        if "User not found" in error_message:
            raise HTTPException(status_code=403, detail="User not found.")
        elif "Insufficient credits" in error_message:
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=500, detail=f"Credit deduction failed: {e}")
    except Exception as e:
        logger.error(f"Transaction failed for user {video_request.user_id}: {e}")
        transaction_ref.update({
            'status': 'failed_transaction',
            'error': str(e),
            'failedAt': firestore.SERVER_TIMESTAMP
        })
        raise HTTPException(status_code=500, detail=f"Failed to manage credits: {e}")

    # --- FAL.AI GENERATION PHASE ---
    try:
        api_params = video_request.params.copy()

        # Determine which endpoint to use (T2V, I2V, or T2I)
        image_param = model_config.get("image_param")
        has_image = False

        # Check for image in params and upload to fal.ai
        for param_name in ["image", "start_image", "image_url"]:
            if param_name in api_params:
                image_data = api_params.get(param_name)
                if image_data and isinstance(image_data, str) and image_data.startswith("data:image"):
                    # Upload to fal.ai and replace with URL
                    uploaded_url = upload_image_to_fal(image_data)
                    if uploaded_url and image_param:
                        # Remove the original param and use the model's expected parameter name
                        api_params.pop(param_name, None)
                        api_params[image_param] = uploaded_url
                        has_image = True
                        logger.info(f"Image uploaded for {video_request.model_id}, using I2V endpoint")
                        break
                else:
                    # Remove empty or invalid image params
                    api_params.pop(param_name, None)

        # Select the appropriate model endpoint
        if "t2i" in model_config:
            # Image generation model (Nano Banana Pro)
            model_endpoint = model_config["t2i"]
            logger.info(f"Using T2I endpoint: {model_endpoint}")
        elif has_image and model_config.get("i2v"):
            # Image-to-video
            model_endpoint = model_config["i2v"]
            logger.info(f"Using I2V endpoint: {model_endpoint}")
        elif model_config.get("t2v"):
            # Text-to-video
            model_endpoint = model_config["t2v"]
            logger.info(f"Using T2V endpoint: {model_endpoint}")
        else:
            raise ValueError(f"Model {video_request.model_id} has no valid endpoint configured")

        # Call fal.ai API
        logger.info(f"Calling fal.ai: {model_endpoint} for user {video_request.user_id}")
        fal_result = fal_client.run(model_endpoint, arguments=api_params)

        # Extract output URLs from fal.ai response
        output_urls = []
        if "video" in fal_result:
            # Video output (most video models)
            video_data = fal_result["video"]
            if isinstance(video_data, dict) and "url" in video_data:
                output_urls = [video_data["url"]]
            elif isinstance(video_data, str):
                output_urls = [video_data]
        elif "images" in fal_result:
            # Multiple image outputs (Nano Banana Pro)
            output_urls = [img["url"] if isinstance(img, dict) else img for img in fal_result["images"]]
        elif "image" in fal_result:
            # Single image output
            img_data = fal_result["image"]
            if isinstance(img_data, dict) and "url" in img_data:
                output_urls = [img_data["url"]]
            elif isinstance(img_data, str):
                output_urls = [img_data]
        elif "url" in fal_result:
            # Direct URL in response
            output_urls = [fal_result["url"]]
        else:
            logger.error(f"Unexpected fal.ai response format: {list(fal_result.keys())}")
            raise TypeError(f"Unexpected fal.ai response format. Keys: {list(fal_result.keys())}")

        if not output_urls:
            raise ValueError("No output URLs returned from fal.ai")

        # Update transaction as completed
        transaction_ref.update({
            'status': 'completed',
            'completedAt': firestore.SERVER_TIMESTAMP,
            'outputUrls': output_urls
        })

        # Save to user's generations subcollection for history display
        # Determine output type based on model configuration
        is_image_model = "t2i" in model_config
        output_type = "image" if is_image_model else "video"

        # Save each output to the user's generations subcollection
        for output_url in output_urls:
            generation_ref = user_ref.collection('generations').document()
            generation_ref.set({
                'outputUrl': output_url,
                'outputType': output_type,
                'prompt': api_params.get('prompt', ''),
                'modelId': video_request.model_id,
                'status': 'completed',
                'createdAt': firestore.SERVER_TIMESTAMP,
                'transactionId': transaction_id
            })

        logger.info(f"Generation completed for user {video_request.user_id}, transaction {transaction_id}. Outputs: {len(output_urls)}")
        return {"output_urls": output_urls}

    except Exception as e:
        # Extract detailed error information
        error_type = type(e).__name__
        error_message = str(e)
        error_traceback = traceback.format_exc()

        # Try to extract fal.ai specific error details if available
        fal_error_details = {}
        if hasattr(e, 'response'):
            try:
                fal_error_details['response'] = str(e.response)
            except Exception:
                pass
        if hasattr(e, 'status_code'):
            fal_error_details['status_code'] = e.status_code
        if hasattr(e, 'body'):
            try:
                fal_error_details['body'] = str(e.body)
            except Exception:
                pass
        if hasattr(e, 'message'):
            fal_error_details['message'] = e.message

        # Log comprehensive error details
        logger.error(f"""
========== FAL.AI GENERATION ERROR ==========
User ID: {video_request.user_id}
Model ID: {video_request.model_id}
Transaction ID: {transaction_id}
Credits to refund: {credits_to_deduct}
Error Type: {error_type}
Error Message: {error_message}
Fal.ai Details: {json.dumps(fal_error_details) if fal_error_details else 'N/A'}
API Params (sanitized): {json.dumps({k: v for k, v in api_params.items() if not (isinstance(v, str) and (v.startswith('data:') or len(v) > 200))})}
Traceback:
{error_traceback}
=============================================""")

        # Update transaction as failed with detailed error info
        transaction_ref.update({
            'status': 'failed_generation',
            'error': error_message,
            'errorType': error_type,
            'errorDetails': fal_error_details if fal_error_details else None,
            'failedAt': firestore.SERVER_TIMESTAMP,
            'refundAttempted': True
        })

        # --- REFUND WITH FAILED REFUND TRACKING ---
        try:
            user_ref.update({'credits': firestore.Increment(credits_to_deduct)})
            transaction_ref.update({
                'refundStatus': 'completed',
                'refundedAt': firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Successfully refunded {credits_to_deduct} credits to user {video_request.user_id}")
        except Exception as refund_e:
            # CRITICAL: Log and store failed refund for manual resolution
            logger.critical(f"FAILED TO REFUND {credits_to_deduct} CREDITS for user {video_request.user_id}. Error: {refund_e}")

            # Store in failed_credit_refunds collection for manual resolution
            try:
                db.collection('failed_credit_refunds').add({
                    'userId': video_request.user_id,
                    'creditsAmount': credits_to_deduct,
                    'transactionId': transaction_id,
                    'originalError': str(e),
                    'refundError': str(refund_e),
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'resolved': False,
                    'retryCount': 0
                })

                # Update transaction with refund failure
                transaction_ref.update({
                    'refundStatus': 'failed',
                    'refundError': str(refund_e)
                })
            except Exception as log_e:
                logger.critical(f"CRITICAL: Failed to log refund failure for user {video_request.user_id}: {log_e}")

        # Construct user-friendly error message with details
        user_error_message = f"Generation failed ({error_type}): {error_message}"

        # Add specific hints for common fal.ai errors
        if 'downstream_service' in error_message.lower():
            user_error_message += " - The AI model service is temporarily unavailable. Please try again later."
        elif 'file_download' in error_message.lower():
            user_error_message += " - Failed to process the input image. Please ensure it is accessible."
        elif 'timeout' in error_message.lower() or 'timed out' in error_message.lower():
            user_error_message += " - The generation request timed out. Please try again."
        elif 'rate' in error_message.lower() and 'limit' in error_message.lower():
            user_error_message += " - Rate limit exceeded. Please wait a moment and try again."

        raise HTTPException(status_code=500, detail=user_error_message)

# ========================
# === ADMIN ENDPOINTS ===
# ========================
@app.get("/admin/stats", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_admin_stats(request: Request):
    users_collection = db.collection('users').stream()
    return {"userCount": len(list(users_collection))}

@app.get("/admin/users", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_all_users(request: Request):
    users_list = []
    users_docs = db.collection('users').stream()
    for user in users_docs:
        user_data = user.to_dict()
        users_list.append({ "id": user.id, "email": user_data.get("email"), "plan": user_data.get("activePlan", "Starter Plan"), "generationCount": 0 })
    return users_list

@app.post("/admin/users", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def create_user_account(request: Request, user_create: AdminUserCreateRequest):
    try:
        user = auth.create_user(email=user_create.email, password=user_create.password)
        db.collection('users').document(user.uid).set({ "email": user.email, "createdAt": firestore.SERVER_TIMESTAMP, "credits": 10, "activePlan": "Starter" })
        return {"message": "User created successfully", "uid": user.uid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/users/{user_id}", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_user_details(request: Request, user_id: str):
    user_doc = db.collection('users').document(user_id).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    transactions = []
    trans_docs = db.collection('users').document(user_id).collection('payments').order_by("createdAt", direction=firestore.Query.DESCENDING).stream()
    for doc in trans_docs:
        trans_data = doc.to_dict()
        trans_data["id"] = doc.id
        if 'createdAt' in trans_data and trans_data['createdAt']:
            trans_data['createdAt'] = trans_data['createdAt'].strftime('%d/%m/%Y')
        transactions.append(trans_data)
    user_profile = user_doc.to_dict()
    user_profile['name'] = user_profile.get('name', user_profile.get('email', ''))
    return {"profile": user_profile, "transactions": transactions}

@app.put("/admin/users/{user_id}", dependencies=[admin_dependency])
@limiter.limit("20/minute")
async def update_user_details(request: Request, user_id: str, user_update: AdminUserUpdateRequest):
    auth.update_user(user_id, email=user_update.email, display_name=user_update.name)
    db.collection('users').document(user_id).update({"email": user_update.email, "name": user_update.name})
    return {"message": "User updated successfully"}

@app.put("/admin/users/{user_id}/billing", dependencies=[admin_dependency])
@limiter.limit("20/minute")
async def update_billing_info(request: Request, user_id: str, billing_update: AdminBillingUpdateRequest):
    db.collection('users').document(user_id).update({"billingInfo": billing_update.dict()})
    return {"message": "Billing information updated successfully."}

@app.post("/admin/users/{user_id}/gift-credits", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def gift_user_credits(request: Request, user_id: str, credit_request: AdminCreditRequest):
    db.collection('users').document(user_id).update({"credits": firestore.Increment(credit_request.amount)})
    return {"message": f"{credit_request.amount} credits gifted successfully"}

@app.post("/admin/transactions/{user_id}", dependencies=[admin_dependency])
@limiter.limit("20/minute")
async def add_transaction(request: Request, user_id: str, trans_request: AdminTransactionRequest):
    trans_date = datetime.strptime(trans_request.date, '%d/%m/%Y')
    db.collection('users').document(user_id).collection('payments').add({
        "createdAt": trans_date,
        "amount": trans_request.amount,
        "type": trans_request.type,
        "status": trans_request.status
    })
    return {"message": "Transaction added successfully"}

@app.put("/admin/transactions/{user_id}/{trans_id}", dependencies=[admin_dependency])
@limiter.limit("20/minute")
async def update_transaction(request: Request, user_id: str, trans_id: str, trans_request: AdminTransactionRequest):
    trans_ref = db.collection('users').document(user_id).collection('payments').document(trans_id)
    trans_date = datetime.strptime(trans_request.date, '%d/%m/%Y')
    trans_ref.update({
        "createdAt": trans_date,
        "amount": trans_request.amount,
        "type": trans_request.type,
        "status": trans_request.status
    })
    return {"message": "Transaction updated successfully"}

@app.delete("/admin/transactions/{user_id}/{trans_id}", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def delete_transaction(request: Request, user_id: str, trans_id: str):
    db.collection('users').document(user_id).collection('payments').document(trans_id).delete()
    return {"message": "Transaction deleted successfully"}

@app.post("/admin/users/{user_id}/reset-password", dependencies=[admin_dependency])
@limiter.limit("5/minute")
async def reset_user_password(request: Request, user_id: str, password_data: dict):
    """Reset a user's password (admin only)"""
    new_password = password_data.get("newPassword")

    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        # Update password in Firebase Auth
        auth.update_user(user_id, password=new_password)
        logger.info(f"Password reset for user {user_id}")
        return {"message": "Password reset successfully"}
    except Exception as e:
        logger.error(f"Failed to reset password for user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to reset password: {str(e)}")

# --- Seller Management Endpoints ---

class SellerSuspendRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

@app.get("/admin/sellers", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_all_sellers(request: Request):
    """Get all sellers with their stats"""
    try:
        # Query users who are sellers (isSeller = true)
        sellers_query = db.collection('users').where('isSeller', '==', True).stream()

        sellers = []
        verified_count = 0
        unverified_count = 0
        suspended_count = 0

        for doc in sellers_query:
            user_data = doc.to_dict()
            seller_profile = user_data.get('sellerProfile', {})

            # Determine seller status
            status = seller_profile.get('status', 'unverified')
            if status == 'verified':
                verified_count += 1
            elif status == 'suspended':
                suspended_count += 1
            else:
                unverified_count += 1

            sellers.append({
                'userId': doc.id,
                'email': user_data.get('email', ''),
                'displayName': user_data.get('displayName', user_data.get('name', '')),
                'status': status,
                'paypalEmail': seller_profile.get('paypalEmail'),
                'verificationDate': seller_profile.get('verificationDate'),
                'suspensionReason': seller_profile.get('suspensionReason'),
                'suspendedAt': seller_profile.get('suspendedAt')
            })

        return {
            'sellers': sellers,
            'count': len(sellers),
            'verified': verified_count,
            'unverified': unverified_count,
            'suspended': suspended_count
        }
    except Exception as e:
        logger.error(f"Failed to fetch sellers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch sellers: {str(e)}")

@app.post("/admin/seller/{user_id}/verify", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def verify_seller(request: Request, user_id: str):
    """Verify a seller account"""
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        if not user_data.get('isSeller'):
            raise HTTPException(status_code=400, detail="User is not a seller")

        # Update seller profile status
        user_ref.update({
            'sellerProfile.status': 'verified',
            'sellerProfile.verificationDate': firestore.SERVER_TIMESTAMP,
            'sellerProfile.suspensionReason': firestore.DELETE_FIELD,
            'sellerProfile.suspendedAt': firestore.DELETE_FIELD
        })

        logger.info(f"Seller {user_id} verified by admin")
        return {"message": "Seller verified successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify seller {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify seller: {str(e)}")

@app.post("/admin/seller/{user_id}/suspend", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def suspend_seller(request: Request, user_id: str, suspend_data: SellerSuspendRequest):
    """Suspend a seller account with reason"""
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        if not user_data.get('isSeller'):
            raise HTTPException(status_code=400, detail="User is not a seller")

        # Update seller profile status
        user_ref.update({
            'sellerProfile.status': 'suspended',
            'sellerProfile.suspensionReason': suspend_data.reason,
            'sellerProfile.suspendedAt': firestore.SERVER_TIMESTAMP
        })

        logger.info(f"Seller {user_id} suspended by admin. Reason: {suspend_data.reason}")
        return {"message": "Seller suspended successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to suspend seller {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to suspend seller: {str(e)}")

@app.post("/admin/seller/{user_id}/unsuspend", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def unsuspend_seller(request: Request, user_id: str):
    """Unsuspend a seller account (restore to verified status)"""
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        if not user_data.get('isSeller'):
            raise HTTPException(status_code=400, detail="User is not a seller")

        seller_profile = user_data.get('sellerProfile', {})
        if seller_profile.get('status') != 'suspended':
            raise HTTPException(status_code=400, detail="Seller is not suspended")

        # Restore to verified status
        user_ref.update({
            'sellerProfile.status': 'verified',
            'sellerProfile.suspensionReason': firestore.DELETE_FIELD,
            'sellerProfile.suspendedAt': firestore.DELETE_FIELD
        })

        logger.info(f"Seller {user_id} unsuspended by admin")
        return {"message": "Seller unsuspended successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unsuspend seller {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to unsuspend seller: {str(e)}")

# --- Payout Management Endpoints ---

@app.get("/admin/payouts/queue", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_pending_payouts(request: Request):
    """Get all pending payout requests"""
    try:
        payouts = []

        # Query all users who are sellers
        sellers_query = db.collection('users').where('isSeller', '==', True).stream()

        for seller_doc in sellers_query:
            user_id = seller_doc.id
            # Get pending withdrawal requests for this seller
            withdrawals = db.collection('users').document(user_id).collection('withdrawalRequests').where('status', '==', 'pending').stream()

            for withdrawal_doc in withdrawals:
                withdrawal_data = withdrawal_doc.to_dict()
                payouts.append({
                    'id': withdrawal_doc.id,
                    'userId': user_id,
                    'amount': withdrawal_data.get('amount', 0),
                    'paypalEmail': withdrawal_data.get('paypalEmail', ''),
                    'status': withdrawal_data.get('status', 'pending'),
                    'createdAt': withdrawal_data.get('createdAt'),
                    'docPath': f"users/{user_id}/withdrawalRequests/{withdrawal_doc.id}"
                })

        # Sort by creation date (newest first)
        payouts.sort(key=lambda x: x.get('createdAt', ''), reverse=True)

        return {'payouts': payouts}
    except Exception as e:
        logger.error(f"Failed to fetch pending payouts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending payouts: {str(e)}")

@app.get("/admin/payouts/history", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_payout_history(request: Request):
    """Get payout history (approved, rejected, completed)"""
    try:
        payouts = []

        # Query all users who are sellers
        sellers_query = db.collection('users').where('isSeller', '==', True).stream()

        for seller_doc in sellers_query:
            user_id = seller_doc.id
            # Get non-pending withdrawal requests for this seller
            withdrawals = db.collection('users').document(user_id).collection('withdrawalRequests').where('status', 'in', ['approved', 'rejected', 'completed']).stream()

            for withdrawal_doc in withdrawals:
                withdrawal_data = withdrawal_doc.to_dict()
                payouts.append({
                    'id': withdrawal_doc.id,
                    'userId': user_id,
                    'amount': withdrawal_data.get('amount', 0),
                    'paypalEmail': withdrawal_data.get('paypalEmail', ''),
                    'status': withdrawal_data.get('status'),
                    'createdAt': withdrawal_data.get('createdAt'),
                    'approvedAt': withdrawal_data.get('approvedAt'),
                    'rejectedAt': withdrawal_data.get('rejectedAt'),
                    'completedAt': withdrawal_data.get('completedAt'),
                    'docPath': f"users/{user_id}/withdrawalRequests/{withdrawal_doc.id}"
                })

        # Sort by most recent activity
        payouts.sort(key=lambda x: x.get('approvedAt') or x.get('rejectedAt') or x.get('completedAt') or x.get('createdAt', ''), reverse=True)

        return {'payouts': payouts}
    except Exception as e:
        logger.error(f"Failed to fetch payout history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch payout history: {str(e)}")

class PayoutActionRequest(BaseModel):
    user_id: str

@app.post("/admin/payouts/{payout_id}/approve", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def approve_payout(request: Request, payout_id: str, action_data: PayoutActionRequest):
    """Approve a payout request"""
    try:
        user_id = action_data.user_id
        payout_ref = db.collection('users').document(user_id).collection('withdrawalRequests').document(payout_id)
        payout_doc = payout_ref.get()

        if not payout_doc.exists:
            raise HTTPException(status_code=404, detail="Payout request not found")

        payout_data = payout_doc.to_dict()
        if payout_data.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Payout is not in pending status")

        # Update payout status to approved
        payout_ref.update({
            'status': 'approved',
            'approvedAt': firestore.SERVER_TIMESTAMP
        })

        amount = payout_data.get('amount', 0)
        paypal_email = payout_data.get('paypalEmail', '')

        # Send email notification to seller
        await send_payout_status_email(user_id, 'approved', amount, paypal_email)

        logger.info(f"Payout {payout_id} approved for user {user_id}")
        return {"message": "Payout approved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve payout {payout_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve payout: {str(e)}")

@app.post("/admin/payouts/{payout_id}/reject", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def reject_payout(request: Request, payout_id: str, action_data: PayoutActionRequest):
    """Reject a payout request and refund balance"""
    try:
        user_id = action_data.user_id
        payout_ref = db.collection('users').document(user_id).collection('withdrawalRequests').document(payout_id)
        payout_doc = payout_ref.get()

        if not payout_doc.exists:
            raise HTTPException(status_code=404, detail="Payout request not found")

        payout_data = payout_doc.to_dict()
        if payout_data.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Payout is not in pending status")

        amount = payout_data.get('amount', 0)

        # Update payout status to rejected
        payout_ref.update({
            'status': 'rejected',
            'rejectedAt': firestore.SERVER_TIMESTAMP
        })

        # Refund the amount to seller's pending balance
        user_ref = db.collection('users').document(user_id)
        user_ref.update({
            'sellerProfile.pendingBalance': firestore.Increment(amount)
        })

        # Send email notification to seller
        await send_payout_status_email(user_id, 'rejected', amount)

        logger.info(f"Payout {payout_id} rejected for user {user_id}, amount {amount} refunded")
        return {"message": "Payout rejected and balance refunded"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reject payout {payout_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reject payout: {str(e)}")

@app.post("/admin/payouts/{payout_id}/complete", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def complete_payout(request: Request, payout_id: str, action_data: PayoutActionRequest):
    """Mark a payout as completed (after PayPal transfer is done)"""
    try:
        user_id = action_data.user_id
        payout_ref = db.collection('users').document(user_id).collection('withdrawalRequests').document(payout_id)
        payout_doc = payout_ref.get()

        if not payout_doc.exists:
            raise HTTPException(status_code=404, detail="Payout request not found")

        payout_data = payout_doc.to_dict()
        if payout_data.get('status') != 'approved':
            raise HTTPException(status_code=400, detail="Payout must be approved before completing")

        amount = payout_data.get('amount', 0)

        # Update payout status to completed
        payout_ref.update({
            'status': 'completed',
            'completedAt': firestore.SERVER_TIMESTAMP
        })

        # Update seller's withdrawn balance
        user_ref = db.collection('users').document(user_id)
        user_ref.update({
            'sellerProfile.withdrawnBalance': firestore.Increment(amount)
        })

        # Send email notification to seller
        await send_payout_status_email(user_id, 'completed', amount)

        logger.info(f"Payout {payout_id} completed for user {user_id}, amount {amount}")
        return {"message": "Payout marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete payout {payout_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete payout: {str(e)}")

# --- Withdrawal Email Notification Endpoints ---

class WithdrawalNotificationRequest(BaseModel):
    requestId: str
    amount: float
    paypalEmail: EmailStr

class SellerProfileUpdateRequest(BaseModel):
    paypalEmail: EmailStr

class PayoutRequestCreate(BaseModel):
    amount: float = Field(..., gt=0, le=10000, description="Withdrawal amount in EUR")
    paypalEmail: EmailStr

# --- User Authentication Dependency (for seller endpoints) ---
async def verify_user_token(authorization: str = Header(...)):
    """Verify Firebase ID token and return user ID"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token['uid']
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# --- Seller Endpoints ---

@app.get("/seller/profile")
@limiter.limit("30/minute")
async def get_seller_profile(request: Request, user_id: str = Depends(verify_user_token)):
    """Get the seller profile for the authenticated user"""
    try:
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        seller_profile = user_data.get('sellerProfile', {})

        # Get seller balance from subcollection
        balance_doc = db.collection('users').document(user_id).collection('seller_balance').document('current').get()
        balance_data = balance_doc.to_dict() if balance_doc.exists else {}

        return {
            "profile": {
                "displayName": user_data.get('displayName', ''),
                "email": user_data.get('email', ''),
                "paypalEmail": seller_profile.get('paypalEmail', ''),
                "isVerifiedSeller": seller_profile.get('isVerifiedSeller', False),
                "verificationStatus": seller_profile.get('verificationStatus', 'unverified'),
                "createdAt": seller_profile.get('createdAt'),
            },
            "balance": {
                "availableBalance": balance_data.get('availableBalance', 0),
                "pendingBalance": balance_data.get('pendingBalance', 0),
                "totalEarnings": balance_data.get('totalEarnings', 0),
                "withdrawnBalance": seller_profile.get('withdrawnBalance', 0),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get seller profile for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get seller profile: {str(e)}")


@app.post("/seller/profile")
@limiter.limit("10/minute")
async def update_seller_profile(request: Request, profile_data: SellerProfileUpdateRequest, user_id: str = Depends(verify_user_token)):
    """Update the seller profile for the authenticated user"""
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        # Update seller profile with PayPal email
        user_ref.update({
            'sellerProfile.paypalEmail': profile_data.paypalEmail,
            'sellerProfile.updatedAt': firestore.SERVER_TIMESTAMP
        })

        logger.info(f"Seller profile updated for user {user_id}")
        return {"message": "Profile updated successfully", "paypalEmail": profile_data.paypalEmail}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update seller profile for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@app.get("/seller/balance")
@limiter.limit("30/minute")
async def get_seller_balance(request: Request, user_id: str = Depends(verify_user_token)):
    """Get the seller balance for the authenticated user"""
    try:
        # Get seller balance from subcollection
        balance_doc = db.collection('users').document(user_id).collection('seller_balance').document('current').get()
        balance_data = balance_doc.to_dict() if balance_doc.exists else {}

        # Get withdrawn balance from user profile
        user_doc = db.collection('users').document(user_id).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        seller_profile = user_data.get('sellerProfile', {})

        return {
            "availableBalance": balance_data.get('availableBalance', 0),
            "pendingBalance": balance_data.get('pendingBalance', 0),
            "totalEarnings": balance_data.get('totalEarnings', 0),
            "withdrawnBalance": seller_profile.get('withdrawnBalance', 0),
            "lastUpdated": balance_data.get('lastUpdated')
        }
    except Exception as e:
        logger.error(f"Failed to get seller balance for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get balance: {str(e)}")


@app.get("/seller/transactions")
@limiter.limit("30/minute")
async def get_seller_transactions(request: Request, user_id: str = Depends(verify_user_token), limit: int = 50, offset: int = 0):
    """Get transaction history for the authenticated seller"""
    try:
        # Query seller transactions subcollection
        transactions_ref = db.collection('users').document(user_id).collection('seller_transactions')
        query = transactions_ref.order_by('createdAt', direction=firestore.Query.DESCENDING).limit(limit).offset(offset)

        transactions = []
        for doc in query.stream():
            tx_data = doc.to_dict()
            tx_data['id'] = doc.id
            # Convert Firestore timestamps to ISO strings
            if tx_data.get('createdAt'):
                tx_data['createdAt'] = tx_data['createdAt'].isoformat() if hasattr(tx_data['createdAt'], 'isoformat') else str(tx_data['createdAt'])
            transactions.append(tx_data)

        # Get total count for pagination
        total_count = len(list(transactions_ref.stream()))

        return {
            "transactions": transactions,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get seller transactions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get transactions: {str(e)}")


@app.post("/seller/payout-request")
@limiter.limit("5/minute")
async def create_payout_request(request: Request, payout_data: PayoutRequestCreate, user_id: str = Depends(verify_user_token)):
    """Create a new payout/withdrawal request for the authenticated seller"""
    try:
        # Get seller balance to verify available funds
        balance_doc = db.collection('users').document(user_id).collection('seller_balance').document('current').get()
        balance_data = balance_doc.to_dict() if balance_doc.exists else {}
        available_balance = balance_data.get('availableBalance', 0)

        if payout_data.amount > available_balance:
            raise HTTPException(status_code=400, detail=f"Insufficient balance. Available: €{available_balance:.2f}")

        # Check for pending payout requests
        pending_requests = db.collection('users').document(user_id).collection('payout_requests').where('status', '==', 'pending').stream()
        pending_count = len(list(pending_requests))
        if pending_count > 0:
            raise HTTPException(status_code=400, detail="You already have a pending payout request")

        # Create payout request document
        payout_ref = db.collection('users').document(user_id).collection('payout_requests').document()
        payout_request = {
            'id': payout_ref.id,
            'userId': user_id,
            'amount': payout_data.amount,
            'paypalEmail': payout_data.paypalEmail,
            'status': 'pending',
            'createdAt': firestore.SERVER_TIMESTAMP,
            'docPath': f'users/{user_id}/payout_requests/{payout_ref.id}'
        }
        payout_ref.set(payout_request)

        # Deduct from available balance and add to pending
        balance_ref = db.collection('users').document(user_id).collection('seller_balance').document('current')
        balance_ref.update({
            'availableBalance': firestore.Increment(-payout_data.amount),
            'pendingBalance': firestore.Increment(payout_data.amount),
            'lastUpdated': firestore.SERVER_TIMESTAMP
        })

        logger.info(f"Payout request created for user {user_id}: €{payout_data.amount}")
        return {
            "message": "Payout request created successfully",
            "requestId": payout_ref.id,
            "amount": payout_data.amount,
            "paypalEmail": payout_data.paypalEmail,
            "status": "pending"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create payout request for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create payout request: {str(e)}")


@app.get("/seller/payout-requests")
@limiter.limit("30/minute")
async def get_seller_payout_requests(request: Request, user_id: str = Depends(verify_user_token), limit: int = 20, status: str = None):
    """Get payout request history for the authenticated seller"""
    try:
        requests_ref = db.collection('users').document(user_id).collection('payout_requests')

        # Apply status filter if provided
        if status and status in ['pending', 'approved', 'completed', 'rejected']:
            query = requests_ref.where('status', '==', status).order_by('createdAt', direction=firestore.Query.DESCENDING).limit(limit)
        else:
            query = requests_ref.order_by('createdAt', direction=firestore.Query.DESCENDING).limit(limit)

        payout_requests = []
        for doc in query.stream():
            req_data = doc.to_dict()
            req_data['id'] = doc.id
            # Convert timestamps
            for field in ['createdAt', 'approvedAt', 'completedAt', 'rejectedAt']:
                if req_data.get(field) and hasattr(req_data[field], 'isoformat'):
                    req_data[field] = req_data[field].isoformat()
            payout_requests.append(req_data)

        return {
            "payoutRequests": payout_requests,
            "total": len(payout_requests)
        }
    except Exception as e:
        logger.error(f"Failed to get payout requests for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get payout requests: {str(e)}")


@app.get("/seller/transactions/export")
@limiter.limit("5/minute")
async def export_seller_transactions(request: Request, user_id: str = Depends(verify_user_token), format: str = "csv", start_date: str = None, end_date: str = None):
    """Export seller transactions as CSV or PDF"""
    try:
        from datetime import datetime
        import io
        import csv
        from fastapi.responses import StreamingResponse

        # Query transactions
        transactions_ref = db.collection('users').document(user_id).collection('seller_transactions')
        query = transactions_ref.order_by('createdAt', direction=firestore.Query.DESCENDING)

        transactions = []
        for doc in query.stream():
            tx_data = doc.to_dict()
            tx_data['id'] = doc.id

            # Filter by date if provided
            if start_date or end_date:
                tx_date = tx_data.get('createdAt')
                if tx_date:
                    if hasattr(tx_date, 'isoformat'):
                        tx_date_str = tx_date.strftime('%Y-%m-%d')
                    else:
                        continue
                    if start_date and tx_date_str < start_date:
                        continue
                    if end_date and tx_date_str > end_date:
                        continue

            transactions.append(tx_data)

        if format.lower() == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Transaction ID', 'Type', 'Amount (EUR)', 'Description', 'Date', 'Status'])

            for tx in transactions:
                date_str = ''
                if tx.get('createdAt'):
                    if hasattr(tx['createdAt'], 'strftime'):
                        date_str = tx['createdAt'].strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        date_str = str(tx['createdAt'])

                writer.writerow([
                    tx.get('id', ''),
                    tx.get('type', ''),
                    f"{tx.get('amount', 0):.2f}",
                    tx.get('description', ''),
                    date_str,
                    tx.get('status', '')
                ])

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=transactions_{user_id[:8]}_{datetime.now().strftime('%Y%m%d')}.csv"}
            )

        elif format.lower() == "pdf":
            # Generate PDF using reportlab
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet

                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)
                elements = []
                styles = getSampleStyleSheet()

                # Title
                elements.append(Paragraph("Transaction History", styles['Heading1']))
                elements.append(Spacer(1, 20))

                # Table data
                table_data = [['ID', 'Type', 'Amount', 'Description', 'Date', 'Status']]
                for tx in transactions:
                    date_str = ''
                    if tx.get('createdAt'):
                        if hasattr(tx['createdAt'], 'strftime'):
                            date_str = tx['createdAt'].strftime('%Y-%m-%d')
                        else:
                            date_str = str(tx['createdAt'])[:10]

                    table_data.append([
                        tx.get('id', '')[:8] + '...' if len(tx.get('id', '')) > 8 else tx.get('id', ''),
                        tx.get('type', ''),
                        f"€{tx.get('amount', 0):.2f}",
                        tx.get('description', '')[:30] + '...' if len(tx.get('description', '')) > 30 else tx.get('description', ''),
                        date_str,
                        tx.get('status', '')
                    ])

                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)

                doc.build(elements)
                buffer.seek(0)

                return StreamingResponse(
                    buffer,
                    media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=transactions_{user_id[:8]}_{datetime.now().strftime('%Y%m%d')}.pdf"}
                )
            except ImportError:
                raise HTTPException(status_code=500, detail="PDF export not available - reportlab not installed")
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'pdf'")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export transactions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export transactions: {str(e)}")


@app.post("/seller/withdrawal-request-notification")
@limiter.limit("10/minute")
async def send_withdrawal_notification(request: Request, notification_data: WithdrawalNotificationRequest, authorization: str = Header(...)):
    """Send email notification to admin when a seller requests a withdrawal"""
    try:
        # Verify authentication
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        token = authorization.split("Bearer ")[1]
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token['uid']

        # Check if Resend is configured
        if not RESEND_API_KEY:
            logger.warning("RESEND_API_KEY not configured - skipping withdrawal notification email")
            return {"message": "Email service not configured", "emailSent": False}

        if not ADMIN_EMAIL:
            logger.warning("ADMIN_EMAIL not configured - skipping withdrawal notification email")
            return {"message": "Admin email not configured", "emailSent": False}

        # Get user details from Firestore
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        seller_name = user_data.get('displayName') or user_data.get('name') or 'Unknown Seller'
        seller_email = user_data.get('email', 'No email')

        # Generate email HTML
        email_html = get_new_withdrawal_request_email(
            seller_name=seller_name,
            seller_email=seller_email,
            amount=notification_data.amount,
            paypal_email=notification_data.paypalEmail,
            seller_id=user_id,
            request_id=notification_data.requestId
        )

        # Send email via Resend
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [ADMIN_EMAIL],
            "subject": f"💰 New Withdrawal Request - €{notification_data.amount:.2f} from {seller_name}",
            "html": email_html,
            "tags": [
                {"name": "type", "value": "withdrawal_request"},
                {"name": "seller_id", "value": user_id},
            ],
        }

        email_response = resend.Emails.send(params)
        logger.info(f"Withdrawal notification email sent for request {notification_data.requestId}: {email_response.get('id')}")

        return {"message": "Notification sent successfully", "emailSent": True, "emailId": email_response.get('id')}

    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send withdrawal notification for request {notification_data.requestId}: {e}")
        # Don't fail the request if email fails - withdrawal is still created
        return {"message": f"Failed to send email: {str(e)}", "emailSent": False}


async def send_payout_status_email(user_id: str, status: str, amount: float, paypal_email: str = ""):
    """Helper function to send payout status emails to sellers"""
    try:
        if not RESEND_API_KEY:
            logger.warning("RESEND_API_KEY not configured - skipping payout status email")
            return False

        # Get user details
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            logger.error(f"User {user_id} not found for payout email")
            return False

        user_data = user_doc.to_dict()
        seller_name = user_data.get('displayName') or user_data.get('name') or 'Seller'
        seller_email = user_data.get('email')

        if not seller_email:
            logger.error(f"No email found for user {user_id}")
            return False

        # Generate email based on status
        if status == 'approved':
            email_html = get_payout_approved_email(seller_name, amount, paypal_email)
            subject = f"✓ Your Withdrawal of €{amount:.2f} Has Been Approved"
        elif status == 'completed':
            email_html = get_payout_completed_email(seller_name, amount)
            subject = f"✓ €{amount:.2f} Has Been Sent to Your PayPal"
        elif status == 'rejected':
            email_html = get_payout_rejected_email(seller_name, amount)
            subject = f"Withdrawal Request Update - €{amount:.2f}"
        else:
            logger.error(f"Unknown payout status: {status}")
            return False

        # Send email via Resend
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [seller_email],
            "subject": subject,
            "html": email_html,
            "tags": [
                {"name": "type", "value": f"payout_{status}"},
                {"name": "user_id", "value": user_id},
            ],
        }

        email_response = resend.Emails.send(params)
        logger.info(f"Payout {status} email sent to {seller_email}: {email_response.get('id')}")
        return True

    except Exception as e:
        logger.error(f"Failed to send payout {status} email to user {user_id}: {e}")
        return False


# --- Marketplace Purchase Endpoints ---

@app.post("/marketplace/create-purchase-payment")
@limiter.limit("10/minute")
async def create_marketplace_purchase_payment(request: Request, purchase_request: MarketplacePurchaseRequest, authorization: str = Header(...)):
    """Create a payment for marketplace product purchase using PayTrust"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    # Verify user authentication
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    try:
        token = authorization.split("Bearer ")[1]
        decoded_token = auth.verify_id_token(token)
        token_user_id = decoded_token['uid']

        # Ensure the token user matches the request user
        if token_user_id != purchase_request.userId:
            raise HTTPException(status_code=403, detail="User ID mismatch")

    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    user_id = purchase_request.userId
    logger.info(f"Marketplace Purchase Request - User: {user_id}, Product: {purchase_request.productId}")

    # Verify buyer exists
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")

    user_data = user_doc.to_dict()

    # Verify product exists in marketplace (uses marketplace_listings collection)
    product_ref = db.collection('marketplace_listings').document(purchase_request.productId)
    product_doc = product_ref.get()
    if not product_doc.exists:
        raise HTTPException(status_code=404, detail="Product not found in marketplace.")

    product_data = product_doc.to_dict()

    # SECURITY: Use verified data from database, NOT client-provided data
    verified_price = product_data.get('price')
    verified_seller_id = product_data.get('sellerId')
    verified_seller_name = product_data.get('sellerName', '')
    verified_video_url = product_data.get('videoUrl')
    verified_thumbnail_url = product_data.get('thumbnailUrl')
    verified_title = product_data.get('title', '')

    # Validate price exists
    if not verified_price or verified_price <= 0:
        raise HTTPException(status_code=400, detail="Invalid product price.")

    # Prevent self-purchase
    if verified_seller_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot purchase your own product.")

    # Check if product is still available
    if product_data.get('status') == 'sold':
        raise HTTPException(status_code=400, detail="This product has already been sold.")

    # Create pending marketplace purchase record using VERIFIED database data
    purchase_ref = db.collection('marketplace_purchases').document()
    purchase_id = purchase_ref.id

    purchase_ref.set({
        "buyerId": user_id,
        "buyerEmail": user_data.get("email"),
        "buyerName": user_data.get("name", ""),
        "sellerId": verified_seller_id,  # From database, not client
        "sellerName": verified_seller_name,  # From database, not client
        "productId": purchase_request.productId,
        "title": verified_title,  # From database, not client
        "videoUrl": verified_video_url,  # From database, not client
        "thumbnailUrl": verified_thumbnail_url,  # From database, not client
        "price": verified_price,  # From database, not client
        "platformFee": round(verified_price * 0.15, 2),  # 15% platform fee
        "sellerEarnings": round(verified_price * 0.85, 2),  # 85% to seller
        "status": "pending",
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    logger.info(f"Marketplace purchase record created: {purchase_id}", extra={
        "user_id": user_id,
        "product_id": purchase_request.productId,
        "price": purchase_request.price
    })

    # Prepare PayTrust payment request
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {PAYTRUST_API_KEY}"
    }

    backend_url = os.getenv('BACKEND_URL', 'https://aivideogenerator-production.up.railway.app')
    frontend_url = "https://ai-video-generator-mvp.netlify.app"

    payload = {
        "paymentType": "DEPOSIT",
        "amount": verified_price,  # Use verified price from database
        "currency": "EUR",
        "returnUrl": f"{frontend_url}/marketplace/purchase/success?purchase_id={purchase_id}",
        "errorUrl": f"{frontend_url}/marketplace/purchase/cancel?purchase_id={purchase_id}",
        "webhookUrl": f"{backend_url}/paytrust-webhook",
        "referenceId": f"marketplace_purchase_id={purchase_id};user_id={user_id};seller_id={verified_seller_id};product_id={purchase_request.productId}",
        "customer": {
            "referenceId": user_id,
            "firstName": user_data.get("name", "").split()[0] if user_data.get("name") else "User",
            "lastName": user_data.get("name", "").split()[-1] if user_data.get("name") and len(user_data.get("name", "").split()) > 1 else "Customer",
            "email": user_data.get("email", "customer@example.com")
        }
    }

    logger.debug(f"PayTrust API request for marketplace purchase {purchase_id}")

    try:
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers)

        logger.debug(f"PayTrust response status: {response.status_code} for marketplace purchase {purchase_id}")

        response.raise_for_status()
        payment_data = response.json()

        logger.debug(f"PayTrust payment data received for marketplace purchase {purchase_id}")

        # PayTrust wraps response in a "result" object
        result = payment_data.get("result", payment_data)

        # Update purchase record with PayTrust payment ID
        purchase_ref.update({
            "paytrustPaymentId": result.get("id"),
            "paytrustTransactionId": result.get("transactionId")
        })

        # Get redirect URL from result object
        redirect_url = result.get("redirectUrl") or result.get("redirect_url") or result.get("paymentUrl")

        if not redirect_url:
            logger.error(f"No redirect URL in PayTrust response for marketplace purchase {purchase_id}")
            raise HTTPException(status_code=500, detail=f"PayTrust did not return a payment URL. Response: {payment_data}")

        logger.info(f"Marketplace payment URL obtained for purchase {purchase_id}")
        return {"paymentUrl": redirect_url, "purchaseId": purchase_id}

    except requests.exceptions.HTTPError as e:
        error_detail = f"PayTrust API Error ({e.response.status_code}): {e.response.text}"
        logger.error(error_detail, extra={"purchase_id": purchase_id})
        # Update purchase status to failed
        purchase_ref.update({"status": "payment_failed", "error": error_detail})
        raise HTTPException(status_code=500, detail=error_detail)
    except requests.exceptions.RequestException as e:
        error_detail = f"Request failed: {str(e)}"
        logger.error(error_detail, extra={"purchase_id": purchase_id})
        purchase_ref.update({"status": "payment_failed", "error": error_detail})
        raise HTTPException(status_code=500, detail=error_detail)
    except Exception as e:
        error_detail = f"Unexpected error: {str(e)}"
        logger.error(error_detail, extra={"purchase_id": purchase_id})
        purchase_ref.update({"status": "payment_failed", "error": error_detail})
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/marketplace/purchase/{purchase_id}")
@limiter.limit("30/minute")
async def get_marketplace_purchase(request: Request, purchase_id: str, authorization: str = Header(...)):
    """Get marketplace purchase details (for success/cancel pages)"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    # Verify user authentication
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    try:
        token = authorization.split("Bearer ")[1]
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token['uid']
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    purchase_ref = db.collection('marketplace_purchases').document(purchase_id)
    purchase_doc = purchase_ref.get()

    if not purchase_doc.exists:
        raise HTTPException(status_code=404, detail="Purchase not found")

    purchase_data = purchase_doc.to_dict()

    # Only buyer or seller can view purchase details
    if purchase_data.get('buyerId') != user_id and purchase_data.get('sellerId') != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": purchase_id,
        "status": purchase_data.get("status"),
        "title": purchase_data.get("title"),
        "price": purchase_data.get("price"),
        "videoUrl": purchase_data.get("videoUrl") if purchase_data.get("status") == "completed" else None,
        "createdAt": purchase_data.get("createdAt"),
        "completedAt": purchase_data.get("completedAt")
    }


@app.get("/marketplace/my-purchases")
@limiter.limit("30/minute")
async def get_my_marketplace_purchases(request: Request, authorization: str = Header(...)):
    """Get all marketplace purchases for the authenticated user"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    # Verify user authentication
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    try:
        token = authorization.split("Bearer ")[1]
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token['uid']
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    try:
        # Query purchases where user is the buyer
        purchases_query = db.collection('marketplace_purchases').where('buyerId', '==', user_id).where('status', '==', 'completed').order_by('completedAt', direction=firestore.Query.DESCENDING).limit(50)
        purchases = purchases_query.stream()

        purchase_list = []
        for doc in purchases:
            data = doc.to_dict()
            purchase_list.append({
                "id": doc.id,
                "title": data.get("title"),
                "videoUrl": data.get("videoUrl"),
                "thumbnailUrl": data.get("thumbnailUrl"),
                "price": data.get("price"),
                "sellerName": data.get("sellerName"),
                "completedAt": data.get("completedAt")
            })

        return {"purchases": purchase_list}

    except Exception as e:
        logger.error(f"Failed to get purchases for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get purchases: {str(e)}")


# --- Main execution block ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    if not os.getenv("FAL_KEY"):
        logger.warning("FAL_KEY not set - generation will fail. Get your key at https://fal.ai")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
