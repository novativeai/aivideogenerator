"""
List Videos in Firebase Storage

Lists all video files in the marketplace/videos and website/videos folders.
"""

import os
import json
import base64
import firebase_admin
from firebase_admin import credentials, storage
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


def list_videos_in_folder(folder_path: str) -> list:
    """
    List all video files in a Firebase Storage folder.

    Args:
        folder_path: Path to the folder (e.g., 'marketplace/videos')

    Returns:
        List of video filenames
    """
    blobs = bucket.list_blobs(prefix=folder_path)
    videos = []

    for blob in blobs:
        # Skip folder itself and non-mp4 files
        if blob.name.endswith('/'):
            continue
        if blob.name.lower().endswith('.mp4'):
            filename = blob.name.split('/')[-1]
            videos.append(filename)

    return sorted(videos)


def main():
    print('=' * 70)
    print('FIREBASE STORAGE VIDEO LISTING')
    print('=' * 70)

    # List marketplace videos
    print('\n--- MARKETPLACE VIDEOS (marketplace/videos/) ---\n')
    marketplace_videos = list_videos_in_folder('marketplace/videos')

    if marketplace_videos:
        for i, video in enumerate(marketplace_videos, 1):
            print(f'{i:3}. {video}')
        print(f'\nTotal: {len(marketplace_videos)} videos')
    else:
        print('No videos found')

    # List website videos
    print('\n--- WEBSITE VIDEOS (website/videos/) ---\n')
    website_videos = list_videos_in_folder('website/videos')

    if website_videos:
        for i, video in enumerate(website_videos, 1):
            print(f'{i:3}. {video}')
        print(f'\nTotal: {len(website_videos)} videos')
    else:
        print('No videos found')

    print('\n' + '=' * 70)

    # Output as JSON for easy reference
    result = {
        'marketplace_videos': marketplace_videos,
        'website_videos': website_videos
    }

    output_file = 'storage_videos_list.json'
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'Saved to: {output_file}')


if __name__ == '__main__':
    main()
