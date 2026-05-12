"""
Populate marketplace with ALL numbered videos (001-055) from Firebase Storage
Uses massive_hits_unified_prompts.json for proper metadata on 001-048
Creates proper metadata for 049-055
Preserves thumbnail system (thumbnailUrl = videoUrl initially)
"""

import os
import re
import json
import base64
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv
import requests

# Load .env from frontend directory
env_path = Path('video-generator-frontend/.env.local')
if env_path.exists():
    load_dotenv(dotenv_path=str(env_path))
else:
    load_dotenv()

# Initialize Firebase Admin SDK
service_account_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
if not service_account_base64:
    print('❌ FIREBASE_SERVICE_ACCOUNT_BASE64 not found in .env')
    print('   Tried: video-generator-frontend/.env.local')
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


def load_prompts_metadata():
    """Load metadata from massive_hits_unified_prompts.json"""
    with open('massive_hits_unified_prompts.json', 'r') as f:
        data = json.load(f)
    
    metadata_by_id = {}
    for video in data['videos']:
        video_id = video['id'].lstrip('0')  # "001" -> "1"
        metadata_by_id[video_id] = video
    
    return metadata_by_id


# Metadata for videos 049-055 (not in prompts file)
EXTRA_METADATA = {
    "49": {
        "title": "Cinematic Bedroom Portrait",
        "prompt": "A woman lying gracefully on a bed, soft natural light streaming through window curtains, cinematic composition with warm tones, gentle shadows creating depth, intimate and elegant atmosphere, slow camera movement.",
        "tags": ["portrait", "cinematic", "bedroom", "woman", "elegant"],
        "category": "cinematic_portrait",
        "width": 1920, "height": 1080, "aspect_ratio": "16:9", "duration": "5"
    },
    "50": {
        "title": "Morning Coffee Moment",
        "prompt": "A woman holding a warm mug of coffee, soft morning light illuminating steam rising from the cup, cozy kitchen atmosphere, natural expressions, warm color palette, intimate daily life moment.",
        "tags": ["coffee", "morning", "cozy", "lifestyle", "woman"],
        "category": "lifestyle",
        "width": 1920, "height": 1080, "aspect_ratio": "16:9", "duration": "5"
    },
    "51": {
        "title": "Library Reading Session",
        "prompt": "A woman browsing books in a cozy library, warm ambient lighting, shelves filled with books in background, contemplative mood, soft focus on subject, intellectual and peaceful atmosphere.",
        "tags": ["library", "books", "reading", "peaceful", "woman"],
        "category": "lifestyle",
        "width": 1920, "height": 1080, "aspect_ratio": "16:9", "duration": "5"
    },
    "52": {
        "title": "Subway Commute with Headphones",
        "prompt": "An young woman on a subway train wearing bright orange headphones, lost in music, city commute atmosphere, natural lighting from subway windows, candid urban lifestyle moment.",
        "tags": ["subway", "urban", "commute", "headphones", "woman"],
        "category": "urban_lifestyle",
        "width": 1920, "height": 1080, "aspect_ratio": "16:9", "duration": "5"
    },
    "53": {
        "title": "Macro Emerald Eyes Close-Up",
        "prompt": "Extreme macro close-up of stunning emerald green eyes with red hair framing the face, intricate iris details visible, dramatic studio lighting creating catchlights, mesmerizing beauty shot.",
        "tags": ["macro", "close-up", "eyes", "beauty", "portrait"],
        "category": "beauty_macro",
        "width": 1920, "height": 1080, "aspect_ratio": "16:9", "duration": "5"
    },
    "54": {
        "title": "Kitchen Dance Joy",
        "prompt": "A woman with emerald eyes dancing joyfully in a sunlit kitchen, natural movement and laughter, warm afternoon light, candid and happy moment, casual home lifestyle.",
        "tags": ["dance", "kitchen", "joy", "lifestyle", "woman"],
        "category": "lifestyle",
        "width": 1920, "height": 1080, "aspect_ratio": "16:9", "duration": "5"
    },
    "55": {
        "title": "Motorcycle Highway Speed",
        "prompt": "A motorcycle speeding down a highway at golden hour, dynamic motion blur, sunset lighting creating long shadows, freedom and adventure feeling, sweeping landscape visible behind.",
        "tags": ["motorcycle", "speed", "highway", "adventure", "golden_hour"],
        "category": "fast_paced_dynamic",
        "width": 1920, "height": 1080, "aspect_ratio": "16:9", "duration": "5"
    }
}


