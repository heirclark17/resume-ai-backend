# AWS S3 Bucket Setup for Video Recording Feature

## Step 1: Create S3 Bucket

1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com/s3/home)
2. Click **"Create bucket"**
3. Configure bucket:
   - **Bucket name**: `talorme-recordings`
   - **AWS Region**: `us-east-1` (US East N. Virginia)
   - **Object Ownership**: ACLs disabled (recommended)
   - **Block Public Access**: Keep all 4 checkboxes **CHECKED** (we use presigned URLs, not public access)
   - **Bucket Versioning**: Disabled (optional - enable if you want version history)
   - **Encryption**: Enable server-side encryption with Amazon S3 managed keys (SSE-S3)
4. Click **"Create bucket"**

---

## Step 2: Configure CORS Policy

1. Select the newly created bucket `talorme-recordings`
2. Go to **"Permissions"** tab
3. Scroll down to **"Cross-origin resource sharing (CORS)"**
4. Click **"Edit"**
5. Paste this CORS configuration:

```json
[
    {
        "AllowedHeaders": [
            "*"
        ],
        "AllowedMethods": [
            "GET",
            "PUT",
            "POST",
            "DELETE",
            "HEAD"
        ],
        "AllowedOrigins": [
            "https://talorme.com",
            "https://www.talorme.com",
            "http://localhost:5173",
            "http://localhost:3000"
        ],
        "ExposeHeaders": [
            "ETag",
            "x-amz-request-id"
        ],
        "MaxAgeSeconds": 3000
    }
]
```

6. Click **"Save changes"**

---

## Step 3: Create IAM User with S3 Permissions

### 3a. Create IAM User

1. Go to [IAM Console](https://console.aws.amazon.com/iam/)
2. Click **"Users"** in left sidebar
3. Click **"Create user"**
4. **User name**: `talorme-s3-recordings`
5. **Do NOT** enable console access (API access only)
6. Click **"Next"**

### 3b. Set Permissions

1. Select **"Attach policies directly"**
2. **Do NOT select any AWS managed policies** (we'll create a custom policy)
3. Click **"Next"**
4. Click **"Create user"**

### 3c. Create Custom Inline Policy

1. After creating the user, click on the user name `talorme-s3-recordings`
2. Go to **"Permissions"** tab
3. Click **"Add permissions"** → **"Create inline policy"**
4. Click **"JSON"** tab
5. Paste this policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "TalormeRecordingsAccess",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::talorme-recordings/*"
        }
    ]
}
```

6. Click **"Next"**
7. **Policy name**: `TalormeS3RecordingsPolicy`
8. Click **"Create policy"**

### 3d. Create Access Keys

1. Still on the user page, go to **"Security credentials"** tab
2. Scroll down to **"Access keys"**
3. Click **"Create access key"**
4. Select **"Application running outside AWS"**
5. Click **"Next"**
6. **Description tag**: `Talorme backend production`
7. Click **"Create access key"**
8. **⚠️ IMPORTANT**: Copy both keys immediately:
   - **Access key ID**: `AKIA...` (example: `AKIAIOSFODNN7EXAMPLE`)
   - **Secret access key**: `wJalr...` (example: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)
9. Click **"Done"**

**⚠️ WARNING**: You cannot retrieve the secret access key again after closing this dialog. Save it securely now!

---

## Step 4: Add Environment Variables to Railway

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Select your `resume-ai-backend` project
3. Click on the service (backend deployment)
4. Go to **"Variables"** tab
5. Click **"+ New Variable"**
6. Add these 4 variables:

| Variable Name | Value | Example |
|---------------|-------|---------|
| `AWS_ACCESS_KEY_ID` | Your access key from Step 3d | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Your secret key from Step 3d | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_S3_BUCKET` | `talorme-recordings` | `talorme-recordings` |
| `AWS_S3_REGION` | `us-east-1` | `us-east-1` |

7. Click **"Save"** or the variables will auto-save
8. Railway will automatically redeploy your backend with the new environment variables

---

## Step 5: Verify Setup

After Railway finishes redeploying (takes ~2-3 minutes):

1. Open your web app at `https://talorme.com`
2. Log in and navigate to Interview Prep
3. Open any Behavioral/Technical question
4. Look for the **"Record Practice"** button below the STAR story
5. Click it and grant camera/microphone permissions
6. Record a short test video (5-10 seconds)
7. Stop recording → should auto-upload to S3
8. Verify playback works
9. Check AWS S3 Console → should see file in `recordings/{user_id}/{question_context}/` path

---

## Troubleshooting

### "Failed to generate upload URL" error
- Check that Railway environment variables are set correctly
- Verify IAM user has the custom policy attached
- Check Railway logs: `railway logs` or view in dashboard

### "Permission denied" error from S3
- Verify the IAM policy has `s3:PutObject` permission
- Verify the resource ARN includes `/*` at the end
- Check bucket name matches exactly: `talorme-recordings`

### CORS errors in browser console
- Verify CORS policy in S3 bucket includes your domain
- Add your domain to `AllowedOrigins` if missing
- Clear browser cache and try again

### Recording uploads but won't play back
- Check that `s3:GetObject` permission is in IAM policy
- Verify presigned URL generation in backend logs
- Test URL directly in browser (should download/play the video)

---

## Cost Estimate

**S3 Storage**: ~$0.023 per GB/month (Standard storage)
- 100 recordings × 5MB average = 500MB = **~$0.01/month**
- 1000 recordings × 5MB average = 5GB = **~$0.12/month**

**S3 Requests**:
- PUT requests: $0.005 per 1,000 requests
- GET requests: $0.0004 per 1,000 requests
- 1000 uploads + 5000 playbacks = **~$0.007/month**

**Data Transfer OUT**: First 100GB/month free, then $0.09/GB
- Typical usage under 100GB = **$0.00/month**

**Total estimated cost**: **<$0.20/month** for typical usage

---

## Security Notes

✅ **What's Secure:**
- Presigned URLs expire (15 min upload, 1 hour download)
- User ID verification prevents cross-user access
- Server-side encryption at rest (SSE-S3)
- No public bucket access (all 4 public access blocks enabled)
- IAM policy scoped to specific bucket only

⚠️ **Best Practices:**
- Rotate access keys every 90 days (set reminder)
- Enable CloudTrail logging for S3 access auditing (optional)
- Set up lifecycle policy to auto-delete old recordings (optional)
- Monitor S3 costs in AWS Cost Explorer

---

## Optional: Lifecycle Policy (Auto-delete old recordings)

To automatically delete recordings older than 90 days:

1. Go to S3 bucket → **"Management"** tab
2. Click **"Create lifecycle rule"**
3. **Rule name**: `Delete old recordings`
4. **Rule scope**: Apply to all objects in bucket
5. **Lifecycle rule actions**: Check "Expire current versions of objects"
6. **Days after object creation**: `90`
7. Click **"Create rule"**

This saves storage costs by removing practice recordings users likely won't replay after 3 months.

---

## Next Steps After Setup

1. ✅ Run database migration: `python run_video_recording_migration.py`
2. ✅ Complete this AWS setup
3. ✅ Add Railway environment variables
4. ✅ Wait for Railway redeploy (~2-3 min)
5. ✅ Test recording feature end-to-end
6. ✅ Verify S3 bucket has recordings
7. ✅ Test playback, rewind/fast-forward, delete functions

**Done!** Your video recording feature is now live in production.
