import os
import logging
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, EmailStr
import replicate
import firebase_admin
from firebase_admin import credentials, firestore, auth
from typing import Dict, Any, List, Optional
import base64
import json
import io
from replicate.helpers import FileOutput
from datetime import datetime
import requests
import hmac
import hashlib
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, HtmlContent
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from google.api_core import retry

# Import email templates
try:
    from email_templates import get_payout_email, get_admin_email, get_new_withdrawal_request_email
except ImportError:
    # Fallback: define simple templates if file not found
    def get_payout_email(status: str, seller_name: str, amount: float, paypal_email: str = "", seller_id: str = "") -> str:
        return f"<p>Payout {status}: €{amount:.2f}</p>"
    def get_admin_email(seller_name: str, amount: float, paypal_email: str, seller_id: str) -> str:
        return f"<p>Payout ready: €{amount:.2f} to {paypal_email}</p>"
    def get_new_withdrawal_request_email(seller_name: str, seller_email: str, amount: float, paypal_email: str, seller_id: str, request_id: str) -> str:
        return f"<p>New withdrawal request: €{amount:.2f} to {paypal_email}</p>"

# --- Logging Configuration ---
# Set up structured logging without sensitive data
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# --- Initialization & Setup ---
load_dotenv()
app = FastAPI()
limiter = Limiter(key_func=get_remote_address)

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
    allow_methods=["GET", "POST"],  # Restrict to only needed methods
    allow_headers=["Content-Type", "Authorization"],  # Restrict to only needed headers
    max_age=3600,  # Cache preflight for 1 hour
)

# --- PayTrust Configuration ---
PAYTRUST_API_KEY = os.getenv("PAYTRUST_API_KEY")
PAYTRUST_PROJECT_ID = os.getenv("PAYTRUST_PROJECT_ID")  # Your PayTrust Project ID
PAYTRUST_API_URL = os.getenv("PAYTRUST_API_URL", "https://engine-sandbox.paytrust.io/api/v1")  # Use production URL when ready

# Price ID to Credits Mapping (configure based on your pricing tiers)
PRICE_ID_TO_CREDITS = {
    "price_YOUR_PRO_PLAN_PRICE_ID": {"credits": 250, "planName": "Creator"},
    "price_YOUR_TEAM_PLAN_PRICE_ID": {"credits": 1000, "planName": "Pro"}
}

# --- Firebase Admin SDK Setup ---
db = None
firebase_init_error = None

try:
    logger.info("Initializing Firebase Admin SDK")

    firebase_secret_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
    if not firebase_secret_base64:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 environment variable not found.")

    try:
        decoded_secret = base64.b64decode(firebase_secret_base64).decode('utf-8')
        service_account_info = json.loads(decoded_secret)
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to decode/parse Firebase credentials") from e

    bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')

    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_info)
        init_config = {'storageBucket': bucket_name} if bucket_name else {}
        firebase_admin.initialize_app(cred, init_config)

    db = firestore.client()
    logger.info("Firebase Admin SDK initialized successfully")

except Exception as e:
    firebase_init_error = str(e)
    logger.error(f"Failed to initialize Firebase Admin SDK")

# --- Pydantic Models ---
class VideoRequest(BaseModel):
    user_id: str
    model_id: str
    params: Dict[str, Any]

class PaymentRequest(BaseModel):
    userId: str
    customAmount: int | None = None

class SubscriptionRequest(BaseModel):
    userId: str
    priceId: str

class PortalRequest(BaseModel):
    userId: str

