"""
Script to:
1. Replace video 031 on Firebase Storage with local edited version
2. Delete video 048 from Storage and Firestore
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

LOCAL_VIDEO_PATH = Path('../video-generator-frontend/public/marketplace/videos')


def replace_video_031():
    """Replace video 031 on Firebase Storage with local edited version"""
    print('\n[1] Replacing video 031_Film_Noire_Bar_Greeting.mp4...')

    filename = '031_Film_Noire_Bar_Greeting.mp4'
    local_path = LOCAL_VIDEO_PATH / filename

    if not local_path.exists():
        print(f'  Local file not found: {local_path}')
        return False

    # Get file size for confirmation
    file_size_mb = local_path.stat().st_size / (1024 * 1024)
    print(f'  Local file size: {file_size_mb:.2f} MB')

    # Upload to Firebase Storage (overwrite existing)
    storage_path = f'marketplace/videos/{filename}'
    print(f'  Uploading to: {storage_path}')

    try:
        blob = bucket.blob(storage_path)
        blob.content_type = 'video/mp4'
        blob.upload_from_filename(str(local_path))
        blob.make_public()

        new_url = blob.public_url
        print(f'  Uploaded successfully: {new_url[:70]}...')

        # Find and update the Firestore document
        print('  Updating Firestore document...')
        docs = db.collection('marketplace_listings').where('fileName', '==', filename).get()

        if docs:
            for doc in docs:
                doc.reference.update({
                    'videoUrl': new_url,
                    'thumbnailUrl': new_url,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                print(f'  Updated Firestore document: {doc.id}')
        else:
            print('  No Firestore document found with this filename')

        return True
    except Exception as e:
        print(f'  Error: {str(e)}')
        return False


def delete_video_048():
    """Delete video 048 from Firebase Storage and Firestore"""
    print('\n[2] Deleting video 048_Spaceman_Dutch_Angle_Dramatic.mp4...')

    filename = '048_Spaceman_Dutch_Angle_Dramatic.mp4'

    # Delete from Firebase Storage
    storage_path = f'marketplace/videos/{filename}'
    print(f'  Deleting from Storage: {storage_path}')

    try:
        blob = bucket.blob(storage_path)
        if blob.exists():
            blob.delete()
            print('  Deleted from Storage successfully')
        else:
            print('  File not found in Storage (may already be deleted)')
    except Exception as e:
        print(f'  Error deleting from Storage: {str(e)}')

    # Delete from Firestore
    print('  Deleting from Firestore...')
    try:
        docs = db.collection('marketplace_listings').where('fileName', '==', filename).get()

        if docs:
            for doc in docs:
                doc.reference.delete()
                print(f'  Deleted Firestore document: {doc.id}')
        else:
            print('  No Firestore document found with this filename')

        return True
    except Exception as e:
        print(f'  Error deleting from Firestore: {str(e)}')
        return False


def main():
    print('=' * 60)
    print('Updating marketplace videos...')
    print('=' * 60)

    # Replace video 031
    success_031 = replace_video_031()

    # Delete video 048
    success_048 = delete_video_048()

    print('\n' + '=' * 60)
    print('Summary:')
    print(f'  Video 031 replacement: {"Success" if success_031 else "Failed"}')
    print(f'  Video 048 deletion: {"Success" if success_048 else "Failed"}')
    print('=' * 60)


if __name__ == '__main__':
    main()