def get_video_id_from_filename(filename):
    """Extract numeric ID from filename like '001_Speedboat_Chase.mp4' -> '1'"""
    match = re.match(r'^(\d+)_', filename)
    if match:
        return str(int(match.group(1)))  # Strip leading zeros
    return None


def make_public_url(blob_path):
    """Get public URL for a storage blob"""
    return f"https://storage.googleapis.com/{bucket.name}/{blob_path}"


def extract_and_upload_thumbnail(video_url: str, seller_id: str = "admin") -> str | None:
    """Download a video, extract a frame at 0.5s with ffmpeg, upload JPEG to Firebase Storage."""
    tmp_video_path = None
    tmp_thumb_path = None
    try:
        resp = requests.get(video_url, stream=True, timeout=60)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp_video_path = tmp.name
            for chunk in resp.iter_content(chunk_size=65536):
                tmp.write(chunk)

        tmp_thumb_path = tmp_video_path.replace('.mp4', '.jpg')
        result = subprocess.run(
            ['ffmpeg', '-i', tmp_video_path, '-ss', '0.5', '-frames:v', '1',
             '-q:v', '2', '-y', tmp_thumb_path],
            capture_output=True, timeout=15
        )
        if result.returncode != 0:
            print(f'    ⚠️  ffmpeg failed: {result.stderr.decode()[:200]}')
            return None

        bucket_storage = storage.bucket()
        ts = int(datetime.now().timestamp() * 1000)
        blob_path = f"marketplace/thumbnails/{seller_id}/{ts}.jpg"
        blob = bucket_storage.blob(blob_path)
        blob.upload_from_filename(tmp_thumb_path, content_type='image/jpeg')
        blob.make_public()
        return blob.public_url

    except Exception as e:
        print(f'    ⚠️  Thumbnail extraction error: {e}')
        return None
    finally:
        for path in [tmp_video_path, tmp_thumb_path]:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def delete_all_listings():
    """Delete ALL existing marketplace listings"""
    print('\n🗑️  Deleting all existing marketplace listings...')
    listings = list(db.collection('marketplace_listings').get())
    print(f'   Found {len(listings)} existing listings')
    
    for doc in listings:
        doc.reference.delete()
        print(f'   ✗ Deleted: {doc.id}')
    
    print(f'   ✓ Deleted {len(listings)} listings total')


def get_video_blobs():
    """
    Get all non-optimized numbered video blobs (001-055)
    Returns list of dicts with path, filename, video_id
    """
    video_blobs = []
    seen_filenames = set()  # Track to avoid duplicates (e.g. 031 exists in two paths)
    
    for blob in bucket.list_blobs():
        # Skip thumbnails and optimized versions
        if blob.name.lower().endswith('.jpg'):
            continue
        if '_optimized' in blob.name:
            continue
        
        filename = Path(blob.name).name.lower()
        
        # Only include numbered videos (starting with digits)
        if not filename[0].isdigit():
            continue
        if not filename.endswith('.mp4'):
            continue
        
        video_id = get_video_id_from_filename(Path(blob.name).name)
        if not video_id:
            continue
        
        video_num = int(video_id)
        if video_num < 1 or video_num > 55:
            continue
        
        # Skip duplicates - prefer the shorter path (marketplace/ over marketplace/videos/)
        if filename in seen_filenames:
            existing = [v for v in video_blobs if Path(v['blob'].name).name.lower() == filename]
            if existing:
                existing_path = existing[0]['blob'].name
                new_path = blob.name
                # Prefer the shorter/more direct path
                if len(new_path) < len(existing_path):
                    video_blobs.remove(existing[0])
                    video_blobs.append({
                        'blob': blob,
                        'filename': Path(blob.name).name,
                        'video_id': video_id,
                        'video_num': video_num
                    })
                    print(f'   ↻ Replaced {existing_path} with {new_path} (shorter path)')
                else:
                    print(f'   ↻ Skipping duplicate: {blob.name} (keeping {existing_path})')
            continue
        
        seen_filenames.add(filename)
        video_blobs.append({
            'blob': blob,
            'filename': Path(blob.name).name,
            'video_id': video_id,
            'video_num': video_num
        })
    
    # Sort by video number
    video_blobs.sort(key=lambda v: v['video_num'])
    return video_blobs


