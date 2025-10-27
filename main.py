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
    "http://localhost:3000", # Main App (Local)
    "https://ai-video-generator-mvp.netlify.app", # Main App (Deployed)
    "http://localhost:3001", # Admin App (Local)
 "https://reelzila-admin.netlify.app"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Paytrust Secrets ---
PAYTRUST_API_KEY = os.getenv("PAYTRUST_API_KEY")
PAYTRUST_SIGNING_KEY = os.getenv("PAYTRUST_SIGNING_KEY")
PAYTRUST_API_URL = "https://api.paytrust.com/v1"

# --- Firebase Admin SDK Setup ---
db = None
try:
    firebase_secret_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
    if not firebase_secret_base64: raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 environment variable not found.")
    decoded_secret = base64.b64decode(firebase_secret_base64).decode('utf-8')
    service_account_info = json.loads(decoded_secret)
    bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
    if not bucket_name: raise ValueError("FIREBASE_STORAGE_BUCKET env var not set.")
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})
    db = firestore.client()
except Exception as e:
    print(f"CRITICAL ERROR during Firebase init: {e}")

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

@app.post("/create-payment")
async def create_payment(request: PaymentRequest):
    if not db: raise HTTPException(status_code=500, detail="Database not initialized.")
    user_ref = db.collection('users').document(request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists: raise HTTPException(status_code=404, detail="User not found.")
    user_data = user_doc.to_dict()

    if not request.customAmount or request.customAmount <= 0:
        raise HTTPException(status_code=400, detail="Invalid custom amount.")
    
    amount = request.customAmount * 100
    credits_to_add = request.customAmount * 10
    description = f"{credits_to_add} Credits Purchase"

    payment_ref = user_ref.collection('payments').document()
    payment_ref.set({
        "amount": amount / 100, "creditsPurchased": credits_to_add,
        "createdAt": firestore.SERVER_TIMESTAMP, "status": "pending", "type": "Purchase"
    })
    
    headers = {"Authorization": f"Bearer {PAYTRUST_API_KEY}"}
    payload = {
        "amount": amount, "currency": "eur",
        "customer": {"email": user_data.get("email"), "name": user_data.get("name", "Valued Customer")},
        "redirect_url": "https://ai-video-generator-mvp.netlify.app/payment/success",
        "cancel_url": "https://ai-video-generator-mvp.netlify.app/payment/cancel",
        "metadata": { "internal_payment_id": payment_ref.id, "user_id": request.userId }
    }
    try:
        response = requests.post(f"{PAYTRUST_API_URL}/payments", json=payload, headers=headers)
        response.raise_for_status()
        payment_data = response.json()
        payment_ref.update({"paymentGatewayId": payment_data.get("id")})
        return {"paymentUrl": payment_data.get("redirect_url")}
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to create payment session: {e}")

@app.post("/create-subscription")
async def create_subscription(request: SubscriptionRequest):
    if not db: raise HTTPException(status_code=500, detail="Database not initialized.")
    user_ref = db.collection('users').document(request.userId)
    user_doc = user_ref.get()
    if not user_doc.exists: raise HTTPException(status_code=404, detail="User not found.")
    user_data = user_doc.to_dict()

    headers = {"Authorization": f"Bearer {PAYTRUST_API_KEY}"}
    payload = {
        "customer": {"email": user_data.get("email")},
        "items": [{"price": request.priceId}],
        "payment_behavior": "default_incomplete", "expand": ["latest_invoice.payment_intent"],
        "metadata": { "user_id": request.userId }
    }
    try:
        response = requests.post(f"{PAYTRUST_API_URL}/subscriptions", json=payload, headers=headers)
        response.raise_for_status()
        subscription_data = response.json()
        client_secret = subscription_data['latest_invoice']['payment_intent']['client_secret']
        
        user_ref.update({
            "subscriptionId": subscription_data.get("id"),
            "subscriptionStatus": subscription_data.get("status"),
            "activePlan": "Pro"
        })
        return {"clientSecret": client_secret, "subscriptionId": subscription_data.get("id")}
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to create subscription: {e}")

@app.post("/paytrust-webhook")
async def paytrust_webhook(request: Request, paytrust_signature: str = Header(None)):
    if not PAYTRUST_SIGNING_KEY: raise HTTPException(status_code=500, detail="Signing key not configured.")
    body = await request.body()
    expected_signature = hmac.new(key=PAYTRUST_SIGNING_KEY.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, paytrust_signature):
        raise HTTPException(status_code=400, detail="Invalid signature.")

    payload = json.loads(body)
    event_type = payload.get("event")
    data = payload.get("data", {}).get("object", {})
    
    if event_type == "invoice.payment_succeeded":
        subscription_id = data.get("subscription")
        if subscription_id:
            users_query = db.collection('users').where('subscriptionId', '==', subscription_id).limit(1).stream()
            user_doc = next(users_query, None)
            if user_doc:
                user_ref = user_doc.reference
                user_ref.update({"credits": firestore.Increment(250)})
                print(f"Subscription payment successful for user {user_doc.id}. Pro credits added.")
    
    elif event_type in ["payment.succeeded", "payment.failed"]:
        metadata = data.get("metadata", {})
        internal_payment_id = metadata.get("internal_payment_id")
        user_id = metadata.get("user_id")
        if internal_payment_id and user_id:
            payment_ref = db.collection('users').document(user_id).collection('payments').document(internal_payment_id)
            if event_type == "payment.succeeded":
                payment_data = payment_ref.get().to_dict()
                payment_ref.update({"status": "paid"})
                user_ref = db.collection('users').document(user_id)
                user_ref.update({"credits": firestore.Increment(payment_data.get("creditsPurchased", 0))})
                print(f"One-time payment successful for user {user_id}. Credits added.")
            else:
                payment_ref.update({"status": "failed"})
                print(f"One-time payment failed for user {user_id}.")

    return {"status": "received"}

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
