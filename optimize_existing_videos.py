"""
Batch Video Optimization Script

Optimizes all existing marketplace videos in Firebase Storage:
1. Downloads each video
2. Optimizes with FFmpeg (H.264 CRF 23)
3. Generates thumbnail
4. Re-uploads optimized version
5. Updates Firestore document with new URLs

Usage:
    python optimize_existing_videos.py           # Process all videos
    python optimize_existing_videos.py --dry-run # Preview without changes
    python optimize_existing_videos.py --limit 5 # Process only 5 videos
"""

import os
import sys
import json
import base64
import argparse
import tempfile
import requests
from datetime import datetime
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv
from video_optimizer import VideoOptimizer

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
service_account_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
if not service_account_base64:
    print('FIREBASE_SERVICE_ACCOUNT_BASE64 not found in .env')
    sys.exit(1)

service_account_json = base64.b64decode(service_account_base64).decode('utf-8')
service_account = json.loads(service_account_json)

if not firebase_admin._apps:
    cred = credentials.Certificate(service_account)
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', 'reelzila.firebasestorage.app')
    })

bucket = storage.bucket()
db = firestore.client()


def download_video(url: str, output_path: str) -> bool:
    """Download video from URL to local path"""
    try:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except Exception as e:
        print(f'    Error downloading: {str(e)}')
        return False


def upload_optimized_video(local_path: str, storage_path: str) -> str:
    """Upload optimized video to Firebase Storage"""
    try:
        blob = bucket.blob(storage_path)
        blob.content_type = 'video/mp4'
        blob.upload_from_filename(local_path)
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print(f'    Error uploading video: {str(e)}')
        return None


def upload_thumbnail(local_path: str, storage_path: str) -> str:
    """Upload thumbnail to Firebase Storage"""
    try:
        blob = bucket.blob(storage_path)
        blob.content_type = 'image/jpeg'
        blob.upload_from_filename(local_path)
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print(f'    Error uploading thumbnail: {str(e)}')
        return None


def delete_old_blob(storage_path: str) -> bool:
    """Delete old blob from Firebase Storage"""
    try:
        blob = bucket.blob(storage_path)
        blob.delete()
        return True
    except Exception as e:
        # File might not exist, which is OK
        return False


def get_storage_path_from_url(url: str) -> str:
    """Extract storage path from Firebase Storage URL"""
    # URL format: https://storage.googleapis.com/bucket/path/to/file.mp4
    # or: https://bucket.firebasestorage.app/path/to/file.mp4
    if 'firebasestorage.app' in url:
        parts = url.split('firebasestorage.app/')
        if len(parts) > 1:
            return parts[1].split('?')[0]
    elif 'storage.googleapis.com' in url:
        parts = url.split('/')
        # Find the bucket name and get everything after
        for i, part in enumerate(parts):
            if '.appspot.com' in part or 'firebasestorage' in part:
                return '/'.join(parts[i+1:]).split('?')[0]

    # Try to extract from the end
    if 'marketplace/videos/' in url:
        idx = url.find('marketplace/videos/')
        return url[idx:].split('?')[0]

    return None


