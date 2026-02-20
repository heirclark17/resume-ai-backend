-- Add video_recording_url column to star_stories table for practice recording storage
ALTER TABLE star_stories ADD COLUMN IF NOT EXISTS video_recording_url TEXT;

-- Create index for faster lookups by recording URL
CREATE INDEX IF NOT EXISTS idx_star_stories_video_recording_url
ON star_stories(video_recording_url)
WHERE video_recording_url IS NOT NULL;
