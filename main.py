import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import replicate
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict, Any, List

# Imports for handling the file conversion from base64
import base64
import io

from replicate.helpers import FileOutput

# --- Initialization ---
load_dotenv()
app = FastAPI()

# --- CORS Middleware ---
origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- Firebase Admin SDK Setup ---
script_dir = os.path.dirname(__file__)
key_path = os.path.join(script_dir, "serviceAccountKey.json")
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"CRITICAL ERROR during Firebase init: {e}")
db = firestore.client()

# --- Pydantic Models ---
class VideoRequest(BaseModel):
    user_id: str
    model_id: str
    params: Dict[str, Any]

# --- Model Mapping ---
REPLICATE_MODELS = {
    "veo-3-fast": "google/veo-3-fast",
    "seedance-1-pro": "bytedance/seedance-1-pro"
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
        # If we can't even deduct the credit, stop here. No refund needed.
        raise HTTPException(status_code=500, detail=f"Failed to deduct credits: {e}")

    # --- Step 3: Prepare and run the long Replicate task ---
    try:
        api_params = request.params.copy()
        
        # Correctly convert the base64 string from the frontend into a file-like object
        if "image" in api_params:
            image_data = api_params.get("image")
            if image_data and isinstance(image_data, str) and image_data.startswith("data:image"):
                _header, encoded_data = image_data.split(",", 1)
                decoded_data = base64.b64decode(encoded_data)
                # This creates the binary file-like object that Replicate expects
                api_params["image"] = io.BytesIO(decoded_data)
            else:
                # If no valid image data, remove the key so it's not sent to Replicate
                api_params.pop("image", None)
        
        # Make the long-running API call
        replicate_output = replicate.run(model_string, input=api_params)

        # Normalize the output to always be a list of strings
        processed_output = str(replicate_output) if isinstance(replicate_output, FileOutput) else replicate_output
        if isinstance(processed_output, str):
            return {"video_url": [processed_output]}
        elif isinstance(processed_output, list):
            return {"video_url": [str(item) for item in processed_output]}
        else:
            # If output is weird, we still need to refund the user.
            raise TypeError("Unexpected model output format.")

    except Exception as e:
        # --- Step 4: If ANY part of the Replicate task fails, refund the credit ---
        print(f"Replicate task failed for user {request.user_id}. Refunding credit. Error: {e}")
        try:
            user_ref.update({'credits': firestore.Increment(1)})
        except Exception as refund_e:
            print(f"CRITICAL: FAILED TO REFUND CREDIT for user {request.user_id}. Error: {refund_e}")
        
        # Inform the user that the generation failed
        raise HTTPException(status_code=500, detail=f"Video generation failed: {e}")


# --- Main execution block ---
if __name__ == "__main__":
    import uvicorn
    if not os.getenv("REPLICATE_API_TOKEN"):
        print("CRITICAL ERROR: REPLICATE_API_TOKEN not set.")
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)