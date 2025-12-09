"""
Script to upload 3 new videos to Firebase Storage and create Firestore documents
"""

import os
import json
import base64
from datetime import datetime
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
service_account_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
if not service_account_base64:
    print('FIREBASE_SERVICE_ACCOUNT_BASE64 not found in .env')
    exit(1)

service_account_json = base64.b64decode(service_account_base64).decode('utf-8')
service_account = json.loads(service_account_json)

if not firebase_admin._apps:
    cred = credentials.Certificate(service_account)
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', 'reelzila.firebasestorage.app')
    })

bucket = storage.bucket()
db = firestore.client()

# Define the 3 new videos with their metadata
NEW_VIDEOS = [
    {
        'local_filename': '049_Woman_Cinematic_On_Bed.mp4',
        'title': 'Woman Cinematic On Bed',
        'description': 'A woman lying on a bed in cinematic lighting, soft shadows and warm tones creating an intimate atmosphere. Camera captures gentle movements with shallow depth of field, fabric textures visible, peaceful and artistic mood.',
        'prompt': 'woman cinematic on bed, soft lighting, intimate atmosphere, shallow depth of field',
        'tags': ['lifestyle', 'cinematic', 'intimate', 'portrait', 'woman', 'bedroom', 'artistic'],
        'useCases': ['Content Creation', 'Social Media', 'Marketing', 'Music Videos'],
        'hasAudio': True,
        'width': 1920,
        'height': 1080,
        'duration': 5,
        'price': 4.99
    },
    {
        'local_filename': '050_Woman_Holding_Mug.mp4',
        'title': 'Woman Holding Mug',
        'description': 'A woman holding a warm mug, hands wrapped around ceramic cup with steam rising gently. Soft natural lighting illuminates her face and the mug, cozy atmosphere, relaxed morning or evening vibe, comforting and warm.',
        'prompt': 'woman holding mug, cozy atmosphere, warm lighting, morning routine',
        'tags': ['lifestyle', 'cozy', 'coffee', 'portrait', 'woman', 'morning', 'relaxation'],
        'useCases': ['Content Creation', 'Social Media', 'Marketing', 'Brand Content'],
        'hasAudio': True,
        'width': 1920,
        'height': 1080,
        'duration': 3.5,
        'price': 4.99
    },
    {
        'local_filename': '051_Woman_Library.mp4',
        'title': 'Woman Library',
        'description': 'A woman in a library setting surrounded by bookshelves, soft ambient lighting creating scholarly atmosphere. Books visible in background, thoughtful expression, intellectual and calm environment, cultured and sophisticated.',
        'prompt': 'woman in library, bookshelves, scholarly atmosphere, intellectual mood',
        'tags': ['lifestyle', 'library', 'intellectual', 'portrait', 'woman', 'books', 'education'],
        'useCases': ['Content Creation', 'Social Media', 'Education', 'Marketing'],
        'hasAudio': True,
        'width': 1920,
        'height': 1080,
        'duration': 5,
        'price': 4.99
    }
]

# Path to local videos
LOCAL_VIDEO_PATH = Path('../video-generator-frontend/public/marketplace/videos')


def upload_video_to_storage(local_path, storage_path):
    """
    Upload a video file to Firebase Storage

    Args:
        local_path: Path to local video file
        storage_path: Destination path in Firebase Storage

    Returns:
        str: Public URL of uploaded video
    """
    try:
        blob = bucket.blob(storage_path)

        # Set content type
        blob.content_type = 'video/mp4'

        # Upload file
        blob.upload_from_filename(str(local_path))

        # Make public
        blob.make_public()

        return blob.public_url
    except Exception as e:
        print(f'  Error uploading {local_path}: {str(e)}')
        return None


def create_marketplace_listing(video_data, video_url):
    """
    Create marketplace listing in Firestore

    Args:
        video_data: Video metadata
        video_url: Firebase Storage URL

    Returns:
        dict: Created listing
    """
    try:
        listing_ref = db.collection('marketplace_listings').document()

        # Calculate aspect ratio string
        ratio = video_data['width'] / video_data['height']
        if abs(ratio - 16/9) < 0.1:
            aspect_ratio = '16:9 (Landscape)'
        elif abs(ratio - 9/16) < 0.1:
            aspect_ratio = '9:16 (Portrait)'
        elif abs(ratio - 1) < 0.1:
            aspect_ratio = '1:1 (Square)'
        else:
            aspect_ratio = f"{video_data['width']}x{video_data['height']}"

        # Format duration
        duration_secs = video_data['duration']
        if duration_secs >= 60:
            duration_str = f"{int(duration_secs // 60)}m {int(duration_secs % 60)}s"
        else:
            duration_str = f"{int(duration_secs)}s"

        listing = {
            'id': listing_ref.id,
            'sellerId': 'admin',
            'sellerName': 'Reelzila',
            'title': video_data['title'],
            'description': video_data['description'],
            'videoUrl': video_url,
            'generationId': 'imported',
            'prompt': video_data['prompt'],
            'price': video_data['price'],
            'tags': video_data['tags'],
            'hasAudio': video_data['hasAudio'],
            'useCases': video_data['useCases'],
            'thumbnailUrl': video_url,
            'status': 'published',
            'createdAt': firestore.SERVER_TIMESTAMP,
            'updatedAt': firestore.SERVER_TIMESTAMP,
            'sold': 0,
            'aspectRatio': aspect_ratio,
            'duration': duration_str,
            'durationSeconds': video_data['duration'],
            'resolution': f"{video_data['width']}x{video_data['height']}",
            'fileName': video_data['local_filename']
        }

        listing_ref.set(listing)
        return listing
    except Exception as e:
        print(f'  Error creating listing: {str(e)}')
        return None


def main():
    print('Starting upload of 3 new videos...\n')
    print('=' * 60)

    success_count = 0

    for i, video in enumerate(NEW_VIDEOS, 1):
        print(f'\n[{i}/3] Processing: {video["local_filename"]}')

        local_path = LOCAL_VIDEO_PATH / video['local_filename']

        # Check if file exists
        if not local_path.exists():
            print(f'  File not found: {local_path}')
            continue

        print(f'  Title: {video["title"]}')
        print(f'  Has Audio: {"Yes" if video["hasAudio"] else "No"}')
        print(f'  Resolution: {video["width"]}x{video["height"]}')
        print(f'  Duration: {video["duration"]}s')
        print(f'  Price: EUR{video["price"]}')

        # Upload to Firebase Storage
        print('  Uploading to Firebase Storage...')
        storage_path = f'marketplace/videos/{video["local_filename"]}'
        video_url = upload_video_to_storage(local_path, storage_path)

        if not video_url:
            print('  Failed to upload video')
            continue

        print(f'  Uploaded: {video_url[:80]}...')

        # Create Firestore document
        print('  Creating Firestore document...')
        listing = create_marketplace_listing(video, video_url)

        if listing:
            print(f'  Created listing with ID: {listing["id"]}')
            success_count += 1
        else:
            print('  Failed to create listing')

    print('\n' + '=' * 60)
    print(f'Completed: {success_count}/3 videos uploaded successfully')
    print('=' * 60)


if __name__ == '__main__':
    main()
