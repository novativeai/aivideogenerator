"""
Upload Website Videos to Firebase Storage

Uploads videos from /public/videos to Firebase Storage with lossless optimization.
These are used for the website UI (hero, about page, model highlights, etc.)

Storage path: website/videos/
Quality: High (CRF 18) - near lossless compression
"""

import os
import json
import base64
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, storage
from dotenv import load_dotenv
from video_optimizer import VideoOptimizer

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

# Path to local videos
LOCAL_VIDEO_PATH = Path('../video-generator-frontend/public/videos')

# Storage folder for website videos
STORAGE_FOLDER = 'website/videos'


def upload_video(local_path: Path, optimize: bool = True) -> tuple:
    """
    Upload a video file to Firebase Storage with optional lossless optimization

    Args:
        local_path: Path to local video file
        optimize: Whether to optimize video before upload

    Returns:
        tuple: (video_url, stats)
    """
    filename = local_path.name
    storage_path = f'{STORAGE_FOLDER}/{filename}'

    try:
        video_to_upload = str(local_path)
        stats = None

        if optimize:
            print(f'  Optimizing (high quality, near-lossless)...')
            # Use 'high' quality preset (CRF 18) for near-lossless compression
            optimizer = VideoOptimizer(quality='high')
            result = optimizer.optimize(
                input_path=str(local_path),
                generate_thumbnail=False  # No thumbnails needed for website videos
            )

            if result.success:
                video_to_upload = result.output_path
                stats = {
                    'original_size_mb': result.original_size / 1024 / 1024,
                    'optimized_size_mb': result.optimized_size / 1024 / 1024,
                    'compression_ratio': result.compression_ratio
                }
                print(f'  Optimized: {stats["original_size_mb"]:.2f}MB -> {stats["optimized_size_mb"]:.2f}MB ({result.compression_ratio:.1f}% reduction)')
            else:
                print(f'  Optimization failed: {result.error}')
                print('  Uploading original file instead...')

        # Upload to Firebase Storage
        print(f'  Uploading to {storage_path}...')
        blob = bucket.blob(storage_path)
        blob.content_type = 'video/mp4'
        blob.upload_from_filename(video_to_upload)
        blob.make_public()
        video_url = blob.public_url

        # Clean up temp optimized file
        if optimize and video_to_upload != str(local_path) and os.path.exists(video_to_upload):
            os.remove(video_to_upload)

        return video_url, stats

    except Exception as e:
        print(f'  Error uploading {local_path}: {str(e)}')
        return None, None


def main():
    print('=' * 70)
    print('WEBSITE VIDEO UPLOAD TO FIREBASE STORAGE')
    print('=' * 70)
    print(f'Source: {LOCAL_VIDEO_PATH}')
    print(f'Destination: {STORAGE_FOLDER}/')
    print('Quality: High (CRF 18) - Near-lossless compression')
    print('=' * 70)

    # Check if source directory exists
    if not LOCAL_VIDEO_PATH.exists():
        print(f'Error: Source directory not found: {LOCAL_VIDEO_PATH}')
        return

    # Get all video files
    video_files = list(LOCAL_VIDEO_PATH.glob('*.mp4')) + list(LOCAL_VIDEO_PATH.glob('*.MP4'))
    video_files = sorted(video_files)

    print(f'\nFound {len(video_files)} video files')

    if not video_files:
        print('No video files found!')
        return

    # Track results
    results = {}
    total_original_mb = 0
    total_optimized_mb = 0
    success_count = 0

    for i, video_path in enumerate(video_files, 1):
        print(f'\n[{i}/{len(video_files)}] Processing: {video_path.name}')

        url, stats = upload_video(video_path)

        if url:
            results[video_path.name] = url
            success_count += 1
            print(f'  URL: {url}')

            if stats:
                total_original_mb += stats['original_size_mb']
                total_optimized_mb += stats['optimized_size_mb']
        else:
            print(f'  FAILED')

    # Summary
    print('\n' + '=' * 70)
    print('UPLOAD COMPLETE')
    print('=' * 70)
    print(f'Successful: {success_count}/{len(video_files)}')

    if total_original_mb > 0:
        total_savings = (1 - total_optimized_mb / total_original_mb) * 100
        print(f'\nTotal size:')
        print(f'  Before: {total_original_mb:.2f}MB')
        print(f'  After:  {total_optimized_mb:.2f}MB')
        print(f'  Saved:  {(total_original_mb - total_optimized_mb):.2f}MB ({total_savings:.1f}%)')

    # Output URL mapping for code replacement
    print('\n' + '=' * 70)
    print('URL MAPPING (for code replacement)')
    print('=' * 70)
    for filename, url in results.items():
        print(f'/videos/{filename} -> {url}')

    # Save URL mapping to JSON file for reference
    mapping_file = 'website_video_urls.json'
    with open(mapping_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'\nURL mapping saved to: {mapping_file}')

    print('=' * 70)


if __name__ == '__main__':
    main()
