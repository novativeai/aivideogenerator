import os
import logging
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, EmailStr, Field
import re
import replicate
import firebase_admin
from firebase_admin import credentials, firestore, auth
from typing import Dict, Any, List
import base64
import json
import io
from replicate.helpers import FileOutput
from datetime import datetime
import requests
import hmac
import hashlib
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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

# --- CORS Middleware ---
# Load allowed origins from environment, fallback to secure defaults
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '').split(',') if os.getenv('ALLOWED_ORIGINS') else [
    "http://localhost:3000",
    "https://ai-video-generator-mvp.netlify.app",
    "http://localhost:3001",
    "https://reelzila-admin.netlify.app"
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

# --- Model Mapping ---
REPLICATE_MODELS = {
    "kling-2.5": "kwaivgi/kling-v2.5-turbo-pro",
    "veo-3.1": "google/veo-3.1",
    "seedance-1-pro": "bytedance/seedance-1-pro",
    "wan-2.2": "wan-video/wan-2.2-i2v-a14b",
    "flux-1.1-pro-ultra": "black-forest-labs/flux-1.1-pro-ultra"
}
MODEL_IMAGE_PARAMS = {
    "kling-2.5": "start_image",
    "veo-3.1": "image",
    "seedance-1-pro": "image",
    "wan-2.2": "image",
    "flux-1.1-pro-ultra": None,
}

# --- Dynamic Credit Pricing Configuration ---
MODEL_CREDIT_PRICING = {
    "kling-2.5": {
        "base": 10,
        "modifiers": [
            {
                "param": "duration",
                "values": {"5": 10, "10": 20},
                "type": "set"
            }
        ]
    },
    "veo-3.1": {
        "base": 100,
        "modifiers": [
            {
                "param": "duration",
                "values": {"4": 50, "6": 75, "8": 100},
                "type": "set"
            }
        ]
    },
    "seedance-1-pro": {
        "base": 10,
        "modifiers": [
            {
                "param": "resolution",
                "values": {"480p": 10, "720p": 15, "1080p": 20},
                "type": "set"
            }
        ]
    },
    "wan-2.2": {
        "base": 3,
        "modifiers": [
            {
                "param": "resolution",
                "values": {"480p": 3, "720p": 5},
                "type": "set"
            }
        ]
    },
    "flux-1.1-pro-ultra": {
        "base": 2
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
    return {
        "status": "healthy" if db else "unhealthy",
        "timestamp": datetime.now().isoformat()
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
            "has_replicate_token": bool(os.getenv('REPLICATE_API_TOKEN')),
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
            else:
                logger.warning(f"No payment_id or subscription_id found in metadata for user {user_id}")
        
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

@app.post("/generate-video")
@limiter.limit("10/minute")
async def generate_media(request: Request, video_request: VideoRequest):
    if not db:
        raise HTTPException(status_code=500, detail="Firestore database not initialized.")

    user_ref = db.collection('users').document(video_request.user_id)
    model_string = REPLICATE_MODELS.get(video_request.model_id)
    if not model_string:
        raise HTTPException(status_code=400, detail="Invalid model ID provided.")

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

    # --- GENERATION PHASE ---
    try:
        api_params = video_request.params.copy()
        image_param_name = MODEL_IMAGE_PARAMS.get(video_request.model_id)
        if image_param_name and image_param_name in api_params:
            image_data = api_params.get(image_param_name)
            if image_data and isinstance(image_data, str) and image_data.startswith("data:image"):
                _header, encoded_data = image_data.split(",", 1)
                api_params[image_param_name] = io.BytesIO(base64.b64decode(encoded_data))
            else:
                api_params.pop(image_param_name, None)

        replicate_output = replicate.run(model_string, input=api_params)
        processed_output = str(replicate_output) if isinstance(replicate_output, FileOutput) else replicate_output

        # Update transaction as completed
        if isinstance(processed_output, str):
            output_urls = [processed_output]
        elif isinstance(processed_output, list):
            output_urls = [str(item) for item in processed_output]
        else:
            raise TypeError("Unexpected model output format.")

        transaction_ref.update({
            'status': 'completed',
            'completedAt': firestore.SERVER_TIMESTAMP,
            'outputUrls': output_urls
        })

        logger.info(f"Generation completed for user {video_request.user_id}, transaction {transaction_id}")
        return {"output_urls": output_urls}

    except Exception as e:
        logger.error(f"Replicate task failed for user {video_request.user_id}. Refunding {credits_to_deduct} credits. Error: {e}")

        # Update transaction as failed
        transaction_ref.update({
            'status': 'failed_generation',
            'error': str(e),
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

        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

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

        logger.info(f"Payout {payout_id} completed for user {user_id}, amount {amount}")
        return {"message": "Payout marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete payout {payout_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete payout: {str(e)}")

# --- Main execution block ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    if not os.getenv("REPLICATE_API_TOKEN"):
        logger.critical("REPLICATE_API_TOKEN not set - application cannot start")
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
