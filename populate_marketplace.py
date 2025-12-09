"""
Script to populate marketplace with videos from Firebase Storage
Extracts metadata, generates tags, and creates Firestore documents
"""

import os
import re
import json
import base64
from datetime import datetime, timedelta
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
service_account_base64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64')
if not service_account_base64:
    print('❌ FIREBASE_SERVICE_ACCOUNT_BASE64 not found in .env')
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


def parse_filename(filename):
    """
    Parse video filename to extract meaningful information

    Args:
        filename (str): The video filename

    Returns:
        dict: Parsed data including title, tags, and use cases
    """
    # Remove file extension
    name_without_ext = re.sub(r'\.(mp4|mov|avi|webm)$', '', filename, flags=re.IGNORECASE)

    # Replace common separators with spaces
    clean_name = name_without_ext.replace('-', ' ').replace('_', ' ')

    # Handle camelCase
    clean_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean_name).lower()

    # Extract words
    words = [w for w in clean_name.split() if len(w) > 2]

    # Category mapping for tags
    category_map = {
        'nature': ['nature', 'landscape', 'outdoor', 'scenery'],
        'city': ['urban', 'cityscape', 'architecture', 'downtown'],
        'ocean': ['ocean', 'sea', 'water', 'beach', 'marine'],
        'mountain': ['mountain', 'hiking', 'nature', 'landscape'],
        'sunset': ['sunset', 'golden hour', 'evening', 'sky'],
        'sunrise': ['sunrise', 'morning', 'dawn', 'sky'],
        'food': ['food', 'culinary', 'cooking', 'restaurant'],
        'people': ['people', 'lifestyle', 'social', 'human'],
        'business': ['business', 'corporate', 'professional', 'office'],
        'technology': ['technology', 'tech', 'digital', 'modern'],
        'travel': ['travel', 'vacation', 'tourism', 'destination'],
        'fitness': ['fitness', 'health', 'exercise', 'workout'],
        'abstract': ['abstract', 'artistic', 'creative', 'design'],
        'aerial': ['aerial', 'drone', 'birds eye', 'top view'],
        'slow': ['slow motion', 'slo mo', 'cinematic'],
        'time': ['time lapse', 'timelapse', 'fast motion'],
        'night': ['night', 'evening', 'dark', 'nighttime'],
        'day': ['day', 'daytime', 'bright', 'sunny'],
        'rain': ['rain', 'weather', 'wet', 'storm'],
        'snow': ['snow', 'winter', 'cold', 'white'],
        'fire': ['fire', 'flame', 'heat', 'burning'],
        'water': ['water', 'liquid', 'fluid', 'aqua'],
        'sky': ['sky', 'clouds', 'atmosphere', 'aerial'],
        'car': ['car', 'vehicle', 'automotive', 'transportation'],
        'drone': ['aerial', 'drone', 'birds eye', 'elevated view'],
        'sunset': ['golden hour', 'sunset', 'dusk', 'evening'],
        'beach': ['beach', 'coast', 'shore', 'seaside'],
        'forest': ['forest', 'woods', 'trees', 'nature'],
        'street': ['street', 'road', 'urban', 'traffic'],
        'building': ['architecture', 'building', 'structure', 'urban'],
        'cloud': ['clouds', 'sky', 'weather', 'atmosphere'],
        'woman': ['people', 'person', 'human', 'lifestyle'],
        'man': ['people', 'person', 'human', 'lifestyle'],
        'hand': ['hands', 'gestures', 'close-up', 'details'],
        'camera': ['equipment', 'filmmaking', 'photography', 'production'],
        'light': ['lighting', 'illumination', 'glow', 'ambient'],
        'wave': ['ocean', 'water', 'waves', 'coastal'],
        'tree': ['nature', 'vegetation', 'outdoor', 'landscape'],
        'road': ['road', 'highway', 'journey', 'travel'],
        'work': ['work', 'office', 'business', 'professional']
    }

    # Use case mapping
    use_case_map = {
        'nature': ['Content Creation', 'Marketing', 'Background', 'Social Media'],
        'city': ['Marketing', 'Real Estate', 'Travel', 'Background'],
        'business': ['Corporate Videos', 'Marketing', 'Presentations'],
        'food': ['Restaurant Marketing', 'Content Creation', 'Social Media'],
        'technology': ['Tech Reviews', 'Marketing', 'Presentations'],
        'abstract': ['Background', 'Transitions', 'Creative Projects'],
        'aerial': ['Real Estate', 'Travel', 'Marketing', 'Documentaries'],
        'people': ['Social Media', 'Marketing', 'Lifestyle Content'],
        'travel': ['Travel Vlogs', 'Marketing', 'Tourism', 'Documentaries']
    }

    # Generate title
    title = ' '.join(word.capitalize() for word in words)

    # Generate tags
    tags = set(['stock footage', 'video clip'])
    use_cases = set()

    for word in words:
        for category, category_tags in category_map.items():
            if category in word or word in category:
                tags.update(category_tags)
                if category in use_case_map:
                    use_cases.update(use_case_map[category])

    # Add generic use cases if none found
    if not use_cases:
        use_cases.update(['Content Creation', 'Marketing', 'Background', 'Social Media'])

    # Generate description
    description = f"High-quality {title.lower()} stock footage perfect for your creative projects. This video can be used for content creation, marketing campaigns, social media posts, and more."

    return {
        'title': title or 'Stock Video Footage',
        'tags': list(tags)[:10],  # Limit to 10 tags
        'useCases': list(use_cases)[:6],  # Limit to 6 use cases
        'description': description
    }


