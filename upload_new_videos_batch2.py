"""
Script to upload 4 new videos to Firebase Storage and create Firestore documents
"""

import os
import json
import base64
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

# Define the 4 new videos with their metadata
NEW_VIDEOS = [
    {
        'local_filename': '052_Asian_Girl_Subway_Orange_Headphones.mp4',
        'title': 'Asian Girl Subway Orange Headphones',
        'description': 'An Asian girl in her 20s listening to music with orange headphones in a crowded subway train. She wears a white oversized hoodie while others wear darker tones. Shot with 35mm ultra-sharp lens, cinematic cold tone with subject contrast. Camera positioned over the shoulder of another passenger.',
        'prompt': 'an asian girl in her 20s listening to music with orange headphones in a crowded subway train, sitting on the side. Everybody wears darker tone casual clothes, she wears a white hoodie oversize. 35mm ultra sharp lens, cinematic cold tone. Cinematic color subject contrast. Camera on her left side over the shoulder of another person as foreground, just slightly in frame.',
        'tags': ['portrait', 'asian', 'subway', 'headphones', 'cinematic', 'urban', 'lifestyle', 'music'],
        'useCases': ['Content Creation', 'Social Media', 'Music Videos', 'Marketing'],
        'hasAudio': False,
        'width': 1920,
        'height': 1080,
        'duration': 5,
        'price': 4.99
    },
    {
        'local_filename': '053_Macro_Shot_Emerald_Eyes_Redhead.mp4',
        'title': 'Macro Shot Emerald Eyes Redhead',
        'description': 'Stunning macro shot of an emerald-eyed red-haired beauty in her 20s with freckles. Captured with ultra-sharp 85mm lens during golden hour with soft lighting. Cinematic tone focusing on her captivating eyes.',
        'prompt': 'macro-shot on emerauld-eyes red hair beauty in her 20s with freckles. Ultra-sharp 85mm lens. Golden-hour soft lighting. Cinematic tone. 2 eyes only on frame.',
        'tags': ['portrait', 'macro', 'eyes', 'redhead', 'freckles', 'golden-hour', 'cinematic', 'beauty'],
        'useCases': ['Content Creation', 'Social Media', 'Beauty', 'Marketing'],
        'hasAudio': False,
        'width': 1920,
        'height': 1080,
        'duration': 5,
        'price': 4.99
    },
    {
        'local_filename': '054_Emerald_Eyes_Kitchen_Dance.mp4',
        'title': 'Emerald Eyes Kitchen Dance',
        'description': 'An emerald-eyed, dark-haired beauty in her 20s with freckles dancing joyfully in the kitchen. Shot with ultra-sharp 35mm lens during golden hour with soft, warm lighting creating a cozy atmosphere.',
        'prompt': 'An emerald-eyed, dark-haired beauty in her 20s with freckles dance in the kitchen. Ultra-sharp 35mm. Golden-hour soft lighting.',
        'tags': ['portrait', 'dance', 'kitchen', 'lifestyle', 'golden-hour', 'joyful', 'cinematic', 'woman'],
        'useCases': ['Content Creation', 'Social Media', 'Lifestyle', 'Marketing'],
        'hasAudio': True,
        'width': 1080,
        'height': 1920,
        'duration': 5,
        'price': 4.99
    },
    {
        'local_filename': '055_Motorcycle_Highway_Speed.mp4',
        'title': 'Motorcycle Highway Speed',
        'description': 'An emerald-eyed, dark-haired beauty in her 20s with freckles riding a motorcycle at high speed on a highway, zigzagging through traffic with open visor. Ultra-sharp 35mm mounted in front, blue-hour soft lighting with cold cinematic tone and lowkey lighting.',
        'prompt': 'An emerald-eyed, dark-haired beauty in her 20s with freckles drives a motorcycle at high speed on a highway, zigzagging through traffic, with open visor. Ultra-sharp 35mm mounted in front of her motorcycle, oriented toward her. Blue-hour soft lighting with a cold blue cinematic tone. Lowkey lighting.',
        'tags': ['action', 'motorcycle', 'highway', 'speed', 'blue-hour', 'cinematic', 'woman', 'adrenaline'],
        'useCases': ['Content Creation', 'Social Media', 'Action', 'Marketing'],
        'hasAudio': True,
        'width': 1080,
        'height': 1920,
        'duration': 5,
        'price': 4.99
    }
]

LOCAL_VIDEO_PATH = Path('../video-generator-frontend/public/marketplace/videos')


def upload_video_to_storage(local_path, storage_path):
    """Upload a video file to Firebase Storage"""
    try:
        blob = bucket.blob(storage_path)
        blob.content_type = 'video/mp4'
        blob.upload_from_filename(str(local_path))
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print(f'  Error uploading {local_path}: {str(e)}')
        return None


def create_marketplace_listing(video_data, video_url):
    """Create marketplace listing in Firestore"""
    try:
        listing_ref = db.collection('marketplace_listings').document()

        ratio = video_data['width'] / video_data['height']
        if abs(ratio - 16/9) < 0.1:
            aspect_ratio = '16:9 (Landscape)'
        elif abs(ratio - 9/16) < 0.1:
            aspect_ratio = '9:16 (Portrait)'
        elif abs(ratio - 1) < 0.1:
            aspect_ratio = '1:1 (Square)'
        else:
            aspect_ratio = f"{video_data['width']}x{video_data['height']}"

        duration_secs = video_data['duration']
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
    print('=' * 60)
    print('Uploading 4 new videos to marketplace...')
    print('=' * 60)

    success_count = 0

    for i, video in enumerate(NEW_VIDEOS, 1):
        print(f'\n[{i}/4] Processing: {video["local_filename"]}')

        local_path = LOCAL_VIDEO_PATH / video['local_filename']

        if not local_path.exists():
            print(f'  File not found: {local_path}')
            continue

        print(f'  Title: {video["title"]}')
        print(f'  Resolution: {video["width"]}x{video["height"]}')
        print(f'  Has Audio: {"Yes" if video["hasAudio"] else "No"}')
        print(f'  Price: EUR{video["price"]}')

        # Upload to Firebase Storage
        print('  Uploading to Firebase Storage...')
        storage_path = f'marketplace/videos/{video["local_filename"]}'
        video_url = upload_video_to_storage(local_path, storage_path)

        if not video_url:
            print('  Failed to upload video')
            continue

        print(f'  Uploaded: {video_url[:70]}...')

        # Create Firestore document
        print('  Creating Firestore document...')
        listing = create_marketplace_listing(video, video_url)

        if listing:
            print(f'  Created listing ID: {listing["id"]}')
            success_count += 1
        else:
            print('  Failed to create listing')

    print('\n' + '=' * 60)
    print(f'Completed: {success_count}/4 videos uploaded successfully')
    print('=' * 60)


if __name__ == '__main__':
    main()
