import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
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

# --- Initialization & Setup ---
load_dotenv()
app = FastAPI()

# --- CORS Middleware ---
origins = [
    "http://localhost:3000", # Main App (Local)
    "https://ai-video-generator-mvp.netlify.app", # Main App (Deployed)
    "http://localhost:3001", # Admin App (Local)
    "https://reelzila-admin.netlify.app"
    # "https://your-admin-app.netlify.app", # Admin App (Deployed) - Add this when ready
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Firebase Admin SDK Setup (Railway Compatible) ---
db = None
try:
    firebase_secret_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
    if not firebase_secret_base64:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 environment variable not found.")
    decoded_secret = base64.b64decode(firebase_secret_base64).decode('utf-8')
    service_account_info = json.loads(decoded_secret)
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"CRITICAL ERROR during Firebase init: {e}")

# --- Pydantic Models ---
class VideoRequest(BaseModel):
    user_id: str
    model_id: str
    params: Dict[str, Any]

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
        try:
            user_ref.update({'credits': firestore.Increment(1)})
        except Exception as refund_e:
            print(f"CRITICAL: FAILED TO REFUND CREDIT for user {request.user_id}. Error: {refund_e}")
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
        users_list.append({
            "id": user.id,
            "email": user_data.get("email"),
            "plan": user_data.get("activePlan", "Starter Plan"),
            "generationCount": 0 # Placeholder: Calculating this is a heavy operation
        })
    return users_list

@app.post("/admin/users", dependencies=[admin_dependency])
async def create_user_account(request: AdminUserCreateRequest):
    try:
        user = auth.create_user(email=request.email, password=request.password)
        db.collection('users').document(user.uid).set({
            "email": user.email,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "credits": 10,
            "activePlan": "Starter"
        })
        return {"message": "User created successfully", "uid": user.uid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/users/{user_id}", dependencies=[admin_dependency])
async def get_user_details(user_id: str):
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
    db.collection('users').document(user_id).collection('payments').add({
        "createdAt": trans_date,
        "amount": request.amount,
        "type": request.type,
        "status": request.status
    })
    return {"message": "Transaction added successfully"}

@app.put("/admin/transactions/{user_id}/{trans_id}", dependencies=[admin_dependency])
async def update_transaction(user_id: str, trans_id: str, request: AdminTransactionRequest):
    trans_ref = db.collection('users').document(user_id).collection('payments').document(trans_id)
    trans_date = datetime.strptime(request.date, '%d/%m/%Y')
    trans_ref.update({
        "createdAt": trans_date,
        "amount": request.amount,
        "type": request.type,
        "status": request.status
    })
    return {"message": "Transaction updated successfully"}

@app.delete("/admin/transactions/{user_id}/{trans_id}", dependencies=[admin_dependency])
async def delete_transaction(user_id: str, trans_id: str):
    db.collection('users').document(user_id).collection('payments').document(trans_id).delete()
    return {"message": "Transaction deleted successfully"}

# --- Main execution block ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    if not os.getenv("REPLICATE_API_TOKEN"):
        print("CRITICAL ERROR: REPLICATE_API_TOKEN environment variable not set.")
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
