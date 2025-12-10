"""
Script to upload new videos to Firebase Storage and create Firestore documents
With automatic video optimization for lightweight, high-quality delivery
"""

import os
import json
import base64
from datetime import datetime
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv
from video_optimizer import VideoOptimizer, OptimizationResult

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


def upload_video_to_storage(local_path, storage_path, optimize=True):
    """
    Upload a video file to Firebase Storage with optional optimization

    Args:
        local_path: Path to local video file
        storage_path: Destination path in Firebase Storage
        optimize: Whether to optimize video before upload (default: True)

    Returns:
        tuple: (video_url, thumbnail_url, optimization_stats)
    """
    try:
        video_to_upload = str(local_path)
        thumbnail_path = None
        optimization_stats = None

        # Optimize video if requested
        if optimize:
            print('  Optimizing video...')
            optimizer = VideoOptimizer(quality='balanced')
            result = optimizer.optimize(
                input_path=str(local_path),
                generate_thumbnail=True
            )

            if result.success:
                video_to_upload = result.output_path
                thumbnail_path = result.thumbnail_path
                optimization_stats = {
                    'original_size_mb': result.original_size / 1024 / 1024,
                    'optimized_size_mb': result.optimized_size / 1024 / 1024,
                    'compression_ratio': result.compression_ratio
                }
                print(f'  Optimized: {optimization_stats["original_size_mb"]:.2f}MB -> {optimization_stats["optimized_size_mb"]:.2f}MB ({result.compression_ratio:.1f}% reduction)')
            else:
                print(f'  Optimization failed: {result.error}')
                print('  Uploading original file instead...')

        # Upload optimized video
        blob = bucket.blob(storage_path)
        blob.content_type = 'video/mp4'
        blob.upload_from_filename(video_to_upload)
        blob.make_public()
        video_url = blob.public_url

        # Upload thumbnail if generated
        thumbnail_url = video_url  # Fallback to video URL
        if thumbnail_path and os.path.exists(thumbnail_path):
            thumb_storage_path = storage_path.replace('.mp4', '_thumb.jpg').replace('.MP4', '_thumb.jpg')
            thumb_blob = bucket.blob(thumb_storage_path)
            thumb_blob.content_type = 'image/jpeg'
            thumb_blob.upload_from_filename(thumbnail_path)
            thumb_blob.make_public()
            thumbnail_url = thumb_blob.public_url
            print(f'  Thumbnail uploaded: {thumbnail_url[:60]}...')

            # Clean up temp thumbnail
            os.remove(thumbnail_path)

        # Clean up temp optimized video
        if optimize and video_to_upload != str(local_path) and os.path.exists(video_to_upload):
            os.remove(video_to_upload)

        return video_url, thumbnail_url, optimization_stats

    except Exception as e:
        print(f'  Error uploading {local_path}: {str(e)}')
        return None, None, None


def create_marketplace_listing(video_data, video_url, thumbnail_url=None):
    """
    Create marketplace listing in Firestore

    Args:
        video_data: Video metadata
        video_url: Firebase Storage URL
        thumbnail_url: Thumbnail URL (optional, defaults to video_url)

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
            'thumbnailUrl': thumbnail_url or video_url,
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
    print('Starting upload of new videos with optimization...\n')
    print('=' * 60)
    print('Video optimization enabled: H.264 CRF 23 (visually lossless)')
    print('Expected compression: 70-85% size reduction')
    print('=' * 60)

    success_count = 0
    total_original_mb = 0
    total_optimized_mb = 0

    for i, video in enumerate(NEW_VIDEOS, 1):
        print(f'\n[{i}/{len(NEW_VIDEOS)}] Processing: {video["local_filename"]}')

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

        # Upload to Firebase Storage (with optimization)
        print('  Processing and uploading...')
        storage_path = f'marketplace/videos/{video["local_filename"]}'
        video_url, thumbnail_url, stats = upload_video_to_storage(local_path, storage_path, optimize=True)

        if not video_url:
            print('  Failed to upload video')
            continue

        # Track compression stats
        if stats:
            total_original_mb += stats['original_size_mb']
            total_optimized_mb += stats['optimized_size_mb']

        print(f'  Video URL: {video_url[:60]}...')

        # Create Firestore document
        print('  Creating Firestore document...')
        listing = create_marketplace_listing(video, video_url, thumbnail_url)

        if listing:
            print(f'  Created listing with ID: {listing["id"]}')
            success_count += 1
        else:
            print('  Failed to create listing')

    print('\n' + '=' * 60)
    print(f'Completed: {success_count}/{len(NEW_VIDEOS)} videos uploaded successfully')
    if total_original_mb > 0:
        total_savings = (1 - total_optimized_mb / total_original_mb) * 100
        print(f'Total size: {total_original_mb:.2f}MB -> {total_optimized_mb:.2f}MB ({total_savings:.1f}% reduction)')
    print('=' * 60)


if __name__ == '__main__':
    main()
