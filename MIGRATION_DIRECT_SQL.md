# Run Migration Using Railway SQL Console

Since Railway CLI is having connection issues, use the Railway dashboard SQL console instead.

## Steps:

1. Go to https://railway.app/dashboard
2. Select your **resume-ai-backend** project
3. Click on the **PostgreSQL** service
4. Click the **"Data"** tab
5. Click the **"Query"** button (or SQL console)
6. Copy and paste this SQL:

```sql
-- Add video_recording_url column to star_stories table
ALTER TABLE star_stories ADD COLUMN IF NOT EXISTS video_recording_url TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_star_stories_video_recording_url
ON star_stories(video_recording_url)
WHERE video_recording_url IS NOT NULL;

-- Verify the column was added
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'star_stories'
AND column_name = 'video_recording_url';
```

7. Click **"Run"** or **"Execute"**

## Expected Output:

You should see a result showing:

| column_name | data_type | is_nullable |
|-------------|-----------|-------------|
| video_recording_url | text | YES |

## Success Message:

If you see the column information above, the migration is complete! ✓

## Next Steps:

After successful migration, verify everything works:

```bash
railway run python VERIFY_SETUP.py
```

Or test directly at: https://talorme.com
