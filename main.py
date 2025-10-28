import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# --- Initialization & Setup ---
load_dotenv()
app = FastAPI()

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "https://ai-video-generator-mvp.netlify.app",
    "http://localhost:3001",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    print("=== Starting Firebase Initialization ===")
    
    firebase_secret_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
    if not firebase_secret_base64:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 environment variable not found.")
    
    print(f"✓ Environment variable found (length: {len(firebase_secret_base64)})")
    
    try:
        decoded_secret = base64.b64decode(firebase_secret_base64).decode('utf-8')
        print("✓ Base64 decoding successful")
    except Exception as decode_error:
        raise ValueError(f"Failed to decode base64: {decode_error}")
    
    try:
        service_account_info = json.loads(decoded_secret)
        print(f"✓ JSON parsing successful (Project: {service_account_info.get('project_id', 'UNKNOWN')})")
    except Exception as json_error:
        raise ValueError(f"Failed to parse JSON: {json_error}")
    
    bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
    if not bucket_name:
        raise ValueError("FIREBASE_STORAGE_BUCKET env var not set.")
    print(f"✓ Storage bucket: {bucket_name}")
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})
        print("✓ Firebase Admin SDK initialized")
    
    db = firestore.client()
    print("✓ Firestore client ready")
    print("=== Firebase Initialization Complete ===")
    
except Exception as e:
    firebase_init_error = str(e)
    print(f"❌ CRITICAL ERROR during Firebase init: {e}")
    print(f"Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()

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

class AdminUserCreateRequest(BaseModel):
    email: str
    password: str

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
async def create_payment(request: PaymentRequest):
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
    
    # Prepare PayTrust payment request
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {PAYTRUST_API_KEY}"
    }
    
    payload = {
        "paymentType": "DEPOSIT",
        "amount": amount,
        "currency": "EUR",
        "returnUrl": f"https://ai-video-generator-mvp.netlify.app/payment/success?payment_id={payment_id}",
        "webhookUrl": f"{os.getenv('BACKEND_URL', 'https://your-backend-url.com')}/paytrust-webhook",
        "referenceId": f"payment_id={payment_id};user_id={request.userId}",
        "customer": {
            "referenceId": request.userId,
            "firstName": user_data.get("name", "").split()[0] if user_data.get("name") else "User",
            "lastName": user_data.get("name", "").split()[-1] if user_data.get("name") and len(user_data.get("name", "").split()) > 1 else "Customer",
            "email": user_data.get("email", "customer@example.com")
        },
        "paymentMethod": "BASIC_CARD"
    }
    
    try:
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers)
        response.raise_for_status()
        payment_data = response.json()
        
        # Update payment record with PayTrust payment ID
        payment_ref.update({
            "paytrustPaymentId": payment_data.get("id"),
            "paytrustTransactionId": payment_data.get("transactionId")
        })
        
        # PayTrust returns the payment URL in the redirectUrl field
        return {"paymentUrl": payment_data.get("redirectUrl")}
    except requests.exceptions.RequestException as e:
        print(f"PayTrust API Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create payment: {str(e)}")

@app.post("/create-subscription")
async def create_subscription(request: SubscriptionRequest):
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
    
    payload = {
        "paymentType": "DEPOSIT",
        "amount": amount,
        "currency": "EUR",
        "returnUrl": f"https://ai-video-generator-mvp.netlify.app/payment/success?subscription_id={subscription_id}",
        "webhookUrl": f"{os.getenv('BACKEND_URL', 'https://your-backend-url.com')}/paytrust-webhook",
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
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers)
        response.raise_for_status()
        payment_data = response.json()
        
        # Update subscription record with PayTrust IDs
        subscription_ref.update({
            "paytrustPaymentId": payment_data.get("id"),
            "paytrustTransactionId": payment_data.get("transactionId")
        })
        
        return {"paymentUrl": payment_data.get("redirectUrl")}
    except requests.exceptions.RequestException as e:
        print(f"PayTrust API Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create subscription: {str(e)}")