class MarketplacePurchaseRequest(BaseModel):
    userId: str
    productId: str
    title: str
    videoUrl: str
    thumbnailUrl: str | None = None
    price: float
    sellerName: str
    sellerId: str

    @validator('userId', 'productId', 'sellerId')
    def validate_id_format(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('ID cannot be empty')
        if len(v) > 255:
            raise ValueError('ID too long')
        return v.strip()

    @validator('title', 'sellerName')
    def validate_string_length(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Field cannot be empty')
        if len(v) > 500:
            raise ValueError('Field too long')
        return v.strip()

    @validator('price')
    def validate_price(cls, v):
        if v <= 0 or v > 10000:
            raise ValueError('Price must be between 0.01 and 10000')
        return v

class AdminUserCreateRequest(BaseModel):
    email: str
    password: str

    @validator('email')
    def validate_email(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Email cannot be empty')
        # RFC 5322 simplified email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        if len(v) > 254:
            raise ValueError('Email too long')
        return v.lower().strip()

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 255:
            raise ValueError('Password too long')
        return v

class AdminUserUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None

class AdminCreditRequest(BaseModel):
    amount: int

class AdminTransactionRequest(BaseModel):
    date: str
    amount: int
    type: str
    status: str

class AdminBillingUpdateRequest(BaseModel):
    nameOnCard: str
    address: str
    city: str
    state: str
    validTill: str

# --- Seller/Payout Models ---
class SellerProfileRequest(BaseModel):
    paypalEmail: str

    @validator('paypalEmail')
    def validate_paypal_email(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('PayPal email cannot be empty')
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        if len(v) > 254:
            raise ValueError('Email too long')
        return v.lower().strip()

class PayoutRequestRequest(BaseModel):
    amount: float

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        if v > 100000:
            raise ValueError('Amount too large (max €100,000)')
        return v

class SellerTransaction(BaseModel):
    videoId: str
    buyerId: str
    amount: float
    timestamp: datetime
    status: str = "completed"

class PayoutRequest(BaseModel):
    amount: float
    paypalEmail: str
    status: str = "pending"
    createdAt: datetime

class AdminSellerSuspendRequest(BaseModel):
    reason: str

    @validator('reason')
    def validate_reason(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Suspension reason cannot be empty')
        if len(v) > 500:
            raise ValueError('Reason too long (max 500 characters)')
        return v.strip()

# --- Model Mapping ---
REPLICATE_MODELS = {
    "veo-3-fast": "google/veo-3-fast",
    "seedance-1-pro": "bytedance/seedance-1-pro",
    "wan-2.2": "wan-video/wan-2.2-i2v-a14b",
    "flux-kontext-pro": "black-forest-labs/flux-kontext-pro"
}
MODEL_IMAGE_PARAMS = {
    "seedance-1-pro": "image",
    "wan-2.2": "image",
    "flux-kontext-pro": "input_image",
}

# --- Email Service ---
def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send email using SendGrid - returns True on success"""
    try:
        sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        sendgrid_from = os.getenv("SENDGRID_FROM_EMAIL", "noreply@yourdomain.com")

        if not sendgrid_api_key:
            logger.warning("SendGrid API key not configured - skipping email")
            return False

        sg = SendGridAPIClient(sendgrid_api_key)
        message = Mail(
            from_email=sendgrid_from,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )

        response = sg.send(message)
        return response.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}")
        return False

def send_payout_notification(seller_email: str, status: str, amount: float, seller_name: str = "Seller", paypal_email: str = ""):
    """Send payout status notification to seller using template"""
    status_display = status.capitalize()

    # Map status to email subject
    subject_map = {
        "approved": f"✓ Payout Approved: €{amount:.2f}",
        "completed": f"✓ Payout Completed: €{amount:.2f} Received!",
        "rejected": f"Payout Rejected: €{amount:.2f}"
    }
    subject = subject_map.get(status, f"Payout {status_display}: €{amount:.2f}")

    # Get HTML content from template
    html_content = get_payout_email(status, seller_name, amount, paypal_email)

    return send_email(seller_email, subject, html_content)

def send_admin_notification(subject: str, html_content: str):
    """Send notification to admin email"""
    admin_email = os.getenv("ADMIN_EMAIL", "admin@yourdomain.com")
    return send_email(admin_email, subject, html_content)

# --- Security Dependency for Admin Routes ---
async def check_is_admin(authorization: str = Header(...)):
    """Verify user is authenticated as admin without leaking error details"""
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Admin request with missing/invalid authorization header")
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Extract and verify token
        id_token = authorization.split("Bearer ", 1)[1]

        # Validate token is non-empty
        if not id_token or len(id_token.strip()) == 0:
            logger.warning("Admin request with empty token")
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Verify Firebase token
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token.get('uid')

        if not uid:
            logger.warning("Token missing uid field")
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Check user exists and has admin role
        if not db:
            logger.error("Database not initialized for admin check")
            raise HTTPException(status_code=500, detail="Service unavailable")

        user_doc = db.collection('users').document(uid).get()
        if not user_doc.exists:
            logger.warning(f"Admin check for non-existent user")
            raise HTTPException(status_code=403, detail="Unauthorized")

        user_data = user_doc.to_dict()
        if user_data.get('isAdmin') is not True:
            logger.warning(f"Non-admin user attempted admin access")
            raise HTTPException(status_code=403, detail="Unauthorized")

        return uid

    except HTTPException:
        raise
    except ValueError as e:
        # Firebase token validation failed (invalid signature, expired, etc.)
        logger.warning("Token validation failed - invalid token")
        raise HTTPException(status_code=401, detail="Unauthorized")
    except Exception as e:
        # Catch all other errors without revealing details
        logger.error("Unexpected error in admin authentication")
        raise HTTPException(status_code=500, detail="Service unavailable")

admin_dependency = Depends(check_is_admin)

# =========================
# === PUBLIC ENDPOINTS ===
# =========================

@app.get("/health")
async def health_check():
    """Check if backend services are initialized properly"""
    return {
        "status": "healthy" if db else "unhealthy",
        "database": "initialized" if db else "not initialized",
        "firebase_error": firebase_init_error,
        "environment": {
            "has_firebase_secret": bool(os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')),
            "has_storage_bucket": bool(os.getenv('FIREBASE_STORAGE_BUCKET')),
            "has_paytrust_key": bool(os.getenv('PAYTRUST_API_KEY')),
            "has_replicate_token": bool(os.getenv('REPLICATE_API_TOKEN')),
        }
    }

@app.post("/create-payment")
@limiter.limit("5/minute")
async def create_payment(request: PaymentRequest, req: Request):
    """Create a one-time payment for credits using PayTrust"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    user_ref = db.collection('users').document(request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")

    user_data = user_doc.to_dict()

    if not request.customAmount or request.customAmount <= 0:
        raise HTTPException(status_code=400, detail="Invalid custom amount.")

    if request.customAmount > 1000:
        raise HTTPException(status_code=400, detail="Maximum amount is €1,000.")

    amount = request.customAmount
    credits_to_add = request.customAmount * 10

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

    # Prepare PayTrust payment request - simplified for one-time purchase
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {PAYTRUST_API_KEY}"
    }

    backend_url = os.getenv('BACKEND_URL')
    if not backend_url:
        logger.error("BACKEND_URL environment variable not configured")
        raise HTTPException(status_code=500, detail="Server configuration error")

    # Simplified payload matching your example
    payload = {
        "paymentType": "DEPOSIT",
        "amount": amount,
        "currency": "EUR",
        "returnUrl": f"https://ai-video-generator-mvp.netlify.app/payment/success?payment_id={payment_id}",
        "errorUrl": f"https://ai-video-generator-mvp.netlify.app/payment/cancel?payment_id={payment_id}",
        "webhookUrl": f"{backend_url}/paytrust-webhook",
        "referenceId": f"payment_id={payment_id};user_id={request.userId}",
        "customer": {
            "referenceId": request.userId,
            "firstName": user_data.get("name", "").split()[0] if user_data.get("name") else "User",
            "lastName": user_data.get("name", "").split()[-1] if user_data.get("name") and len(user_data.get("name", "").split()) > 1 else "Customer",
            "email": user_data.get("email", "customer@example.com")
        }
    }

    try:
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        payment_data = response.json()

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
            logger.error(f"PayTrust did not return payment URL for payment {payment_id}")
            raise HTTPException(status_code=500, detail="Payment service error")

        logger.info(f"Payment created successfully for user {request.userId}")
        return {"paymentUrl": redirect_url}

    except requests.exceptions.HTTPError as e:
        logger.error(f"PayTrust API error for payment {payment_id}")
        raise HTTPException(status_code=500, detail="Payment service error")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for payment {payment_id}")
        raise HTTPException(status_code=500, detail="Payment service unavailable")
    except Exception as e:
        logger.error(f"Unexpected error for payment {payment_id}")
        raise HTTPException(status_code=500, detail="Payment processing error")

@app.post("/marketplace/verify-seller/{seller_id}")
@limiter.limit("20/minute")
async def verify_seller_exists(seller_id: str, req: Request):
    """Verify that a seller exists and is eligible to sell"""
    if not db:
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

    try:
        # Check seller exists
        seller_doc = db.collection('users').document(seller_id).get()
        if not seller_doc.exists:
            return {"valid": False, "reason": "Seller not found"}

        seller_data = seller_doc.to_dict()

        # Verify seller is not suspended/banned
        if seller_data.get('suspended') is True or seller_data.get('banned') is True:
            return {"valid": False, "reason": "Seller account is not active"}

        # Return seller info
        return {
            "valid": True,
            "sellerName": seller_data.get('displayName') or seller_data.get('name'),
            "email": seller_data.get('email'),
            "verified": seller_data.get('sellerVerified', False)
        }
    except Exception as e:
        logger.error("Seller verification failed")
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

@app.post("/marketplace/create-purchase-payment")
@limiter.limit("10/minute")
async def create_marketplace_purchase_payment(request: MarketplacePurchaseRequest, req: Request):
    """Create a payment for marketplace video purchase using PayTrust"""
    if not db:
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

    # Verify buyer user exists
    user_ref = db.collection('users').document(request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user_doc.to_dict()

    # Verify product exists in marketplace and price matches
    product_ref = db.collection('marketplace_listings').document(request.productId)
    product_doc = product_ref.get()
    if not product_doc.exists:
        raise HTTPException(status_code=404, detail="Product not found in marketplace")

    # Verify price matches to prevent price manipulation
    product_data = product_doc.to_dict()
    if product_data.get("price") != request.price:
        logger.warning(f"Price mismatch for purchase {request.productId}")
        raise HTTPException(status_code=400, detail="Product price has changed")

    # Verify seller exists and is valid
    seller_doc = db.collection('users').document(request.sellerId).get()
    if not seller_doc.exists:
        logger.warning(f"Seller {request.sellerId} not found for purchase {request.productId}")
        raise HTTPException(status_code=400, detail="Seller information is invalid")

    seller_data = seller_doc.to_dict()
    if seller_data.get('suspended') is True or seller_data.get('banned') is True:
        logger.warning(f"Seller {request.sellerId} is suspended/banned")
        raise HTTPException(status_code=400, detail="Seller account is not active")

    # Create pending marketplace purchase record in Firestore
    purchase_ref = user_ref.collection('marketplace_purchases').document()
    purchase_id = purchase_ref.id
    purchase_ref.set({
        "productId": request.productId,
        "title": request.title,
        "videoUrl": request.videoUrl,
        "thumbnailUrl": request.thumbnailUrl,
        "price": request.price,
        "sellerName": request.sellerName,
        "sellerId": request.sellerId,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "status": "pending"
    })

    # Prepare PayTrust payment request
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {PAYTRUST_API_KEY}"
    }

    backend_url = os.getenv('BACKEND_URL')
    if not backend_url:
        logger.error("BACKEND_URL environment variable not configured")
        raise HTTPException(status_code=500, detail="Server configuration error")

    payload = {
        "paymentType": "DEPOSIT",
        "amount": request.price,
        "currency": "EUR",
        "returnUrl": f"https://ai-video-generator-mvp.netlify.app/marketplace?purchase=success",
        "errorUrl": f"https://ai-video-generator-mvp.netlify.app/marketplace?purchase=cancelled",
        "webhookUrl": f"{backend_url}/paytrust-webhook",
        "referenceId": f"purchase_id={purchase_id};user_id={request.userId};product_id={request.productId};purchase_type=marketplace",
        "customer": {
            "referenceId": request.userId,
            "firstName": user_data.get("name", "").split()[0] if user_data.get("name") else "User",
            "lastName": user_data.get("name", "").split()[-1] if user_data.get("name") and len(user_data.get("name", "").split()) > 1 else "Customer",
            "email": user_data.get("email", "customer@example.com")
        }
    }

    try:
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        payment_data = response.json()

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
            logger.error(f"PayTrust did not return payment URL for purchase {purchase_id}")
            raise HTTPException(status_code=500, detail="Payment service error")

        logger.info(f"Marketplace purchase created for user {request.userId}")
        return {"paymentUrl": redirect_url}

    except requests.exceptions.HTTPError as e:
        logger.error(f"PayTrust API error for purchase {purchase_id}")
        raise HTTPException(status_code=500, detail="Payment service error")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for purchase {purchase_id}")
        raise HTTPException(status_code=500, detail="Payment service unavailable")
    except Exception as e:
        logger.error(f"Unexpected error for purchase {purchase_id}")
        raise HTTPException(status_code=500, detail="Payment processing error")

@app.post("/create-subscription")
@limiter.limit("5/minute")
async def create_subscription(request: SubscriptionRequest, req: Request):
    """Create a recurring subscription using PayTrust"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    user_ref = db.collection('users').document(request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")

    user_data = user_doc.to_dict()

    # Get subscription details from price ID
    subscription_info = PRICE_ID_TO_CREDITS.get(request.priceId)
    if not subscription_info:
        raise HTTPException(status_code=400, detail="Invalid price ID.")

    amount = 22 if subscription_info["planName"] == "Creator" else 49
    credits_per_month = subscription_info["credits"]
    plan_name = subscription_info["planName"]
    
    # Create subscription record in Firestore
    subscription_ref = user_ref.collection('subscriptions').document()
    subscription_id = subscription_ref.id
    subscription_ref.set({
        "priceId": request.priceId,
        "planName": plan_name,
        "amount": amount,
        "creditsPerMonth": credits_per_month,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "status": "pending"
    })

    # Prepare PayTrust recurring payment request
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {PAYTRUST_API_KEY}"
    }
    
    # Calculate next billing date (1 month from now)
    from datetime import timedelta
    next_billing = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")

    backend_url = os.getenv('BACKEND_URL')
    if not backend_url:
        logger.error("BACKEND_URL environment variable not configured")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
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
        "referenceId": f"subscription_id={subscription_id};user_id={request.userId};price_id={request.priceId}",
        "customer": {
            "referenceId": request.userId,
            "firstName": user_data.get("name", "").split()[0] if user_data.get("name") else "User",
            "lastName": user_data.get("name", "").split()[-1] if user_data.get("name") and len(user_data.get("name", "").split()) > 1 else "Customer",
            "email": user_data.get("email", "customer@example.com")
        },
        "paymentMethod": "BASIC_CARD"
    }

    try:
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        payment_data = response.json()
        
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
            logger.error(f"PayTrust did not return payment URL for subscription {subscription_id}")
            raise HTTPException(status_code=500, detail="Payment service error")

        logger.info(f"Subscription created for user {request.userId}")
        return {"paymentUrl": redirect_url}

    except requests.exceptions.HTTPError as e:
        logger.error(f"PayTrust API error for subscription {subscription_id}")
        raise HTTPException(status_code=500, detail="Payment service error")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for subscription {subscription_id}")
        raise HTTPException(status_code=500, detail="Payment service unavailable")
    except Exception as e:
        logger.error(f"Unexpected error for subscription {subscription_id}")
        raise HTTPException(status_code=500, detail="Payment processing error")

def verify_paytrust_signature(body: bytes, signature: str) -> bool:
    """
    Verify PayTrust webhook signature
    PayTrust signs webhooks with HMAC-SHA256 using the signing key
    """
    try:
        signing_key = os.getenv('PAYTRUST_SIGNING_KEY')
        if not signing_key:
            logger.error("PAYTRUST_SIGNING_KEY not configured")
            return False

        computed_signature = hmac.new(
            signing_key.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature)
    except Exception as e:
        logger.error("Webhook signature verification failed")
        return False

@app.post("/paytrust-webhook")
@limiter.limit("100/minute")
async def paytrust_webhook(request: Request, req: Request):
    """
    Handle webhook notifications from PayTrust
    Verifies webhook signature before processing
    """
    body = await request.body()
    signature = request.headers.get('X-PayTrust-Signature', '')

    # Verify signature
    if not signature or not verify_paytrust_signature(body, signature):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body)

    # Extract event data from PayTrust response
    # PayTrust may send data in different structures, handle both
    if "result" in payload:
        event_data = payload.get("result", {})
    else:
        event_data = payload

    event_type = event_data.get("state") or payload.get("state")

    # Extract unique transaction/event ID
    transaction_id = event_data.get("transactionId") or event_data.get("id") or payload.get("eventId")
    if not transaction_id:
        logger.warning("Webhook missing unique transaction ID")
        raise HTTPException(status_code=400, detail="Missing transaction ID")

    # IDEMPOTENCY CHECK
    webhook_ref = db.collection('processed_webhooks').document(transaction_id)
    webhook_doc = webhook_ref.get()

    if webhook_doc.exists:
        webhook_data = webhook_doc.to_dict()
        logger.info(f"Webhook {transaction_id} already processed at {webhook_data.get('processedAt')}")
        return {"status": "already_processed", "transactionId": transaction_id}

    # Mark as processing (prevents concurrent processing)
    webhook_ref.set({
        'processedAt': firestore.SERVER_TIMESTAMP,
        'payload': payload,
        'status': 'processing',
        'eventType': event_type
    })

    try:
        # Extract remaining data
        state = event_type
        payment_id = event_data.get("id")
        reference_id = event_data.get("referenceId", "")
        amount = event_data.get("amount")

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
        purchase_id = metadata.get("purchase_id")
        product_id = metadata.get("product_id")
        purchase_type = metadata.get("purchase_type")

        if not user_id:
            logger.warning("Webhook received without user_id")
            webhook_ref.update({'status': 'failed', 'error': 'Missing userId'})
            raise HTTPException(status_code=400, detail="Missing userId in webhook")

        # Verify user exists
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            logger.error(f"Webhook for non-existent user: {user_id}")
            db.collection('orphaned_payments').add({
                'transactionId': transaction_id,
                'payload': payload,
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            webhook_ref.update({'status': 'failed', 'error': 'User not found'})
            raise ValueError("User not found")
        
        # Handle different payment states
        # PayTrust uses: COMPLETED (success), FAILED, DECLINED, PENDING, CHECKOUT
        if state == "COMPLETED" or state == "SUCCESS":

            # Check if this is a subscription payment or one-time payment
            if subscription_doc_id or price_id:

                # This is a subscription payment (initial or recurring)
                subscription_info = PRICE_ID_TO_CREDITS.get(price_id) if price_id else None
                credits_to_add = subscription_info["credits"] if subscription_info else 250  # Default to Creator plan
                plan_name = subscription_info["planName"] if subscription_info else "Creator"
                
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

                logger.info(f"Subscription payment processed")
            
            elif payment_doc_id:

                # This is a one-time payment
                payment_ref = user_ref.collection('payments').document(payment_doc_id)
                payment_doc = payment_ref.get()

                if not payment_doc.exists:
                    raise ValueError("Payment record not found")

                payment_data = payment_doc.to_dict()

                # VALIDATE AMOUNT (prevent tampering)
                webhook_amount = amount
                stored_amount = payment_data.get("amount")
                expected_credits = webhook_amount * 10 if webhook_amount else 0  # 1 EUR = 10 credits
                stored_credits = payment_data.get("creditsPurchased", 0)

                if stored_amount != webhook_amount:
                    logger.critical(f"Amount mismatch - stored: {stored_amount}, webhook: {webhook_amount}")
                    raise ValueError("Amount validation failed")

                if abs(stored_credits - expected_credits) > 1:  # Allow 1 credit tolerance for rounding
                    logger.warning(f"Credit mismatch - using webhook amount as source of truth")
                    credits_to_add = expected_credits
                else:
                    credits_to_add = expected_credits

                # Update payment status from pending to paid
                payment_ref.update({
                    "status": "paid",
                    "paidAt": firestore.SERVER_TIMESTAMP,
                    "paytrustTransactionId": transaction_id
                })

                # Add credits to user (atomic)
                user_ref.update({
                    "credits": firestore.Increment(credits_to_add)
                })

                logger.info(f"One-time payment processed - added {credits_to_add} credits to user {user_id}")

            elif purchase_id and purchase_type == "marketplace":

                # This is a marketplace purchase
                purchase_ref = user_ref.collection('marketplace_purchases').document(purchase_id)
                purchase_doc = purchase_ref.get()

                if purchase_doc.exists:
                    purchase_data = purchase_doc.to_dict()

                    purchase_amount = purchase_data.get("price", 0.0)
                    seller_id = purchase_data.get("sellerId")
                    buyer_id = user_id

                    # Update purchase status from pending to paid
                    purchase_ref.update({
                        "status": "paid",
                        "paidAt": firestore.SERVER_TIMESTAMP,
                        "paytrustTransactionId": transaction_id
                    })

                    # Save purchased video to users/{buyerId}/purchased_videos/{productId}
                    purchased_video_ref = user_ref.collection('purchased_videos').document(product_id)
                    purchased_video_ref.set({
                        "id": product_id,
                        "title": purchase_data.get("title"),
                        "videoUrl": purchase_data.get("videoUrl"),
                        "thumbnailUrl": purchase_data.get("thumbnailUrl"),
                        "price": purchase_data.get("price"),
                        "sellerName": purchase_data.get("sellerName"),
                        "sellerId": purchase_data.get("sellerId"),
                        "purchasedAt": firestore.SERVER_TIMESTAMP,
                        "paytrustTransactionId": transaction_id
                    })

                    # === SELLER EARNINGS ===
                    # Record seller transaction and update seller balance
                    if seller_id:
                        try:
                            seller_ref = db.collection('users').document(seller_id)

                            # Create seller transaction record
                            seller_ref.collection('seller_transactions').add({
                                "videoId": product_id,
                                "buyerId": buyer_id,
                                "amount": purchase_amount,
                                "timestamp": firestore.SERVER_TIMESTAMP,
                                "status": "completed",
                                "paytrustTransactionId": transaction_id
                            })

                            # Update seller balance
                            balance_ref = seller_ref.collection('seller_balance').document('current')
                            balance_ref.set({
                                "totalEarned": firestore.Increment(purchase_amount),
                                "pendingBalance": firestore.Increment(purchase_amount),
                                "withdrawnBalance": 0.0,
                                "lastTransactionDate": firestore.SERVER_TIMESTAMP
                            }, merge=True)

                            logger.info(f"Seller earnings recorded: {seller_id} earned €{purchase_amount}")
                        except Exception as seller_error:
                            logger.error(f"Failed to record seller earnings for {seller_id}")

                    logger.info(f"Marketplace purchase processed")


        elif state == "FAIL" or state == "FAILED" or state == "DECLINED":

            # Handle failed payments
            if payment_doc_id:
                payment_ref = user_ref.collection('payments').document(payment_doc_id)
                payment_doc = payment_ref.get()
                if payment_doc.exists:
                    payment_ref.update({
                        "status": "failed",
                        "failedAt": firestore.SERVER_TIMESTAMP
                    })

            if subscription_doc_id:
                sub_ref = user_ref.collection('subscriptions').document(subscription_doc_id)
                sub_doc = sub_ref.get()
                if sub_doc.exists:
                    sub_ref.update({
                        "status": "failed",
                        "failedAt": firestore.SERVER_TIMESTAMP
                    })

            if purchase_id:
                purchase_ref = user_ref.collection('marketplace_purchases').document(purchase_id)
                purchase_doc = purchase_ref.get()
                if purchase_doc.exists:
                    purchase_ref.update({
                        "status": "failed",
                        "failedAt": firestore.SERVER_TIMESTAMP
                    })

            logger.info(f"Payment failed")

        elif state == "PENDING" or state == "CHECKOUT":
            # Payment is still processing
            logger.info(f"Payment pending/checkout")

        # Mark webhook as successfully processed
        webhook_ref.update({'status': 'success'})

        return {"status": "processed", "transactionId": transaction_id}

    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        webhook_ref.update({
            'status': 'failed',
            'error': str(e),
            'failedAt': firestore.SERVER_TIMESTAMP
        })
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@app.get("/payment-status/{payment_id}")
@limiter.limit("30/minute")
async def check_payment_status(payment_id: str, user_id: str, authorization: str = Header(...), req: Request = None):
    """Allow frontend to check payment status - requires authentication"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    # Verify user is authenticated and can only access their own payments
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        id_token = authorization.split("Bearer ")[1]
        decoded_token = auth.verify_id_token(id_token)
        token_uid = decoded_token['uid']

        # Prevent users from accessing other users' payment statuses
        if token_uid != user_id:
            logger.warning(f"Unauthorized payment status access attempt")
            raise HTTPException(status_code=403, detail="Unauthorized")

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
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Payment status check failed")
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/create-customer-portal-session")
async def create_customer_portal(request: PortalRequest):
    """
    Note: PayTrust may not have a built-in customer portal like Stripe.
    You may need to build your own subscription management UI.
    This endpoint is kept for compatibility but may need custom implementation.
    """
    user_ref = db.collection('users').document(request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists: 
        raise HTTPException(status_code=404, detail="User not found.")
    
    # For now, redirect to your own account management page
    return {"portalUrl": "https://ai-video-generator-mvp.netlify.app/account"}

# ============================
# === CREDIT REFUND HELPER ===
# ============================

@retry.Retry(predicate=retry.if_exception_type(Exception), maximum=3)
def refund_credit_with_retry(user_ref):
    """Refund credit with automatic retry"""
    user_ref.update({'credits': firestore.Increment(1)})
    return True

@app.post("/generate-video")
@limiter.limit("5/minute")  # Reduced from 30
@limiter.limit("50/hour")
async def generate_media(request: VideoRequest, req: Request):
    """Generate video using Replicate API with credit management"""
    if not db:
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

    user_id = request.user_id
    model_id = request.model_id
    params = request.params

    user_ref = db.collection('users').document(user_id)
    model_string = REPLICATE_MODELS.get(model_id)

    if not model_string:
        raise HTTPException(status_code=400, detail="Invalid model ID provided.")

    # Use Firestore transaction for atomic read-modify-write
    transaction = db.transaction()

    @firestore.transactional
    def deduct_credit_safely(transaction, user_ref):
        snapshot = user_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = snapshot.to_dict()
        current_credits = user_data.get('credits', 0)

        if current_credits <= 0:
            raise HTTPException(status_code=402, detail="Insufficient credits")

        # Atomic update
        transaction.update(user_ref, {'credits': current_credits - 1})
        return current_credits - 1

    # Execute transaction
    try:
        new_balance = deduct_credit_safely(transaction, user_ref)
        logger.info(f"Credit deducted for user {user_id}, new balance: {new_balance}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transaction failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process credit deduction")

    try:
        # Prepare API parameters
        api_params = params.copy() if params else {}
        image_param_name = MODEL_IMAGE_PARAMS.get(model_id)

        # Handle image parameter if present
        if image_param_name and image_param_name in api_params:
            image_data = api_params.get(image_param_name)
            if image_data and isinstance(image_data, str) and image_data.startswith("data:image"):
                try:
                    _header, encoded_data = image_data.split(",", 1)
                    api_params[image_param_name] = io.BytesIO(base64.b64decode(encoded_data))
                except Exception as e:
                    logger.warning("Failed to decode image data")
                    raise HTTPException(status_code=400, detail="Invalid image format")
            else:
                api_params.pop(image_param_name, None)

        # Call Replicate API
        replicate_output = replicate.run(model_string, input=api_params)
        processed_output = str(replicate_output) if isinstance(replicate_output, FileOutput) else replicate_output

        # Format output
        if isinstance(processed_output, str):
            return {"output_urls": [processed_output]}
        elif isinstance(processed_output, list):
            return {"output_urls": [str(item) for item in processed_output]}
        else:
            logger.error("Unexpected output format from Replicate")
            raise HTTPException(status_code=500, detail="Generation failed")

    except HTTPException:
        raise
    except Exception as e:
        # Refund credit on failure
        logger.error(f"Video generation failed: {str(e)}")
        try:
            refund_credit_with_retry(user_ref)
            logger.info(f"Credit refunded for failed generation - user {user_id}")
        except Exception as refund_error:
            logger.critical(f"CRITICAL: Failed to refund credit for user {user_id} - MANUAL INTERVENTION NEEDED")
            # TODO: Send alert to admin
        raise HTTPException(status_code=500, detail="Video generation failed")

# ============================
# === SELLER ENDPOINTS ===
# ============================

@app.get("/seller/profile")
@limiter.limit("30/minute")
async def get_seller_profile(authorization: str = Header(...), req: Request = None):
    """Get seller profile and PayPal settings"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        id_token = authorization.split("Bearer ", 1)[1]
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token.get('uid')

        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get seller profile
        seller_profile_ref = db.collection('users').document(user_id).collection('seller_profile').document('settings')
        seller_profile_doc = seller_profile_ref.get()

        if seller_profile_doc.exists:
            profile_data = seller_profile_doc.to_dict()
            return {
                "isPaayal": profile_data.get('isPaayal', False),
                "paypalEmail": profile_data.get('paypalEmail'),
                "verified": profile_data.get('verified', False),
                "createdAt": profile_data.get('createdAt')
            }
        else:
            return {
                "isPaayal": False,
                "paypalEmail": None,
                "verified": False,
                "createdAt": None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to get seller profile")
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/seller/profile")
@limiter.limit("5/minute")
async def set_seller_profile(request: SellerProfileRequest, authorization: str = Header(...), req: Request = None):
    """Set up PayPal email for seller account"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        id_token = authorization.split("Bearer ", 1)[1]
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token.get('uid')

        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Update seller profile
        seller_profile_ref = db.collection('users').document(user_id).collection('seller_profile').document('settings')
        seller_profile_ref.set({
            "paypalEmail": request.paypalEmail,
            "isPaayal": True,
            "verified": True,
            "updatedAt": firestore.SERVER_TIMESTAMP
        }, merge=True)

        logger.info("Seller profile updated")
        return {
            "message": "Seller profile updated successfully",
            "paypalEmail": request.paypalEmail
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update seller profile")
        raise HTTPException(status_code=500, detail="Failed to update profile")

@app.get("/seller/balance")
@limiter.limit("30/minute")
async def get_seller_balance(authorization: str = Header(...), req: Request = None):
    """Get seller earnings balance"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        id_token = authorization.split("Bearer ", 1)[1]
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token.get('uid')

        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get seller balance
        balance_ref = db.collection('users').document(user_id).collection('seller_balance').document('current')
        balance_doc = balance_ref.get()

        if balance_doc.exists:
            balance_data = balance_doc.to_dict()
            return {
                "totalEarned": balance_data.get('totalEarned', 0.0),
                "pendingBalance": balance_data.get('pendingBalance', 0.0),
                "withdrawnBalance": balance_data.get('withdrawnBalance', 0.0),
                "lastPayoutDate": balance_data.get('lastPayoutDate')
            }
        else:
            return {
                "totalEarned": 0.0,
                "pendingBalance": 0.0,
                "withdrawnBalance": 0.0,
                "lastPayoutDate": None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to get seller balance")
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/seller/transactions")
@limiter.limit("30/minute")
async def get_seller_transactions(authorization: str = Header(...), req: Request = None, limit: int = 50):
    """Get seller transaction history"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        id_token = authorization.split("Bearer ", 1)[1]
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token.get('uid')

        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not db or limit <= 0 or limit > 100:
            limit = 50

        # Get seller transactions
        transactions = []
        trans_docs = db.collection('users').document(user_id).collection('seller_transactions').order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()

        for doc in trans_docs:
            trans_data = doc.to_dict()
            trans_data["id"] = doc.id
            transactions.append(trans_data)

        return {"transactions": transactions, "count": len(transactions)}

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to get seller transactions")
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/seller/transactions/export")
@limiter.limit("5/minute")
async def export_seller_transactions(authorization: str = Header(...), format: str = "csv", req: Request = None):
    """Export seller transactions as CSV or PDF - limit 5 per minute per user"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Validate format
        if format.lower() not in ["csv", "pdf"]:
            raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

        id_token = authorization.split("Bearer ", 1)[1]
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token.get('uid')

        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get seller transactions (max 500)
        transactions = []
        trans_docs = db.collection('users').document(user_id).collection('seller_transactions').order_by("timestamp", direction=firestore.Query.DESCENDING).limit(500).stream()

        for doc in trans_docs:
            trans_data = doc.to_dict()
            trans_data["id"] = doc.id
            transactions.append(trans_data)

        if not transactions:
            raise HTTPException(status_code=404, detail="No transactions found")

        # Get seller profile for name
        user_doc = db.collection('users').document(user_id).get()
        seller_name = user_doc.get('displayName', 'Seller') if user_doc.exists else 'Seller'
        seller_email = user_doc.get('email') if user_doc.exists else 'unknown'

        # Prepare data for export
        export_data = []
        for trans in transactions:
            timestamp = trans.get('timestamp')
            if timestamp:
                timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp)
            else:
                timestamp_str = 'Unknown'

            export_data.append({
                'Date': timestamp_str,
                'Video ID': trans.get('videoId', 'N/A'),
                'Buyer ID': trans.get('buyerId', 'N/A'),
                'Amount (€)': f"{trans.get('amount', 0):.2f}",
                'Status': trans.get('status', 'Unknown').upper()
            })

        if format.lower() == "csv":
            # Export as CSV
            df = pd.DataFrame(export_data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()

            filename = f"transactions_{seller_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            return StreamingResponse(
                iter([csv_content]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        else:  # PDF format
            # Export as PDF
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

            # Build content
            elements = []
            styles = getSampleStyleSheet()

            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=6,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph("Transaction History Report", title_style))

            # Subtitle
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#666666'),
                spaceAfter=12
            )
            elements.append(Paragraph(f"Seller: {seller_name} | Email: {seller_email}", subtitle_style))
            elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", subtitle_style))
            elements.append(Spacer(1, 0.3*inch))

            # Summary
            total_amount = sum(float(item['Amount (€)']) for item in export_data)
            summary_style = ParagraphStyle(
                'Summary',
                parent=styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor('#333333'),
                spaceAfter=6,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph(f"Total Transactions: {len(export_data)} | Total Amount: €{total_amount:.2f}", summary_style))
            elements.append(Spacer(1, 0.2*inch))

            # Table
            table_data = [['Date', 'Video ID', 'Buyer ID', 'Amount (€)', 'Status']]
            for item in export_data:
                table_data.append([
                    item['Date'],
                    item['Video ID'][:12] + '...' if len(item['Video ID']) > 12 else item['Video ID'],
                    item['Buyer ID'][:12] + '...' if len(item['Buyer ID']) > 12 else item['Buyer ID'],
                    item['Amount (€)'],
                    item['Status']
                ])

            table = Table(table_data, colWidths=[1.3*inch, 1.2*inch, 1.2*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(table)

            # Footer
            elements.append(Spacer(1, 0.3*inch))
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#999999'),
                alignment='center'
            )
            elements.append(Paragraph("This is an official transaction report. Keep this for your records.", footer_style))

            # Build PDF
            doc.build(elements)
            pdf_buffer.seek(0)

            filename = f"transactions_{seller_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            return StreamingResponse(
                iter([pdf_buffer.getvalue()]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export transactions")

@app.post("/seller/payout-request")
@limiter.limit("10/minute")
async def create_payout_request(request: PayoutRequestRequest, authorization: str = Header(...), req: Request = None):
    """Request a payout/withdrawal of seller earnings"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        id_token = authorization.split("Bearer ", 1)[1]
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token.get('uid')

        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Check if seller is suspended
        seller_profile_ref = db.collection('users').document(user_id).collection('seller_profile').document('profile')
        seller_profile_doc = seller_profile_ref.get()

        if seller_profile_doc.exists:
            seller_status = seller_profile_doc.to_dict().get('status', 'unverified')
            if seller_status == 'suspended':
                raise HTTPException(status_code=403, detail="Your seller account is suspended and cannot request payouts")

        # Get current balance
        balance_ref = db.collection('users').document(user_id).collection('seller_balance').document('current')
        balance_doc = balance_ref.get()

        if not balance_doc.exists:
            raise HTTPException(status_code=400, detail="No balance found")

        balance_data = balance_doc.to_dict()
        pending_balance = balance_data.get('pendingBalance', 0.0)

        # Validate amount
        if request.amount > pending_balance:
            raise HTTPException(status_code=400, detail="Insufficient pending balance")

        # Get PayPal email from profile
        seller_profile_ref = db.collection('users').document(user_id).collection('seller_profile').document('settings')
        seller_profile_doc = seller_profile_ref.get()

        if not seller_profile_doc.exists or not seller_profile_doc.to_dict().get('paypalEmail'):
            raise HTTPException(status_code=400, detail="PayPal email not configured")

        paypal_email = seller_profile_doc.to_dict().get('paypalEmail')

        # Create payout request
        payout_ref = db.collection('users').document(user_id).collection('payout_requests').document()
        payout_id = payout_ref.id

        payout_ref.set({
            "amount": request.amount,
            "paypalEmail": paypal_email,
            "status": "pending",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "userId": user_id
        })

        logger.info(f"Payout request created: {payout_id}")
        return {
            "payoutId": payout_id,
            "amount": request.amount,
            "status": "pending",
            "message": "Payout request created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create payout request")
        raise HTTPException(status_code=500, detail="Failed to create payout request")

@app.get("/seller/payout-requests")
@limiter.limit("30/minute")
async def get_payout_requests(authorization: str = Header(...), req: Request = None):
    """Get seller payout request history"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        id_token = authorization.split("Bearer ", 1)[1]
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token.get('uid')

        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get payout requests
        payouts = []
        payout_docs = db.collection('users').document(user_id).collection('payout_requests').order_by("createdAt", direction=firestore.Query.DESCENDING).limit(100).stream()

        for doc in payout_docs:
            payout_data = doc.to_dict()
            payout_data["id"] = doc.id
            payouts.append(payout_data)

        return {"payouts": payouts, "count": len(payouts)}

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to get payout requests")
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/seller/withdrawal-request-notification")
@limiter.limit("10/minute")
async def send_withdrawal_notification(authorization: str = Header(...), req: Request = None):
    """Send email notification to admin when a withdrawal request is created"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Parse request body
        body = await req.json()
        request_id = body.get('requestId')
        amount = body.get('amount')
        paypal_email = body.get('paypalEmail')

        if not request_id or not amount or not paypal_email:
            raise HTTPException(status_code=400, detail="Missing required fields: requestId, amount, paypalEmail")

        # Verify user token
        id_token = authorization.split("Bearer ", 1)[1]
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token.get('uid')

        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get user details
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        user_email = user_data.get('email', 'N/A')
        user_name = user_data.get('displayName', user_data.get('email', 'Unknown Seller'))

        # Get admin email from environment variable
        admin_email = os.getenv("ADMIN_EMAIL")
        if not admin_email:
            logger.warning("ADMIN_EMAIL not configured - withdrawal notification not sent")
            return {"success": True, "message": "Notification skipped - admin email not configured"}

        # Generate email HTML
        email_html = get_new_withdrawal_request_email(
            seller_name=user_name,
            seller_email=user_email,
            amount=float(amount),
            paypal_email=paypal_email,
            seller_id=user_id,
            request_id=request_id
        )

        # Send email to admin
        email_sent = send_email(
            to_email=admin_email,
            subject=f"💰 New Withdrawal Request - €{amount:.2f} from {user_name}",
            html_content=email_html
        )

        if email_sent:
            logger.info(f"Withdrawal notification email sent for request {request_id}")
            return {"success": True, "message": "Notification sent successfully"}
        else:
            logger.warning(f"Failed to send withdrawal notification for request {request_id}")
            return {"success": False, "message": "Failed to send notification"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send withdrawal notification: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send notification")

# ========================
# === ADMIN ENDPOINTS ===
# ========================
@app.get("/admin/stats", dependencies=[admin_dependency])
async def get_admin_stats():
    users_collection = db.collection('users').stream()
    return {"userCount": len(list(users_collection))}

@app.get("/admin/users", dependencies=[admin_dependency])
async def get_all_users():
    users_list = []
    users_docs = db.collection('users').stream()
    for user in users_docs:
        user_data = user.to_dict()
        users_list.append({ "id": user.id, "email": user_data.get("email"), "plan": user_data.get("activePlan", "Starter Plan"), "generationCount": 0 })
    return users_list

@app.post("/admin/users", dependencies=[admin_dependency])
async def create_user_account(request: AdminUserCreateRequest):
    """Create a new user account - admin only"""
    try:
        # Create Firebase Auth user
        user = auth.create_user(email=request.email, password=request.password)

        # Initialize Firestore user document
        db.collection('users').document(user.uid).set({
            "email": user.email,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "credits": 10,
            "activePlan": "Starter",
            "banned": False,
            "suspended": False
        })

        logger.info("Admin created new user account")
        return {"message": "User created successfully", "uid": user.uid}

    except auth.EmailAlreadyExistsError:
        logger.warning("Attempt to create user with existing email")
        raise HTTPException(status_code=400, detail="Email already in use")
    except auth.InvalidPasswordError:
        raise HTTPException(status_code=400, detail="Password does not meet requirements")
    except Exception as e:
        logger.error("Failed to create user account")
        raise HTTPException(status_code=400, detail="Failed to create user account")

@app.get("/admin/users/{user_id}", dependencies=[admin_dependency])
async def get_user_details(user_id: str):
    """Get user profile and transaction history - admin only"""
    try:
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        # Get transactions
        transactions = []
        try:
            trans_docs = db.collection('users').document(user_id).collection('payments').order_by("createdAt", direction=firestore.Query.DESCENDING).limit(100).stream()
            for doc in trans_docs:
                trans_data = doc.to_dict()
                trans_data["id"] = doc.id
                if 'createdAt' in trans_data and trans_data['createdAt']:
                    trans_data['createdAt'] = trans_data['createdAt'].strftime('%d/%m/%Y')
                transactions.append(trans_data)
        except Exception as e:
            logger.warning("Failed to fetch transactions for user")

        user_profile = user_doc.to_dict()
        user_profile['name'] = user_profile.get('name', user_profile.get('email', ''))
        return {"profile": user_profile, "transactions": transactions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user details")
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

@app.put("/admin/users/{user_id}", dependencies=[admin_dependency])
async def update_user_details(user_id: str, request: AdminUserUpdateRequest):
    """Update user profile - admin only"""
    try:
        # Update Firebase Auth if email changed
        if request.email:
            auth.update_user(user_id, email=request.email)

        # Update Firestore
        update_data = {}
        if request.email:
            update_data['email'] = request.email
        if request.name:
            update_data['name'] = request.name

        if update_data:
            db.collection('users').document(user_id).update(update_data)

        logger.info("Admin updated user details")
        return {"message": "User updated successfully"}

    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except auth.InvalidEmailError:
        raise HTTPException(status_code=400, detail="Invalid email address")
    except Exception as e:
        logger.error("Failed to update user details")
        raise HTTPException(status_code=500, detail="Failed to update user")

@app.put("/admin/users/{user_id}/billing", dependencies=[admin_dependency])
async def update_billing_info(user_id: str, request: AdminBillingUpdateRequest):
    """Update user billing information - admin only"""
    try:
        db.collection('users').document(user_id).update({"billingInfo": request.dict()})
        logger.info("Admin updated billing information")
        return {"message": "Billing information updated successfully"}

    except Exception as e:
        logger.error("Failed to update billing information")
        raise HTTPException(status_code=500, detail="Failed to update billing information")

@app.post("/admin/users/{user_id}/gift-credits", dependencies=[admin_dependency])
async def gift_user_credits(user_id: str, request: AdminCreditRequest):
    """Gift credits to user - admin only"""
    try:
        if request.amount <= 0 or request.amount > 100000:
            raise HTTPException(status_code=400, detail="Credit amount must be between 1 and 100000")

        db.collection('users').document(user_id).update({"credits": firestore.Increment(request.amount)})
        logger.info(f"Admin gifted {request.amount} credits")
        return {"message": f"{request.amount} credits gifted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to gift credits")
        raise HTTPException(status_code=500, detail="Failed to gift credits")

@app.post("/admin/transactions/{user_id}", dependencies=[admin_dependency])
async def add_transaction(user_id: str, request: AdminTransactionRequest):
    """Add transaction record - admin only"""
    try:
        trans_date = datetime.strptime(request.date, '%d/%m/%Y')
        db.collection('users').document(user_id).collection('payments').add({
            "createdAt": trans_date,
            "amount": request.amount,
            "type": request.type,
            "status": request.status
        })
        logger.info("Admin added transaction")
        return {"message": "Transaction added successfully"}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use DD/MM/YYYY")
    except Exception as e:
        logger.error("Failed to add transaction")
        raise HTTPException(status_code=500, detail="Failed to add transaction")

@app.put("/admin/transactions/{user_id}/{trans_id}", dependencies=[admin_dependency])
async def update_transaction(user_id: str, trans_id: str, request: AdminTransactionRequest):
    """Update transaction record - admin only"""
    try:
        trans_date = datetime.strptime(request.date, '%d/%m/%Y')
        trans_ref = db.collection('users').document(user_id).collection('payments').document(trans_id)
        trans_ref.update({
            "createdAt": trans_date,
            "amount": request.amount,
            "type": request.type,
            "status": request.status
        })
        logger.info("Admin updated transaction")
        return {"message": "Transaction updated successfully"}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use DD/MM/YYYY")
    except Exception as e:
        logger.error("Failed to update transaction")
        raise HTTPException(status_code=500, detail="Failed to update transaction")

@app.delete("/admin/transactions/{user_id}/{trans_id}", dependencies=[admin_dependency])
async def delete_transaction(user_id: str, trans_id: str):
    """Delete transaction record - admin only"""
    try:
        db.collection('users').document(user_id).collection('payments').document(trans_id).delete()
        logger.info("Admin deleted transaction")
        return {"message": "Transaction deleted successfully"}

    except Exception as e:
        logger.error("Failed to delete transaction")
        raise HTTPException(status_code=500, detail="Failed to delete transaction")

@app.post("/admin/users/{user_id}/reset-password", dependencies=[admin_dependency])
async def reset_user_password(user_id: str, request: dict):
    """Reset a user's password - admin only"""
    new_password = request.get("newPassword")

    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if len(new_password) > 255:
        raise HTTPException(status_code=400, detail="Password too long")

    try:
        auth.update_user(user_id, password=new_password)
        logger.info("Admin reset user password")
        return {"message": "Password reset successfully"}

    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except auth.InvalidPasswordError:
        raise HTTPException(status_code=400, detail="Password does not meet requirements")
    except Exception as e:
        logger.error("Failed to reset password")
        raise HTTPException(status_code=500, detail="Failed to reset password")

# --- Payout Management Endpoints (Admin) ---

@app.get("/admin/payouts/queue", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_payout_queue(req: Request = None):
    """Get pending payout requests - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get all pending payout requests
        pending_payouts = []
        payout_docs = db.collection_group('payout_requests').where('status', '==', 'pending').limit(100).stream()

        for doc in payout_docs:
            payout_data = doc.to_dict()
            payout_data["id"] = doc.id
            payout_data["docPath"] = doc.reference.path
            pending_payouts.append(payout_data)

        return {
            "payouts": pending_payouts,
            "count": len(pending_payouts)
        }

    except Exception as e:
        logger.error("Failed to get payout queue")
        raise HTTPException(status_code=500, detail="Failed to fetch payouts")

@app.post("/admin/payouts/{payout_id}/approve", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def approve_payout(payout_id: str, user_id: str, req: Request = None):
    """Approve payout request - admin only - triggers PayPal transfer"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get payout request
        payout_ref = db.collection('users').document(user_id).collection('payout_requests').document(payout_id)
        payout_doc = payout_ref.get()

        if not payout_doc.exists:
            raise HTTPException(status_code=404, detail="Payout request not found")

        payout_data = payout_doc.to_dict()

        if payout_data.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Payout is not pending")

        payout_amount = payout_data.get('amount', 0.0)
        paypal_email = payout_data.get('paypalEmail')

        # In a real implementation, trigger PayPal transfer here
        # For now, we'll mark as approved and create a record
        # TODO: Integrate with PayPal API to actually transfer funds

        # Update payout status to approved
        payout_ref.update({
            "status": "approved",
            "approvedAt": firestore.SERVER_TIMESTAMP,
            "approvedBy": user_id
        })

        # Deduct from pending balance
        balance_ref = db.collection('users').document(user_id).collection('seller_balance').document('current')
        balance_ref.update({
            "pendingBalance": firestore.Increment(-payout_amount),
            "lastPayoutDate": firestore.SERVER_TIMESTAMP
        })

        # Send notification email to seller
        try:
            user_doc = db.collection('users').document(user_id).get()
            seller_email = user_doc.get('email') if user_doc.exists else paypal_email
            seller_name = user_doc.get('displayName', 'Seller') if user_doc.exists else 'Seller'
            send_payout_notification(seller_email, 'approved', payout_amount, seller_name)
        except Exception as e:
            logger.warning(f"Failed to send payout approval email: {str(e)}")

        # Send notification to admin
        try:
            admin_subject = f"[ACTION] Payout Approved: €{payout_amount:.2f}"
            user_doc = db.collection('users').document(user_id).get()
            seller_name = user_doc.get('displayName', 'Seller') if user_doc.exists else 'Seller'
            admin_html = get_admin_email(seller_name, payout_amount, paypal_email, user_id)
            send_admin_notification(admin_subject, admin_html)
        except Exception as e:
            logger.warning(f"Failed to send admin notification: {str(e)}")

        logger.info(f"Payout approved: {payout_id} for {payout_amount} EUR")
        return {
            "message": "Payout approved successfully",
            "payoutId": payout_id,
            "amount": payout_amount,
            "status": "approved"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to approve payout")
        raise HTTPException(status_code=500, detail="Failed to approve payout")

@app.post("/admin/payouts/{payout_id}/reject", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def reject_payout(payout_id: str, user_id: str, req: Request = None):
    """Reject payout request - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get payout request
        payout_ref = db.collection('users').document(user_id).collection('payout_requests').document(payout_id)
        payout_doc = payout_ref.get()

        if not payout_doc.exists:
            raise HTTPException(status_code=404, detail="Payout request not found")

        payout_data = payout_doc.to_dict()

        if payout_data.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Payout is not pending")

        payout_amount = payout_data.get('amount', 0.0)
        paypal_email = payout_data.get('paypalEmail')

        # Update payout status to rejected
        payout_ref.update({
            "status": "rejected",
            "rejectedAt": firestore.SERVER_TIMESTAMP,
            "rejectedBy": user_id
        })

        # Send rejection notification email to seller
        try:
            user_doc = db.collection('users').document(user_id).get()
            seller_email = user_doc.get('email') if user_doc.exists else paypal_email
            seller_name = user_doc.get('displayName', 'Seller') if user_doc.exists else 'Seller'
            send_payout_notification(seller_email, 'rejected', payout_amount, seller_name)
        except Exception as e:
            logger.warning(f"Failed to send payout rejection email: {str(e)}")

        logger.info(f"Payout rejected: {payout_id}")
        return {
            "message": "Payout rejected successfully",
            "payoutId": payout_id,
            "status": "rejected"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reject payout")
        raise HTTPException(status_code=500, detail="Failed to reject payout")

@app.post("/admin/payouts/{payout_id}/complete", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def complete_payout(payout_id: str, user_id: str, req: Request = None):
    """Mark payout as completed after manual PayPal transfer - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get payout request
        payout_ref = db.collection('users').document(user_id).collection('payout_requests').document(payout_id)
        payout_doc = payout_ref.get()

        if not payout_doc.exists:
            raise HTTPException(status_code=404, detail="Payout request not found")

        payout_data = payout_doc.to_dict()

        if payout_data.get('status') != 'approved':
            raise HTTPException(status_code=400, detail="Only approved payouts can be completed")

        # Update payout status to completed
        payout_ref.update({
            "status": "completed",
            "completedAt": firestore.SERVER_TIMESTAMP,
            "completedBy": user_id
        })

        # Update withdrawn balance
        payout_amount = payout_data.get('amount', 0.0)
        paypal_email = payout_data.get('paypalEmail')
        balance_ref = db.collection('users').document(user_id).collection('seller_balance').document('current')
        balance_ref.update({
            "withdrawnBalance": firestore.Increment(payout_amount)
        })

        # Send completion notification email to seller
        try:
            user_doc = db.collection('users').document(user_id).get()
            seller_email = user_doc.get('email') if user_doc.exists else paypal_email
            seller_name = user_doc.get('displayName', 'Seller') if user_doc.exists else 'Seller'
            send_payout_notification(seller_email, 'completed', payout_amount, seller_name)
        except Exception as e:
            logger.warning(f"Failed to send payout completion email: {str(e)}")

        logger.info(f"Payout completed: {payout_id} for {payout_amount} EUR")
        return {
            "message": "Payout marked as completed successfully",
            "payoutId": payout_id,
            "amount": payout_amount,
            "status": "completed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to complete payout")
        raise HTTPException(status_code=500, detail="Failed to complete payout")

@app.get("/admin/payouts/history", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_payout_history(req: Request = None):
    """Get payout history (approved/completed/rejected) - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get all non-pending payout requests
        payouts = []
        payout_docs = db.collection_group('payout_requests').where('status', 'in', ['approved', 'completed', 'rejected']).limit(200).stream()

        for doc in payout_docs:
            payout_data = doc.to_dict()
            payout_data["id"] = doc.id
            payouts.append(payout_data)

        return {
            "payouts": payouts,
            "count": len(payouts)
        }

    except Exception as e:
        logger.error("Failed to get payout history")
        raise HTTPException(status_code=500, detail="Failed to fetch payout history")

@app.get("/admin/seller/{user_id}/earnings", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_seller_earnings(user_id: str, req: Request = None):
    """Get seller earnings summary - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get seller balance
        balance_ref = db.collection('users').document(user_id).collection('seller_balance').document('current')
        balance_doc = balance_ref.get()

        if not balance_doc.exists:
            return {
                "userId": user_id,
                "totalEarned": 0.0,
                "pendingBalance": 0.0,
                "withdrawnBalance": 0.0,
                "transactionCount": 0
            }

        balance_data = balance_doc.to_dict()

        # Get transaction count
        trans_docs = db.collection('users').document(user_id).collection('seller_transactions').stream()
        transaction_count = len(list(trans_docs))

        return {
            "userId": user_id,
            "totalEarned": balance_data.get('totalEarned', 0.0),
            "pendingBalance": balance_data.get('pendingBalance', 0.0),
            "withdrawnBalance": balance_data.get('withdrawnBalance', 0.0),
            "transactionCount": transaction_count,
            "lastPayoutDate": balance_data.get('lastPayoutDate')
        }

    except Exception as e:
        logger.error("Failed to get seller earnings")
        raise HTTPException(status_code=500, detail="Failed to fetch seller earnings")

@app.post("/admin/seller/{user_id}/verify", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def verify_seller(user_id: str, admin_id: str = Header(..., alias="X-Admin-ID"), req: Request = None):
    """Verify a seller account - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get seller profile
        profile_ref = db.collection('users').document(user_id).collection('seller_profile').document('profile')
        profile_doc = profile_ref.get()

        if not profile_doc.exists:
            # Create seller profile if it doesn't exist
            profile_ref.set({
                "status": "verified",
                "verificationDate": firestore.SERVER_TIMESTAMP,
                "verifiedBy": admin_id
            }, merge=True)
        else:
            # Update existing profile
            profile_ref.update({
                "status": "verified",
                "verificationDate": firestore.SERVER_TIMESTAMP,
                "verifiedBy": admin_id
            })

        logger.info(f"Seller {user_id} verified by admin {admin_id}")
        return {
            "message": "Seller verified successfully",
            "userId": user_id,
            "status": "verified"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify seller: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to verify seller")

@app.post("/admin/seller/{user_id}/suspend", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def suspend_seller(user_id: str, suspend_request: AdminSellerSuspendRequest, admin_id: str = Header(..., alias="X-Admin-ID"), req: Request = None):
    """Suspend a seller account - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get seller profile
        profile_ref = db.collection('users').document(user_id).collection('seller_profile').document('profile')
        profile_doc = profile_ref.get()

        if not profile_doc.exists:
            raise HTTPException(status_code=404, detail="Seller profile not found")

        # Update seller status to suspended
        profile_ref.update({
            "status": "suspended",
            "suspensionReason": suspend_request.reason,
            "suspendedBy": admin_id,
            "suspendedAt": firestore.SERVER_TIMESTAMP
        })

        # Send suspension notification email to seller
        try:
            user_doc = db.collection('users').document(user_id).get()
            seller_email = user_doc.get('email') if user_doc.exists else None
            seller_name = user_doc.get('displayName', 'Seller') if user_doc.exists else 'Seller'

            if seller_email:
                subject = "⚠️ Your Seller Account Has Been Suspended"
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 40px; border-radius: 8px;">
                        <div style="background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
                            <h1 style="margin: 0; font-size: 28px;">Account Suspended</h1>
                        </div>
                        <p>Hi {seller_name},</p>
                        <p>Your seller account has been suspended. This means you are temporarily unable to sell videos or request payouts.</p>
                        <div style="background-color: #fee2e2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; border-radius: 4px;">
                            <p style="margin: 0;"><strong>Reason:</strong> {suspend_request.reason}</p>
                        </div>
                        <p>If you believe this is a mistake or would like to appeal this decision, please contact our support team.</p>
                        <p>Thank you for your understanding.</p>
                        <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                            This is an automated message. Please do not reply to this email.
                        </p>
                    </div>
                </body>
                </html>
                """
                send_email(seller_email, subject, html_content)
        except Exception as e:
            logger.warning(f"Failed to send suspension email: {str(e)}")

        logger.info(f"Seller {user_id} suspended by admin {admin_id}. Reason: {suspend_request.reason}")
        return {
            "message": "Seller suspended successfully",
            "userId": user_id,
            "status": "suspended",
            "reason": suspend_request.reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to suspend seller: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to suspend seller")

@app.post("/admin/seller/{user_id}/unsuspend", dependencies=[admin_dependency])
@limiter.limit("10/minute")
async def unsuspend_seller(user_id: str, admin_id: str = Header(..., alias="X-Admin-ID"), req: Request = None):
    """Unsuspend a seller account - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Get seller profile
        profile_ref = db.collection('users').document(user_id).collection('seller_profile').document('profile')
        profile_doc = profile_ref.get()

        if not profile_doc.exists:
            raise HTTPException(status_code=404, detail="Seller profile not found")

        current_status = profile_doc.get('status')
        if current_status != 'suspended':
            raise HTTPException(status_code=400, detail="Seller is not suspended")

        # Update seller status to verified
        profile_ref.update({
            "status": "verified",
            "suspensionReason": firestore.DELETE_FIELD,
            "suspendedBy": firestore.DELETE_FIELD,
            "suspendedAt": firestore.DELETE_FIELD,
            "unsuspendedBy": admin_id,
            "unsuspendedAt": firestore.SERVER_TIMESTAMP
        })

        # Send reactivation notification email to seller
        try:
            user_doc = db.collection('users').document(user_id).get()
            seller_email = user_doc.get('email') if user_doc.exists else None
            seller_name = user_doc.get('displayName', 'Seller') if user_doc.exists else 'Seller'

            if seller_email:
                subject = "✅ Your Seller Account Has Been Reactivated"
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 40px; border-radius: 8px;">
                        <div style="background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
                            <h1 style="margin: 0; font-size: 28px;">Account Reactivated</h1>
                        </div>
                        <p>Hi {seller_name},</p>
                        <p>Great news! Your seller account has been reactivated. You can now resume selling videos and requesting payouts.</p>
                        <div style="background-color: #dcfce7; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 4px;">
                            <p style="margin: 0;"><strong>Status:</strong> Your account is now active and ready to use.</p>
                        </div>
                        <p>If you have any questions or need assistance, please don't hesitate to contact our support team.</p>
                        <p>Thank you for being part of our marketplace!</p>
                        <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                            This is an automated message. Please do not reply to this email.
                        </p>
                    </div>
                </body>
                </html>
                """
                send_email(seller_email, subject, html_content)
        except Exception as e:
            logger.warning(f"Failed to send reactivation email: {str(e)}")

        logger.info(f"Seller {user_id} unsuspended by admin {admin_id}")
        return {
            "message": "Seller unsuspended successfully",
            "userId": user_id,
            "status": "verified"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unsuspend seller: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to unsuspend seller")

@app.get("/admin/sellers", dependencies=[admin_dependency])
@limiter.limit("30/minute")
async def get_all_sellers(req: Request = None):
    """Get all sellers with their verification status - admin only"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        sellers = []
        # Get all users
        users = db.collection('users').stream()

        for user_doc in users:
            user_data = user_doc.to_dict()

            # Check if user has seller profile
            seller_profile_ref = db.collection('users').document(user_doc.id).collection('seller_profile').document('profile')
            seller_profile_doc = seller_profile_ref.get()

            if seller_profile_doc.exists:
                seller_data = seller_profile_doc.to_dict()
                sellers.append({
                    "userId": user_doc.id,
                    "email": user_data.get('email'),
                    "displayName": user_data.get('displayName', 'Unknown'),
                    "status": seller_data.get('status', 'unverified'),
                    "paypalEmail": seller_data.get('paypalEmail'),
                    "verificationDate": seller_data.get('verificationDate'),
                    "suspensionReason": seller_data.get('suspensionReason'),
                    "suspendedAt": seller_data.get('suspendedAt')
                })

        # Sort by verification date (newest first) or status (suspended first)
        sellers.sort(key=lambda x: (x['status'] == 'suspended', x['verificationDate']), reverse=True)

        return {
            "sellers": sellers,
            "count": len(sellers),
            "verified": sum(1 for s in sellers if s['status'] == 'verified'),
            "unverified": sum(1 for s in sellers if s['status'] == 'unverified'),
            "suspended": sum(1 for s in sellers if s['status'] == 'suspended')
        }

    except Exception as e:
        logger.error(f"Failed to get sellers: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch sellers")

# --- Main execution block ---
if __name__ == "__main__":
    import uvicorn

    # Verify critical environment variables
    required_env_vars = ["REPLICATE_API_TOKEN", "PAYTRUST_API_KEY", "FIREBASE_SERVICE_ACCOUNT_BASE64"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    port = int(os.environ.get("PORT", 8000))
    is_production = os.getenv("ENV") == "production"
    reload = not is_production

    logger.info(f"Starting application on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=reload)