def create_listing(video_info, metadata):
    """Create a marketplace listing in Firestore"""
    try:
        blob = video_info['blob']
        filename = video_info['filename']
        video_num = video_info['video_num']
        video_id = video_info['video_id']
        
        # Make public
        blob.make_public()
        video_url = blob.public_url

        # Generate a proper static thumbnail from the video
        print(f'     Generating thumbnail...')
        thumbnail_url = extract_and_upload_thumbnail(video_url)
        if thumbnail_url:
            print(f'     ✅ Thumbnail: {thumbnail_url[:70]}...')
        else:
            thumbnail_url = video_url  # Fallback to video URL
            print(f'     ⚠️  Using video URL as fallback thumbnail')
        
        # Build the listing document
        listing_ref = db.collection('marketplace_listings').document()
        
        # Parse duration (could be string or int)
        raw_duration = metadata.get('duration', '5')
        try:
            duration_seconds = int(raw_duration)
        except (ValueError, TypeError):
            duration_seconds = 5
        
        # Parse tags safely (prompts JSON uses string tags array, which is fine)
        raw_tags = metadata.get('tags', ['stock footage'])
        
        listing = {
            'id': listing_ref.id,
            'sellerId': 'admin',
            'sellerName': 'Reelzila',
            'title': metadata['title'],
            'description': metadata.get('prompt', metadata['title']),
            'videoUrl': video_url,
            'generationId': f'imported_{int(video_id):03d}',
            'prompt': metadata.get('prompt', metadata['title']),
            'price': 4.99,
            'tags': raw_tags,
            'hasAudio': False,
            'useCases': ['Content Creation', 'Marketing', 'Social Media', 'Background'],
            'thumbnailUrl': thumbnail_url,
            'status': 'published',
            'createdAt': firestore.SERVER_TIMESTAMP,
            'updatedAt': firestore.SERVER_TIMESTAMP,
            'sold': 0,
            'aspectRatio': metadata.get('aspect_ratio', '16:9'),
            'duration': f"{duration_seconds}s",
            'durationSeconds': duration_seconds,
            'resolution': f"{metadata.get('width', 1920)}x{metadata.get('height', 1080)}",
            'fileSize': f"{blob.size / (1024 * 1024):.2f} MB" if blob.size else 'Unknown',
            'fileName': filename,
            'category': metadata.get('category', 'general'),
            'videoId': f'{video_num:03d}'
        }
        
        listing_ref.set(listing)
        return listing
    except Exception as e:
        print(f'  ❌ Error creating listing for {filename}: {str(e)}')
        return None


def main():
    print('=' * 70)
    print('🚀 Populating Marketplace with ALL numbered videos (001-055)')
    print('=' * 70)
    
    # Load metadata
    print('\n📖 Loading metadata from massive_hits_unified_prompts.json...')
    prompts_metadata = load_prompts_metadata()
    print(f'   Loaded {len(prompts_metadata)} entries (001-048)')
    
    # Get video blobs
    print('\n🔍 Scanning Firebase Storage for numbered videos...')
    video_blobs = get_video_blobs()
    print(f'   Found {len(video_blobs)} numbered videos')
    for v in video_blobs:
        print(f'     {v["video_num"]:03d}: {v["filename"]} ({v["blob"].name})')
    
    # Delete existing listings
    delete_all_listings()
    
    # Create listings
    print('\n📝 Creating marketplace listings...')
    success_count = 0
    error_count = 0
    
    for video_info in video_blobs:
        video_num = video_info['video_num']
        video_id = video_info['video_id']
        filename = video_info['filename']
        
        # Get metadata
        if video_id in prompts_metadata:
            metadata = prompts_metadata[video_id]
            source = 'prompts JSON'
        elif video_id in EXTRA_METADATA:
            metadata = EXTRA_METADATA[video_id]
            source = 'extra metadata'
        else:
            print(f'  ⚠️  [{filename}] No metadata found, skipping...')
            error_count += 1
            continue
        
        print(f'\n  [{video_num:03d}] {filename} (using {source})')
        print(f'     Title: {metadata["title"]}')
        
        listing = create_listing(video_info, metadata)
        
        if listing:
            print(f'     ✓ Created: {listing["id"]}')
            success_count += 1
        else:
            print(f'     ❌ Failed to create listing')
            error_count += 1
    
    # Summary
    print('\n' + '=' * 70)
    print('✅ Marketplace population complete!')
    print(f'   Videos found in storage: {len(video_blobs)}')
    print(f'   Successfully created: {success_count}')
    print(f'   Errors: {error_count}')
    print('=' * 70)
    
    print('\n📋 Note: Proper static thumbnails are now generated during population.')
    print('   No need to run fix_marketplace_thumbnails.py for newly uploaded videos.')


if __name__ == '__main__':
    main()