@app.post("/paytrust-webhook")
async def paytrust_webhook(request: Request):
    """
    Handle webhook notifications from PayTrust
    PayTrust sends notifications for payment events like:
    - Payment successful
    - Payment failed
    - Subscription payment (recurring)
    - Refunds
    """
    try:
        body = await request.body()
        payload = json.loads(body)
        
        print(f"PayTrust Webhook received: {json.dumps(payload, indent=2)}")
        
        # Extract event data
        event_type = payload.get("type")
        state = payload.get("state")
        transaction_id = payload.get("transactionId")
        payment_id = payload.get("id")
        reference_id = payload.get("referenceId", "")
        amount = payload.get("amount")
        
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
        
        if not user_id:
            print("Warning: No user_id in webhook payload")
            return {"status": "received", "warning": "No user_id found"}
        
        user_ref = db.collection('users').document(user_id)
        
        # Handle different payment states
        if state == "SUCCESS":
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
                    if sub_ref.get().exists:
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
                    "paytrustTransactionId": transaction_id
                })
                
                print(f"Subscription payment successful for user {user_id}. Added {credits_to_add} credits.")
            
            elif payment_doc_id:
                # This is a one-time payment
                payment_ref = user_ref.collection('payments').document(payment_doc_id)
                payment_doc = payment_ref.get()
                
                if payment_doc.exists:
                    payment_data = payment_doc.to_dict()
                    credits_to_add = payment_data.get("creditsPurchased", 0)
                    
                    # Update payment status
                    payment_ref.update({
                        "status": "paid",
                        "paidAt": firestore.SERVER_TIMESTAMP,
                        "paytrustTransactionId": transaction_id
                    })
                    
                    # Add credits to user
                    user_ref.update({
                        "credits": firestore.Increment(credits_to_add)
                    })
                    
                    print(f"One-time payment successful for user {user_id}. Added {credits_to_add} credits.")
                else:
                    print(f"Warning: Payment document {payment_doc_id} not found")
        
        elif state == "FAIL" or state == "DECLINED":
            # Handle failed payments
            if payment_doc_id:
                payment_ref = user_ref.collection('payments').document(payment_doc_id)
                if payment_ref.get().exists:
                    payment_ref.update({
                        "status": "failed",
                        "failedAt": firestore.SERVER_TIMESTAMP
                    })
            
            if subscription_doc_id:
                sub_ref = user_ref.collection('subscriptions').document(subscription_doc_id)
                if sub_ref.get().exists:
                    sub_ref.update({
                        "status": "failed",
                        "failedAt": firestore.SERVER_TIMESTAMP
                    })
            
            print(f"Payment failed for user {user_id}")
        
        elif state == "PENDING":
            # Payment is still processing
            print(f"Payment pending for user {user_id}")
        
        return {"status": "received"}
    
    except Exception as e:
        print(f"Webhook processing error: {e}")
        # Return 200 even on errors to prevent PayTrust from retrying
        return {"status": "error", "message": str(e)}

@app.get("/payment-status/{payment_id}")
async def check_payment_status(payment_id: str, user_id: str):
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