def process_video(listing: dict, optimizer: VideoOptimizer, dry_run: bool = False) -> dict:
    """
    Process a single video listing

    Returns:
        dict with 'success', 'original_size', 'optimized_size', 'error'
    """
    listing_id = listing.get('id')
    title = listing.get('title', 'Untitled')
    video_url = listing.get('videoUrl')

    if not video_url:
        return {'success': False, 'error': 'No video URL'}

    # Skip if already optimized (check for _optimized suffix or thumbnail exists)
    if '_optimized' in video_url:
        return {'success': False, 'error': 'Already optimized'}

    print(f'  Title: {title}')
    print(f'  URL: {video_url[:60]}...')

    if dry_run:
        print('  [DRY RUN] Would optimize this video')
        return {'success': True, 'dry_run': True}

    # Create temp directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download video
        print('  Downloading...')
        input_path = os.path.join(temp_dir, 'input.mp4')
        if not download_video(video_url, input_path):
            return {'success': False, 'error': 'Download failed'}

        original_size = os.path.getsize(input_path)
        print(f'  Original size: {original_size / 1024 / 1024:.2f}MB')

        # Optimize video
        print('  Optimizing...')
        result = optimizer.optimize(
            input_path=input_path,
            generate_thumbnail=True
        )

        if not result.success:
            return {'success': False, 'error': result.error}

        print(f'  Optimized: {result.original_size / 1024 / 1024:.2f}MB -> {result.optimized_size / 1024 / 1024:.2f}MB ({result.compression_ratio:.1f}% reduction)')

        # Get storage paths
        old_storage_path = get_storage_path_from_url(video_url)
        if not old_storage_path:
            # Fallback: construct from filename
            filename = listing.get('fileName', f'{listing_id}.mp4')
            old_storage_path = f'marketplace/videos/{filename}'

        # Create new paths with _optimized suffix
        base_path = old_storage_path.rsplit('.', 1)[0]
        new_video_path = f'{base_path}_optimized.mp4'
        new_thumb_path = f'{base_path}_thumb.jpg'

        # Upload optimized video
        print('  Uploading optimized video...')
        new_video_url = upload_optimized_video(result.output_path, new_video_path)
        if not new_video_url:
            return {'success': False, 'error': 'Upload failed'}

        # Upload thumbnail
        new_thumb_url = None
        if result.thumbnail_path:
            print('  Uploading thumbnail...')
            new_thumb_url = upload_thumbnail(result.thumbnail_path, new_thumb_path)

        # Update Firestore document
        print('  Updating Firestore document...')
        try:
            doc_ref = db.collection('marketplace_listings').document(listing_id)
            update_data = {
                'videoUrl': new_video_url,
                'updatedAt': firestore.SERVER_TIMESTAMP,
                'optimized': True,
                'originalSize': original_size,
                'optimizedSize': result.optimized_size,
            }
            if new_thumb_url:
                update_data['thumbnailUrl'] = new_thumb_url

            doc_ref.update(update_data)
        except Exception as e:
            return {'success': False, 'error': f'Firestore update failed: {str(e)}'}

        # Optionally delete old video (commented out for safety)
        # delete_old_blob(old_storage_path)

        print(f'  Done! New URL: {new_video_url[:60]}...')

        return {
            'success': True,
            'original_size': original_size,
            'optimized_size': result.optimized_size,
            'compression_ratio': result.compression_ratio
        }


def main():
    parser = argparse.ArgumentParser(description='Optimize existing marketplace videos')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of videos to process')
    parser.add_argument('--quality', choices=['high', 'balanced', 'small'], default='balanced',
                        help='Quality preset (default: balanced)')
    args = parser.parse_args()

    print('=' * 70)
    print('MARKETPLACE VIDEO BATCH OPTIMIZATION')
    print('=' * 70)
    print(f'Quality preset: {args.quality}')
    print(f'Dry run: {args.dry_run}')
    if args.limit:
        print(f'Limit: {args.limit} videos')
    print('=' * 70)

    # Initialize optimizer
    try:
        optimizer = VideoOptimizer(quality=args.quality)
    except RuntimeError as e:
        print(f'Error: {str(e)}')
        sys.exit(1)

    # Fetch all marketplace listings
    print('\nFetching marketplace listings...')
    listings = []
    docs = db.collection('marketplace_listings').stream()

    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        listings.append(data)

    print(f'Found {len(listings)} listings')

    # Filter out already optimized
    to_process = [l for l in listings if not l.get('optimized', False) and '_optimized' not in l.get('videoUrl', '')]
    print(f'Videos to optimize: {len(to_process)}')

    if args.limit:
        to_process = to_process[:args.limit]
        print(f'Processing limited to: {len(to_process)} videos')

    if not to_process:
        print('\nNo videos need optimization!')
        return

    # Process each video
    success_count = 0
    error_count = 0
    total_original = 0
    total_optimized = 0

    for i, listing in enumerate(to_process, 1):
        print(f'\n[{i}/{len(to_process)}] Processing: {listing.get("id")}')

        result = process_video(listing, optimizer, dry_run=args.dry_run)

        if result.get('success'):
            success_count += 1
            if not args.dry_run and 'original_size' in result:
                total_original += result['original_size']
                total_optimized += result['optimized_size']
        else:
            error_count += 1
            print(f'  Error: {result.get("error")}')

    # Summary
    print('\n' + '=' * 70)
    print('OPTIMIZATION COMPLETE')
    print('=' * 70)
    print(f'Successful: {success_count}')
    print(f'Failed: {error_count}')

    if not args.dry_run and total_original > 0:
        total_savings = (1 - total_optimized / total_original) * 100
        print(f'\nTotal storage:')
        print(f'  Before: {total_original / 1024 / 1024:.2f}MB')
        print(f'  After:  {total_optimized / 1024 / 1024:.2f}MB')
        print(f'  Saved:  {(total_original - total_optimized) / 1024 / 1024:.2f}MB ({total_savings:.1f}%)')

    print('=' * 70)


if __name__ == '__main__':
    main()
