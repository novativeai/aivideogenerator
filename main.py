import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import replicate
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict, Any, List

# --- Imports for handling environment variables and file conversion ---
import base64
import json
import io

from replicate.helpers import FileOutput

# --- Initialization ---
# This loads your local .env file for testing. On Railway, it does nothing.
load_dotenv()
app = FastAPI()

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://localhost:8081",
    "https://ai-video-generator-mvp.netlify.app"
    # IMPORTANT: Add your deployed frontend URL here if it's different.
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- Firebase Admin SDK Setup (Railway Compatible) ---
# This block now reads secrets from environment variables instead of a local file.
db = None
try:
    # Get the Base64 encoded service account from environment variables
    firebase_secret_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
    if not firebase_secret_base64:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_BASE64 environment variable not found.")

    # Decode the Base64 string into bytes, then into a JSON string
    decoded_secret = base64.b64decode(firebase_secret_base64).decode('utf-8')
    # Parse the JSON string into a Python dictionary
    service_account_info = json.loads(decoded_secret)

    # Hot-reload safe initialization
    if not firebase_admin._apps:
        # Initialize the app using the credentials dictionary, NOT a file path
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

# --- Model Mapping ---
REPLICATE_MODELS = {
    "veo-3-fast": "google/veo-3-fast",
    "seedance-1-pro": "bytedance/seedance-1-pro",
    "wan-2.2": "wan-video/wan-2.2-i2v-a14b"
}

# --- API Endpoints ---
@app.post("/generate-video")
async def generate_video(request: VideoRequest):
    if not db:
        raise HTTPException(status_code=500, detail="Firestore database not initialized.")

    user_ref = db.collection('users').document(request.user_id)
    model_string = REPLICATE_MODELS.get(request.model_id)
    if not model_string:
        raise HTTPException(status_code=400, detail="Invalid model ID provided.")

    # --- Step 1: Check user and credits (Fast Read) ---
    try:
        user_doc = user_ref.get()
        if not user_doc.exists or user_doc.to_dict().get('credits', 0) <= 0:
            raise HTTPException(status_code=403, detail="User not found or has insufficient credits.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read user data: {e}")

    # --- Step 2: Deduct credit immediately (Fast Write) ---
    try:
        user_ref.update({'credits': firestore.Increment(-1)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deduct credits: {e}")

    # --- Step 3: Prepare and run the long Replicate task ---
    try:
        api_params = request.params.copy()
        
        if "image" in api_params:
            image_data = api_params.get("image")
            if image_data and isinstance(image_data, str) and image_data.startswith("data:image"):
                _header, encoded_data = image_data.split(",", 1)
                decoded_data = base64.b64decode(encoded_data)
                api_params["image"] = io.BytesIO(decoded_data)
            else:
                api_params.pop("image", None)
        
        replicate_output = replicate.run(model_string, input=api_params)

        processed_output = str(replicate_output) if isinstance(replicate_output, FileOutput) else replicate_output
        if isinstance(processed_output, str):
            return {"video_url": [processed_output]}
        elif isinstance(processed_output, list):
            return {"video_url": [str(item) for item in processed_output]}
        else:
            raise TypeError("Unexpected model output format.")

    except Exception as e:
        # --- Step 4: If Replicate fails, refund the credit ---
        print(f"Replicate task failed for user {request.user_id}. Refunding credit. Error: {e}")
        try:
            user_ref.update({'credits': firestore.Increment(1)})
        except Exception as refund_e:
            print(f"CRITICAL: FAILED TO REFUND CREDIT for user {request.user_id}. Error: {refund_e}")
        
        raise HTTPException(status_code=500, detail=f"Video generation failed: {e}")


# --- Main execution block ---
if __name__ == "__main__":
    import uvicorn
    # This setting is primarily for local testing.
    # The Procfile (`web: uvicorn main:app --host 0.0.0.0 --port $PORT`) will be used by Railway.
    port = int(os.environ.get("PORT", 8000))
    if not os.getenv("REPLICATE_API_TOKEN"):
        print("CRITICAL ERROR: REPLICATE_API_TOKEN not set.")
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
