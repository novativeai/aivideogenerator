"""
Script to update marketplace listings with correct metadata from massive_hits_unified_prompts.json
Updates: prompts, aspect ratios, tags, durations, resolutions
"""

import os
import json
import base64
import firebase_admin
from firebase_admin import credentials, firestore
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

db = firestore.client()


def get_aspect_ratio_description(aspect_ratio):
    """Convert aspect ratio to description"""
    mapping = {
        '16:9': '16:9 (Landscape)',
        '9:16': '9:16 (Portrait)',
        '1:1': '1:1 (Square)',
        '4:3': '4:3 (Standard)',
        '21:9': '21:9 (Ultrawide)'
    }
    return mapping.get(aspect_ratio, aspect_ratio)


def update_marketplace_listings():
    """Update all marketplace listings with correct metadata"""
    print('🚀 Starting marketplace metadata update...\n')

    # Load the unified prompts JSON
    json_path = '/Users/macbook/Documents/Dev/Portfolio/SaaS & Integration/ai-video-generator/massive_hits_unified_prompts.json'

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f'❌ Could not find {json_path}')
        return
    except json.JSONDecodeError as e:
        print(f'❌ Error parsing JSON: {e}')
        return

    videos = data.get('videos', [])
    print(f'📹 Found {len(videos)} videos in unified prompts JSON\n')

    # Get all marketplace listings
    listings_ref = db.collection('marketplace_listings')
    listings = listings_ref.stream()

    updated_count = 0
    not_found_count = 0
    error_count = 0

    for listing in listings:
        listing_data = listing.to_dict()
        file_name = listing_data.get('fileName')

        if not file_name:
            print(f'⚠️  Skipping listing {listing.id} - no fileName')
            not_found_count += 1
            continue

        # Find matching video in JSON
        video_data = None
        for video in videos:
            if video['filename'] == file_name:
                video_data = video
                break

        if not video_data:
            print(f'⚠️  No metadata found for: {file_name}')
            not_found_count += 1
            continue

        print(f'\n[{updated_count + 1}] Updating: {file_name}')

        # Prepare update data
        update_data = {
            'title': video_data['title'],
            'prompt': video_data['prompt'],
            'aspectRatio': get_aspect_ratio_description(video_data['aspect_ratio']),
            'resolution': f"{video_data['width']}x{video_data['height']}",
            'duration': f"{video_data['duration']}s",
            'durationSeconds': int(video_data['duration']),
            'tags': video_data['tags'],
            'updatedAt': firestore.SERVER_TIMESTAMP
        }

        # Update description if available
        if 'source' in video_data:
            update_data['description'] = f"{video_data['prompt'][:150]}..."

        # Update use cases based on tags
        use_cases = []
        tag_list = video_data['tags']

        if any(tag in tag_list for tag in ['action', 'extreme_sports', 'tactical', 'racing']):
            use_cases.extend(['Content Creation', 'Social Media', 'Sports Marketing'])
        if any(tag in tag_list for tag in ['business', 'corporate', 'professional', 'office']):
            use_cases.extend(['Corporate Videos', 'Marketing', 'Presentations'])
        if any(tag in tag_list for tag in ['space', 'astronaut', 'sci-fi']):
            use_cases.extend(['Creative Projects', 'Film Production', 'Social Media'])
        if any(tag in tag_list for tag in ['lifestyle', 'wellness', 'family']):
            use_cases.extend(['Content Creation', 'Social Media', 'Lifestyle Marketing'])
        if any(tag in tag_list for tag in ['pov', 'first_person']):
            use_cases.extend(['Action Sports', 'Gaming', 'Immersive Content'])
        if any(tag in tag_list for tag in ['film_noir', 'vintage', 'detective']):
            use_cases.extend(['Film Production', 'Creative Projects', 'Period Content'])

        # Remove duplicates and limit to 6
        use_cases = list(dict.fromkeys(use_cases))[:6]

        # Add generic cases if none found
        if not use_cases:
            use_cases = ['Content Creation', 'Marketing', 'Social Media']

        update_data['useCases'] = use_cases

        # Determine if video has audio (based on category/type)
        category = video_data.get('category', '')
        if category in ['fast_paced_dynamic', 'ultra_epic_cinematic']:
            update_data['hasAudio'] = False  # AI-generated videos typically don't have audio
        else:
            update_data['hasAudio'] = False  # Default to false for AI videos

        # Adjust pricing based on resolution and duration
        width = video_data['width']
        duration_sec = int(video_data['duration'])

        if width >= 1920 and duration_sec >= 5:
            price = 7.99  # HD+ and 5+ seconds
        elif width >= 1440:
            price = 5.99  # HD content
        elif width == 1080 and video_data['height'] == 1920:
            price = 4.99  # Portrait/vertical
        else:
            price = 4.99  # Default

        update_data['price'] = price

        try:
            # Update the document
            listing.reference.update(update_data)

            print(f'  ✓ Title: {video_data["title"]}')
            print(f'  ✓ Aspect Ratio: {update_data["aspectRatio"]}')
            print(f'  ✓ Resolution: {update_data["resolution"]}')
            print(f'  ✓ Duration: {update_data["duration"]}')
            print(f'  ✓ Tags: {", ".join(video_data["tags"])}')
            print(f'  ✓ Use Cases: {", ".join(use_cases)}')
            print(f'  ✓ Price: €{price}')

            updated_count += 1
        except Exception as e:
            print(f'  ❌ Error updating: {str(e)}')
            error_count += 1

    print('\n' + '=' * 60)
    print('✅ Marketplace metadata update complete!')
    print(f'  - Successfully updated: {updated_count} videos')
    print(f'  - Not found in JSON: {not_found_count}')
    print(f'  - Errors: {error_count}')
    print('=' * 60 + '\n')


if __name__ == '__main__':
    update_marketplace_listings()
    print('Script completed successfully!')
