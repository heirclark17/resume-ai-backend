# Run Video Recording Database Migration

## Quick Start (Recommended)

### Option 1: Using Railway CLI (Easiest)

1. **Install Railway CLI** (if not already installed):
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway**:
   ```bash
   railway login
   ```

3. **Link to your project**:
   ```bash
   cd C:\Users\derri\resume-ai-backend
   railway link
   ```
   Select your `resume-ai-backend` project when prompted.

4. **Run migration with Railway database**:
   ```bash
   railway run python run_video_recording_migration.py
   ```

   This automatically uses your Railway PostgreSQL DATABASE_URL.

---

### Option 2: Manual with DATABASE_URL

1. **Get DATABASE_URL from Railway**:
   - Go to https://railway.app/dashboard
   - Select your backend project
   - Click on **PostgreSQL** service
   - Go to **"Variables"** tab
   - Copy the `DATABASE_URL` value (starts with `postgresql://...`)

2. **Set environment variable** (Windows):
   ```bash
   set DATABASE_URL=postgresql://postgres:...@...railway.app:5432/railway
   ```

   Or (PowerShell):
   ```powershell
   $env:DATABASE_URL="postgresql://postgres:...@...railway.app:5432/railway"
   ```

3. **Run migration**:
   ```bash
   cd C:\Users\derri\resume-ai-backend
   python run_video_recording_migration.py
   ```

---

### Option 3: Direct SQL in Railway Dashboard

If you prefer to run SQL directly:

1. Go to Railway Dashboard → PostgreSQL service
2. Click **"Data"** tab
3. Click **"Query"** button
4. Paste this SQL:
   ```sql
   -- Add video_recording_url column
   ALTER TABLE star_stories ADD COLUMN IF NOT EXISTS video_recording_url TEXT;

   -- Create index for faster lookups
   CREATE INDEX IF NOT EXISTS idx_star_stories_video_recording_url
   ON star_stories(video_recording_url)
   WHERE video_recording_url IS NOT NULL;

   -- Verify column was added
   SELECT column_name, data_type, is_nullable
   FROM information_schema.columns
   WHERE table_name = 'star_stories'
   AND column_name = 'video_recording_url';
   ```
5. Click **"Run"**
6. Verify you see output showing the new column

---

## Expected Output (Success)

```
Starting video recording migration...
Connecting to database...
✓ Connected successfully

Checking if star_stories table exists...
✓ Found star_stories table

Checking if video_recording_url column exists...

Adding video_recording_url column...
✓ Added video_recording_url column

Creating index on video_recording_url...
✓ Created index

Verifying migration...
✓ Column verified: video_recording_url (text, nullable=YES)

============================================================
✓ MIGRATION COMPLETED SUCCESSFULLY
============================================================

Next steps:
1. Set up AWS S3 bucket (see AWS_S3_SETUP.md)
2. Add AWS environment variables to Railway
3. Test video recording feature
```

---

## Troubleshooting

### Error: "psycopg2 not installed"
```bash
pip install psycopg2-binary
```
Then run migration again.

### Error: "DATABASE_URL not set"
- Make sure you're using `railway run` command (Option 1)
- OR verify you set the environment variable correctly (Option 2)
- OR use the Railway dashboard SQL query option (Option 3)

### Error: "Failed to connect to database"
- Verify your DATABASE_URL is correct
- Check Railway PostgreSQL service is running
- Try copying the DATABASE_URL again from Railway dashboard

### "Column already exists - skipping"
✅ This is fine! The migration script is idempotent (safe to run multiple times).

---

## After Migration Completes

1. ✅ Migration done
2. ⏭️ **Next**: Follow `AWS_S3_SETUP.md` to create S3 bucket
3. ⏭️ Add AWS environment variables to Railway
4. ⏭️ Test video recording feature

---

## Quick Test Command (After AWS Setup)

Verify everything works:

```bash
# Test S3 connection from backend
railway run python -c "from app.services.s3_service import _get_s3_client; client = _get_s3_client(); print('✓ S3 client initialized successfully')"
```

If no errors → AWS credentials are configured correctly! 🎉
