# Video Recording Feature - Quick Start Guide

## 🚀 Complete Setup in 3 Steps

### Step 1: Database Migration (2 minutes)

Run this command in terminal:

```bash
cd C:\Users\derri\resume-ai-backend
railway login
railway link  # Select your resume-ai-backend project
railway run python run_video_recording_migration.py
```

**Expected output:**
```
✓ Connected successfully
✓ Found star_stories table
✓ Added video_recording_url column
✓ Created index
✓ MIGRATION COMPLETED SUCCESSFULLY
```

**Alternative** (if Railway CLI issues):
- Double-click: `COMPLETE_VIDEO_SETUP.bat`

---

### Step 2: AWS S3 Bucket Setup (10 minutes)

**Open and follow**: `AWS_S3_SETUP.md`

Quick checklist:
- [ ] Create bucket: `talorme-recordings` in `us-east-1`
- [ ] Add CORS policy (copy from guide)
- [ ] Create IAM user: `talorme-s3-recordings`
- [ ] Attach custom S3 policy (copy from guide)
- [ ] Create access keys → **SAVE THEM!**
- [ ] Add 4 env vars to Railway:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_S3_BUCKET=talorme-recordings`
  - `AWS_S3_REGION=us-east-1`

---

### Step 3: Test (5 minutes)

After Railway redeploys:

1. Go to https://talorme.com
2. Login → Interview Prep
3. Open any Behavioral/Technical question
4. Click **"Record Practice"** button
5. Grant camera/mic permissions
6. Record 10-second test video
7. Verify:
   - ✅ Recording stops and shows progress bar
   - ✅ Playback controls appear (play, rewind, fast-forward)
   - ✅ Video plays back correctly
   - ✅ Delete button works
8. Check AWS S3 Console:
   - Should see file in `recordings/{user_id}/{question_context}/`

---

## ✅ Success Criteria

- [x] All code implemented (DONE - 100%)
- [ ] Database migration completed
- [ ] AWS S3 bucket created
- [ ] AWS credentials added to Railway
- [ ] Test recording works end-to-end

---

## 📁 Reference Files

| File | Purpose |
|------|---------|
| `QUICK_START.md` | **This file** - Overview |
| `RUN_VIDEO_MIGRATION.md` | Detailed migration instructions |
| `AWS_S3_SETUP.md` | **Complete AWS setup guide** |
| `COMPLETE_VIDEO_SETUP.bat` | One-click migration script |
| `run_video_recording_migration.py` | Migration script (runs automatically) |

---

## 🆘 Need Help?

### Migration Issues
→ See `RUN_VIDEO_MIGRATION.md` troubleshooting section

### AWS Setup Issues
→ See `AWS_S3_SETUP.md` troubleshooting section

### After everything is set up but recording fails
1. Check Railway logs: `railway logs`
2. Check browser console (F12 → Console tab)
3. Verify AWS env vars are set in Railway dashboard
4. Test S3 connection:
   ```bash
   railway run python -c "from app.services.s3_service import _get_s3_client; _get_s3_client(); print('✓ S3 OK')"
   ```

---

## 💰 Cost

**Total monthly cost**: ~$0.20 (see AWS_S3_SETUP.md for breakdown)

---

## ⏱️ Time Estimate

- **Database migration**: 2 minutes
- **AWS S3 setup**: 10 minutes (first time)
- **Railway deployment**: 2-3 minutes (automatic)
- **Testing**: 5 minutes

**Total**: ~20 minutes

---

## 🎯 What You're Getting

✅ Video recording in 3 locations:
- Behavioral/Technical Questions (20 questions)
- Common Interview Questions (12 questions)
- STAR Story Builder (Candidate Positioning)

✅ Full playback controls:
- Play/Pause
- Rewind 10 seconds
- Fast-forward 10 seconds
- Seek bar (click to jump)
- Timer display
- Delete with confirmation

✅ Audio-only mode option

✅ Automatic S3 upload with progress

✅ Persistent storage (recordings survive refresh)

✅ Secure presigned URLs (15-min upload, 1-hour playback)

---

Ready? Start with **Step 1** above! 🚀
