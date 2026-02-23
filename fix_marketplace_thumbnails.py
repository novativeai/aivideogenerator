"""
Script to fix marketplace listings that have thumbnailUrl === videoUrl.
Downloads each video, extracts a frame with ffmpeg, uploads to Firebase Storage,
and updates the Firestore document.
"""

import os
import json
import base64
import subprocess
import tempfile
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
service_account_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
if not service_account_base64:
    print('FIREBASE_SERVICE_ACCOUNT_BASE64 not found in .env')
    exit(1)

service_account_json = base64.b64decode(service_account_base64).decode('utf-8')
service_account = json.loads(service_account_json)

bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET', 'reelzila.firebasestorage.app')

if not firebase_admin._apps:
    cred = credentials.Certificate(service_account)
    firebase_admin.initialize_app(cred, {
        'storageBucket': bucket_name
    })

db = firestore.client()


def is_video_url(url: str) -> bool:
    """Check if URL looks like a video rather than a static thumbnail."""
    if not url:
        return False
    video_extensions = ('.mp4', '.webm', '.mov', '.avi')
    lower = url.lower()
    # Check file extension
    for ext in video_extensions:
        if ext in lower:
            return True
    # fal.media URLs are always video
    if 'fal.media' in lower:
        return True
    return False


def is_static_thumbnail(url: str) -> bool:
    """Check if URL is already a proper static thumbnail (Firebase Storage image)."""
    if not url:
        return False
    lower = url.lower()
    return ('storage.googleapis.com' in lower or 'firebasestorage.googleapis.com' in lower) and \
           ('.jpg' in lower or '.jpeg' in lower or '.png' in lower or '.webp' in lower)


def extract_and_upload_thumbnail(video_url: str, seller_id: str) -> str | None:
    """Download video, extract frame at 0.5s with ffmpeg, upload JPEG to Firebase Storage."""
    tmp_video_path = None
    tmp_thumb_path = None
    try:
        # Download enough of the video to extract a frame (first 2 MB)
        resp = requests.get(video_url, stream=True, timeout=30)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp_video_path = tmp.name
            downloaded = 0
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
                downloaded += len(chunk)
                if downloaded > 2 * 1024 * 1024:
                    break

        # Extract frame at 0.5s
        tmp_thumb_path = tmp_video_path.replace('.mp4', '.jpg')
        result = subprocess.run(
            ['ffmpeg', '-i', tmp_video_path, '-ss', '0.5', '-frames:v', '1',
             '-q:v', '2', '-y', tmp_thumb_path],
            capture_output=True, timeout=15
        )
        if result.returncode != 0:
            print(f'  ffmpeg failed: {result.stderr.decode()[:200]}')
            return None

        # Upload to Firebase Storage
        bucket = storage.bucket()
        ts = int(datetime.now().timestamp() * 1000)
        blob_path = f"marketplace/thumbnails/{seller_id}/{ts}.jpg"
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(tmp_thumb_path, content_type='image/jpeg')
        blob.make_public()
        return blob.public_url

    except Exception as e:
        print(f'  Error: {e}')
        return None
    finally:
        for path in [tmp_video_path, tmp_thumb_path]:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def fix_all_listings():
    """Find and fix all marketplace listings with missing or video-URL thumbnails."""
    print('Scanning marketplace_listings for broken thumbnails...\n')

    listings_ref = db.collection('marketplace_listings')
    docs = listings_ref.stream()

    broken = []
    ok = []

    for doc in docs:
        data = doc.to_dict()
        title = data.get('title', 'Untitled')
        thumb = data.get('thumbnailUrl', '')
        video = data.get('videoUrl', '')

        # A listing needs a fix if:
        # 1. thumbnailUrl is empty
        # 2. thumbnailUrl === videoUrl (both are video)
        # 3. thumbnailUrl is a video URL (not a static image)
        needs_fix = (
            not thumb or
            thumb == video or
            (is_video_url(thumb) and not is_static_thumbnail(thumb))
        )

        if needs_fix:
            broken.append((doc.id, data))
            print(f'  BROKEN: "{title}" (ID: {doc.id})')
            print(f'          thumb: {thumb[:80]}...' if len(thumb) > 80 else f'          thumb: {thumb}')
        else:
            ok.append(doc.id)

    print(f'\nFound {len(broken)} broken, {len(ok)} OK\n')

    if not broken:
        print('All listings have proper thumbnails!')
        return

    # Fix each broken listing
    fixed = 0
    failed = 0
    for doc_id, data in broken:
        title = data.get('title', 'Untitled')
        video_url = data.get('videoUrl', '')
        seller_id = data.get('sellerId', 'unknown')

        if not video_url:
            print(f'  SKIP "{title}": no videoUrl')
            failed += 1
            continue

        print(f'  Fixing "{title}"...')
        thumbnail_url = extract_and_upload_thumbnail(video_url, seller_id)

        if thumbnail_url:
            # Update Firestore
            listings_ref.document(doc_id).update({
                'thumbnailUrl': thumbnail_url,
                'updatedAt': firestore.SERVER_TIMESTAMP,
            })
            print(f'  OK: {thumbnail_url}')
            fixed += 1
        else:
            print(f'  FAILED: Could not generate thumbnail')
            failed += 1

    print(f'\nDone! Fixed: {fixed}, Failed: {failed}')


if __name__ == '__main__':
    fix_all_listings()