@app.post("/generate-video")
async def generate_media(request: VideoRequest):
    if not db: raise HTTPException(status_code=500, detail="Firestore database not initialized.")
    user_ref = db.collection('users').document(request.user_id)
    model_string = REPLICATE_MODELS.get(request.model_id)
    if not model_string: raise HTTPException(status_code=400, detail="Invalid model ID provided.")
    try:
        user_doc = user_ref.get()
        if not user_doc.exists or user_doc.to_dict().get('credits', 0) <= 0:
            raise HTTPException(status_code=403, detail="User not found or has insufficient credits.")
        user_ref.update({'credits': firestore.Increment(-1)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to manage credits: {e}")
    try:
        api_params = request.params.copy()
        image_param_name = MODEL_IMAGE_PARAMS.get(request.model_id)
        if image_param_name and image_param_name in api_params:
            image_data = api_params.get(image_param_name)
            if image_data and isinstance(image_data, str) and image_data.startswith("data:image"):
                _header, encoded_data = image_data.split(",", 1)
                api_params[image_param_name] = io.BytesIO(base64.b64decode(encoded_data))
            else:
                api_params.pop(image_param_name, None)
        replicate_output = replicate.run(model_string, input=api_params)
        processed_output = str(replicate_output) if isinstance(replicate_output, FileOutput) else replicate_output
        if isinstance(processed_output, str):
            return {"output_urls": [processed_output]}
        elif isinstance(processed_output, list):
            return {"output_urls": [str(item) for item in processed_output]}
        else:
            raise TypeError("Unexpected model output format.")
    except Exception as e:
        print(f"Replicate task failed for user {request.user_id}. Refunding credit. Error: {e}")
        try: user_ref.update({'credits': firestore.Increment(1)})
        except Exception as refund_e: print(f"CRITICAL: FAILED TO REFUND CREDIT for user {request.user_id}. Error: {refund_e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

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
    try:
        user = auth.create_user(email=request.email, password=request.password)
        db.collection('users').document(user.uid).set({ "email": user.email, "createdAt": firestore.SERVER_TIMESTAMP, "credits": 10, "activePlan": "Starter" })
        return {"message": "User created successfully", "uid": user.uid}
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/users/{user_id}", dependencies=[admin_dependency])
async def get_user_details(user_id: str):
    user_doc = db.collection('users').document(user_id).get()
    if not user_doc.exists: raise HTTPException(status_code=404, detail="User not found")
    transactions = []
    trans_docs = db.collection('users').document(user_id).collection('payments').order_by("createdAt", direction=firestore.Query.DESCENDING).stream()
    for doc in trans_docs:
        trans_data = doc.to_dict()
        trans_data["id"] = doc.id
        if 'createdAt' in trans_data and trans_data['createdAt']: trans_data['createdAt'] = trans_data['createdAt'].strftime('%d/%m/%Y')
        transactions.append(trans_data)
    user_profile = user_doc.to_dict()
    user_profile['name'] = user_profile.get('name', user_profile.get('email', ''))
    return {"profile": user_profile, "transactions": transactions}

@app.put("/admin/users/{user_id}", dependencies=[admin_dependency])
async def update_user_details(user_id: str, request: AdminUserUpdateRequest):
    auth.update_user(user_id, email=request.email, display_name=request.name)
    db.collection('users').document(user_id).update({"email": request.email, "name": request.name})
    return {"message": "User updated successfully"}

@app.put("/admin/users/{user_id}/billing", dependencies=[admin_dependency])
async def update_billing_info(user_id: str, request: AdminBillingUpdateRequest):
    db.collection('users').document(user_id).update({"billingInfo": request.dict()})
    return {"message": "Billing information updated successfully."}

@app.post("/admin/users/{user_id}/gift-credits", dependencies=[admin_dependency])
async def gift_user_credits(user_id: str, request: AdminCreditRequest):
    db.collection('users').document(user_id).update({"credits": firestore.Increment(request.amount)})
    return {"message": f"{request.amount} credits gifted successfully"}

@app.post("/admin/transactions/{user_id}", dependencies=[admin_dependency])
async def add_transaction(user_id: str, request: AdminTransactionRequest):
    trans_date = datetime.strptime(request.date, '%d/%m/%Y')
    db.collection('users').document(user_id).collection('payments').add({ "createdAt": trans_date, "amount": request.amount, "type": request.type, "status": request.status })
    return {"message": "Transaction added successfully"}

@app.put("/admin/transactions/{user_id}/{trans_id}", dependencies=[admin_dependency])
async def update_transaction(user_id: str, trans_id: str, request: AdminTransactionRequest):
    trans_ref = db.collection('users').document(user_id).collection('payments').document(trans_id)
    trans_date = datetime.strptime(request.date, '%d/%m/%Y')
    trans_ref.update({ "createdAt": trans_date, "amount": request.amount, "type": request.type, "status": request.status })
    return {"message": "Transaction updated successfully"}

@app.delete("/admin/transactions/{user_id}/{trans_id}", dependencies=[admin_dependency])
async def delete_transaction(user_id: str, trans_id: str):
    db.collection('users').document(user_id).collection('payments').document(trans_id).delete()
    return {"message": "Transaction deleted successfully"}

# --- Main execution block ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    if not os.getenv("REPLICATE_API_TOKEN"): print("CRITICAL ERROR: REPLICATE_API_TOKEN not set.")
    else: uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
