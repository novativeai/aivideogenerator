/**
 * Script to populate marketplace with videos from Firebase Storage
 * Extracts metadata, generates tags, and creates Firestore documents
 */

const admin = require('firebase-admin');
const path = require('path');
const fs = require('fs');

// Load environment variables
require('dotenv').config();

// Initialize Firebase Admin SDK
const serviceAccountBase64 = process.env.FIREBASE_SERVICE_ACCOUNT_BASE64;
if (!serviceAccountBase64) {
  console.error('FIREBASE_SERVICE_ACCOUNT_BASE64 not found in .env');
  process.exit(1);
}

const serviceAccountJson = Buffer.from(serviceAccountBase64, 'base64').toString('utf-8');
const serviceAccount = JSON.parse(serviceAccountJson);

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  storageBucket: process.env.FIREBASE_STORAGE_BUCKET || 'reelzila.firebasestorage.app'
});

const bucket = admin.storage().bucket();
const db = admin.firestore();

/**
 * Parse video filename to extract meaningful information
 * @param {string} filename - The video filename
 * @returns {object} Parsed data including title, tags, and use cases
 */
function parseFilename(filename) {
  // Remove file extension and replace separators with spaces
  const nameWithoutExt = filename.replace(/\.(mp4|mov|avi|webm)$/i, '');

  // Replace common separators with spaces
  let cleanName = nameWithoutExt
    .replace(/[-_]/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2') // Handle camelCase
    .toLowerCase();

  // Extract potential keywords for tags
  const words = cleanName.split(/\s+/).filter(w => w.length > 2);

  // Common video categories and their associated tags
  const categoryMap = {
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
    'slow motion': ['slow motion', 'slo mo', 'cinematic'],
    'time lapse': ['time lapse', 'timelapse', 'fast motion'],
    'night': ['night', 'evening', 'dark', 'nighttime'],
    'day': ['day', 'daytime', 'bright', 'sunny'],
    'rain': ['rain', 'weather', 'wet', 'storm'],
    'snow': ['snow', 'winter', 'cold', 'white'],
    'fire': ['fire', 'flame', 'heat', 'burning'],
    'water': ['water', 'liquid', 'fluid', 'aqua'],
    'sky': ['sky', 'clouds', 'atmosphere', 'aerial']
  };

  // Use case mapping based on content
  const useCaseMap = {
    'nature': ['Content Creation', 'Marketing', 'Background', 'Social Media'],
    'city': ['Marketing', 'Real Estate', 'Travel', 'Background'],
    'business': ['Corporate Videos', 'Marketing', 'Presentations'],
    'food': ['Restaurant Marketing', 'Content Creation', 'Social Media'],
    'technology': ['Tech Reviews', 'Marketing', 'Presentations'],
    'abstract': ['Background', 'Transitions', 'Creative Projects'],
    'aerial': ['Real Estate', 'Travel', 'Marketing', 'Documentaries']
  };

  // Generate title (capitalize first letter of each word)
  const title = words
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

  // Generate tags based on keywords found
  const tags = new Set(['stock footage', 'video clip']);
  const useCases = new Set();

  words.forEach(word => {
    // Check if word matches any category
    Object.keys(categoryMap).forEach(category => {
      if (word.includes(category) || category.includes(word)) {
        categoryMap[category].forEach(tag => tags.add(tag));
        if (useCaseMap[category]) {
          useCaseMap[category].forEach(uc => useCases.add(uc));
        }
      }
    });
  });

  // Add generic use cases if none found
  if (useCases.size === 0) {
    ['Content Creation', 'Marketing', 'Background', 'Social Media'].forEach(uc => useCases.add(uc));
  }

  // Generate description
  const description = `High-quality ${title.toLowerCase()} stock footage perfect for your creative projects. This video can be used for content creation, marketing campaigns, social media posts, and more.`;

  return {
    title: title || 'Stock Video Footage',
    tags: Array.from(tags).slice(0, 10), // Limit to 10 tags
    useCases: Array.from(useCases).slice(0, 6), // Limit to 6 use cases
    description
  };
}

/**
 * Determine aspect ratio from video dimensions
 * @param {number} width - Video width
 * @param {number} height - Video height
 * @returns {string} Aspect ratio description
 */
function getAspectRatio(width, height) {
  if (!width || !height) return 'Unknown';

  const ratio = width / height;

  if (Math.abs(ratio - 16/9) < 0.1) return '16:9 (Landscape)';
  if (Math.abs(ratio - 9/16) < 0.1) return '9:16 (Portrait)';
  if (Math.abs(ratio - 1) < 0.1) return '1:1 (Square)';
  if (Math.abs(ratio - 4/3) < 0.1) return '4:3 (Standard)';
  if (Math.abs(ratio - 21/9) < 0.1) return '21:9 (Ultrawide)';

  return `${width}x${height}`;
}

/**
 * Format duration from seconds to readable string
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration
 */
function formatDuration(seconds) {
  if (!seconds) return 'Unknown';

  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);

  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

/**
 * Get video metadata from Firebase Storage
 * @param {string} filePath - Path to video file in storage
 * @returns {object} Video metadata
 */
async function getVideoMetadata(filePath) {
  try {
    const file = bucket.file(filePath);
    const [metadata] = await file.getMetadata();

    // Get public URL
    const [url] = await file.getSignedUrl({
      action: 'read',
      expires: '03-01-2500' // Far future date for marketplace videos
    });

    // Extract custom metadata if available
    const customMetadata = metadata.metadata || {};

    return {
      url,
      size: metadata.size,
      contentType: metadata.contentType,
      timeCreated: metadata.timeCreated,
      width: customMetadata.width ? parseInt(customMetadata.width) : null,
      height: customMetadata.height ? parseInt(customMetadata.height) : null,
      duration: customMetadata.duration ? parseFloat(customMetadata.duration) : null,
      hasAudio: customMetadata.hasAudio === 'true' || customMetadata.hasAudio === true
    };
  } catch (error) {
    console.error(`Error getting metadata for ${filePath}:`, error.message);
    return null;
  }
}

/**
 * Create or update marketplace listing in Firestore
 * @param {object} videoData - Processed video data
 */
async function createMarketplaceListing(videoData) {
  try {
    const listingRef = db.collection('marketplace_listings').doc();

    const listing = {
      id: listingRef.id,
      sellerId: 'admin', // Platform curated content
      sellerName: 'Reelzila',
      title: videoData.title,
      description: videoData.description,
      videoUrl: videoData.url,
      generationId: 'imported', // Imported from storage
      prompt: videoData.title.toLowerCase(), // Use title as prompt
      price: videoData.price || 4.99, // Default price €4.99
      tags: videoData.tags,
      hasAudio: videoData.hasAudio,
      useCases: videoData.useCases,
      thumbnailUrl: videoData.url, // Use video URL as thumbnail (can be improved)
      status: 'published',
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
      sold: 0,
      // Additional metadata for search/filter
      aspectRatio: videoData.aspectRatio,
      duration: videoData.duration,
      durationSeconds: videoData.durationSeconds,
      resolution: videoData.resolution,
      fileSize: videoData.fileSize,
      fileName: videoData.fileName
    };

    await listingRef.set(listing);
    console.log(`✓ Created listing: ${videoData.title} (${videoData.fileName})`);

    return listing;
  } catch (error) {
    console.error(`Error creating listing for ${videoData.fileName}:`, error.message);
    return null;
  }
}

/**
 * Main function to process all videos
 */
async function populateMarketplace() {
  console.log('🚀 Starting marketplace population...\n');

  try {
    // List all video files in storage
    const [files] = await bucket.getFiles();

    // Filter video files
    const videoFiles = files.filter(file => {
      const ext = path.extname(file.name).toLowerCase();
      return ['.mp4', '.mov', '.avi', '.webm'].includes(ext);
    });

    console.log(`📹 Found ${videoFiles.length} video files in storage\n`);

    if (videoFiles.length === 0) {
      console.log('No video files found. Make sure videos are uploaded to Firebase Storage.');
      return;
    }

    // Process each video
    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < videoFiles.length; i++) {
      const file = videoFiles[i];
      const fileName = path.basename(file.name);

      console.log(`\n[${i + 1}/${videoFiles.length}] Processing: ${fileName}`);

      // Get metadata from storage
      const metadata = await getVideoMetadata(file.name);

      if (!metadata) {
        console.log(`  ⚠️  Skipping - could not get metadata`);
        errorCount++;
        continue;
      }

      // Parse filename to extract information
      const parsed = parseFilename(fileName);

      // Determine pricing based on video characteristics
      let price = 4.99; // Default
      if (metadata.duration && metadata.duration > 30) price = 7.99; // Longer videos
      if (metadata.width && metadata.width >= 3840) price = 9.99; // 4K videos

      // Combine all data
      const videoData = {
        fileName,
        url: metadata.url,
        title: parsed.title,
        description: parsed.description,
        tags: parsed.tags,
        useCases: parsed.useCases,
        hasAudio: metadata.hasAudio,
        aspectRatio: getAspectRatio(metadata.width, metadata.height),
        duration: formatDuration(metadata.duration),
        durationSeconds: metadata.duration,
        resolution: metadata.width && metadata.height ? `${metadata.width}x${metadata.height}` : 'Unknown',
        fileSize: `${(metadata.size / (1024 * 1024)).toFixed(2)} MB`,
        price
      };

      // Log extracted info
      console.log(`  📝 Title: ${videoData.title}`);
      console.log(`  🏷️  Tags: ${videoData.tags.join(', ')}`);
      console.log(`  📊 Aspect Ratio: ${videoData.aspectRatio}`);
      console.log(`  ⏱️  Duration: ${videoData.duration}`);
      console.log(`  📐 Resolution: ${videoData.resolution}`);
      console.log(`  🔊 Audio: ${videoData.hasAudio ? 'Yes' : 'No'}`);
      console.log(`  💰 Price: €${videoData.price}`);

      // Create listing in Firestore
      const listing = await createMarketplaceListing(videoData);

      if (listing) {
        successCount++;
      } else {
        errorCount++;
      }

      // Small delay to avoid rate limiting
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    console.log('\n' + '='.repeat(60));
    console.log('✅ Marketplace population complete!');
    console.log(`  - Successfully processed: ${successCount} videos`);
    console.log(`  - Errors: ${errorCount}`);
    console.log(`  - Total: ${videoFiles.length} videos`);
    console.log('='.repeat(60) + '\n');

  } catch (error) {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  }
}

// Run the script
populateMarketplace()
  .then(() => {
    console.log('Script completed successfully!');
    process.exit(0);
  })
  .catch(error => {
    console.error('Script failed:', error);
    process.exit(1);
  });