def get_aspect_ratio(width, height):
    """
    Determine aspect ratio from video dimensions

    Args:
        width (int): Video width
        height (int): Video height

    Returns:
        str: Aspect ratio description
    """
    if not width or not height:
        return 'Unknown'

    ratio = width / height

    if abs(ratio - 16/9) < 0.1:
        return '16:9 (Landscape)'
    elif abs(ratio - 9/16) < 0.1:
        return '9:16 (Portrait)'
    elif abs(ratio - 1) < 0.1:
        return '1:1 (Square)'
    elif abs(ratio - 4/3) < 0.1:
        return '4:3 (Standard)'
    elif abs(ratio - 21/9) < 0.1:
        return '21:9 (Ultrawide)'

    return f'{width}x{height}'


def format_duration(seconds):
    """
    Format duration from seconds to readable string

    Args:
        seconds (float): Duration in seconds

    Returns:
        str: Formatted duration
    """
    if not seconds:
        return 'Unknown'

    mins = int(seconds // 60)
    secs = int(seconds % 60)

    if mins > 0:
        return f'{mins}m {secs}s'
    return f'{secs}s'


def get_video_metadata(file_path):
    """
    Get video metadata from Firebase Storage

    Args:
        file_path (str): Path to video file in storage

    Returns:
        dict: Video metadata or None if error
    """
    try:
        blob = bucket.blob(file_path)

        # Get metadata
        blob.reload()

        # Make video publicly accessible or use a shorter-lived signed URL
        # For marketplace, we'll make the blob publicly readable
        blob.make_public()
        url = blob.public_url

        # Get custom metadata if available
        metadata_dict = blob.metadata or {}

        return {
            'url': url,
            'size': blob.size,
            'contentType': blob.content_type,
            'timeCreated': blob.time_created,
            'width': int(metadata_dict.get('width', 0)) if metadata_dict.get('width') else None,
            'height': int(metadata_dict.get('height', 0)) if metadata_dict.get('height') else None,
            'duration': float(metadata_dict.get('duration', 0)) if metadata_dict.get('duration') else None,
            'hasAudio': metadata_dict.get('hasAudio', 'false').lower() == 'true'
        }
    except Exception as e:
        print(f'  ⚠️  Error getting metadata: {str(e)}')
        return None


def create_marketplace_listing(video_data):
    """
    Create or update marketplace listing in Firestore

    Args:
        video_data (dict): Processed video data

    Returns:
        dict: Created listing or None if error
    """
    try:
        # Create new document reference
        listing_ref = db.collection('marketplace_listings').document()

        listing = {
            'id': listing_ref.id,
            'sellerId': 'admin',  # Platform curated content
            'sellerName': 'Reelzila',
            'title': video_data['title'],
            'description': video_data['description'],
            'videoUrl': video_data['url'],
            'generationId': 'imported',  # Imported from storage
            'prompt': video_data['title'].lower(),
            'price': video_data['price'],
            'tags': video_data['tags'],
            'hasAudio': video_data['hasAudio'],
            'useCases': video_data['useCases'],
            'thumbnailUrl': video_data['url'],  # Use video URL as thumbnail
            'status': 'published',
            'createdAt': firestore.SERVER_TIMESTAMP,
            'updatedAt': firestore.SERVER_TIMESTAMP,
            'sold': 0,
            # Additional metadata
            'aspectRatio': video_data['aspectRatio'],
            'duration': video_data['duration'],
            'durationSeconds': video_data['durationSeconds'],
            'resolution': video_data['resolution'],
            'fileSize': video_data['fileSize'],
            'fileName': video_data['fileName']
        }

        listing_ref.set(listing)
        print(f'  ✓ Created listing: {video_data["title"]} ({video_data["fileName"]})')

        return listing
    except Exception as e:
        print(f'  ❌ Error creating listing: {str(e)}')
        return None


def populate_marketplace():
    """
    Main function to process all videos
    """
    print('🚀 Starting marketplace population...\n')

    try:
        # List all blobs in storage
        blobs = list(bucket.list_blobs())

        # Filter video files
        video_extensions = ['.mp4', '.mov', '.avi', '.webm']
        video_blobs = [
            blob for blob in blobs
            if any(blob.name.lower().endswith(ext) for ext in video_extensions)
        ]

        print(f'📹 Found {len(video_blobs)} video files in storage\n')

        if len(video_blobs) == 0:
            print('No video files found. Make sure videos are uploaded to Firebase Storage.')
            return

        # Process each video
        success_count = 0
        error_count = 0

        for i, blob in enumerate(video_blobs):
            file_name = Path(blob.name).name

            print(f'\n[{i + 1}/{len(video_blobs)}] Processing: {file_name}')

            # Get metadata from storage
            metadata = get_video_metadata(blob.name)

            if not metadata:
                print(f'  ⚠️  Skipping - could not get metadata')
                error_count += 1
                continue

            # Parse filename
            parsed = parse_filename(file_name)

            # Determine pricing based on characteristics
            price = 4.99  # Default
            if metadata['duration'] and metadata['duration'] > 30:
                price = 7.99  # Longer videos
            if metadata['width'] and metadata['width'] >= 3840:
                price = 9.99  # 4K videos

            # Combine all data
            video_data = {
                'fileName': file_name,
                'url': metadata['url'],
                'title': parsed['title'],
                'description': parsed['description'],
                'tags': parsed['tags'],
                'useCases': parsed['useCases'],
                'hasAudio': metadata['hasAudio'],
                'aspectRatio': get_aspect_ratio(metadata['width'], metadata['height']),
                'duration': format_duration(metadata['duration']),
                'durationSeconds': metadata['duration'],
                'resolution': f"{metadata['width']}x{metadata['height']}" if metadata['width'] and metadata['height'] else 'Unknown',
                'fileSize': f"{(metadata['size'] / (1024 * 1024)):.2f} MB",
                'price': price
            }

            # Log extracted info
            print(f'  📝 Title: {video_data["title"]}')
            print(f'  🏷️  Tags: {", ".join(video_data["tags"])}')
            print(f'  📊 Aspect Ratio: {video_data["aspectRatio"]}')
            print(f'  ⏱️  Duration: {video_data["duration"]}')
            print(f'  📐 Resolution: {video_data["resolution"]}')
            print(f'  🔊 Audio: {"Yes" if video_data["hasAudio"] else "No"}')
            print(f'  💰 Price: €{video_data["price"]}')

            # Create listing
            listing = create_marketplace_listing(video_data)

            if listing:
                success_count += 1
            else:
                error_count += 1

        print('\n' + '=' * 60)
        print('✅ Marketplace population complete!')
        print(f'  - Successfully processed: {success_count} videos')
        print(f'  - Errors: {error_count}')
        print(f'  - Total: {len(video_blobs)} videos')
        print('=' * 60 + '\n')

    except Exception as e:
        print(f'❌ Fatal error: {str(e)}')
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    populate_marketplace()
    print('Script completed successfully!')
