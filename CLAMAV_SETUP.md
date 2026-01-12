# ClamAV Virus Scanning Setup Guide

## Overview

ClamAV is an open-source antivirus engine for detecting trojans, viruses, malware, and other malicious threats. This guide explains how to set up ClamAV for the Resume AI application.

---

## Railway Deployment (Recommended Approach)

### Option 1: Using Railway's Nixpacks

Railway uses Nixpacks for builds. You can add ClamAV as a system dependency.

#### 1. Create nixpacks.toml

Create `backend/nixpacks.toml`:

```toml
[phases.setup]
nixPkgs = ["python39", "clamav"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "freshclam --quiet && clamd && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

#### 2. Update Railway Build Command

In Railway dashboard:
- Go to Settings → Build
- Add build command: `freshclam --quiet`

**Note:** Railway's ephemeral filesystem means virus databases will download on each deployment (~150MB). This adds build time but ensures latest signatures.

---

### Option 2: Using Docker (Best for Production)

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.9-slim

# Install ClamAV and dependencies
RUN apt-get update && apt-get install -y \
    clamav \
    clamav-daemon \
    clamav-freshclam \
    && rm -rf /var/lib/apt/lists/*

# Create directory for virus definitions
RUN mkdir -p /var/lib/clamav

# Update virus definitions
RUN freshclam --quiet || true

# Create app directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start ClamAV daemon and application
CMD clamd && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Deploy to Railway using Docker:
```bash
railway up --dockerfile backend/Dockerfile
```

---

### Option 3: External ClamAV Service (Scalable)

Use a dedicated ClamAV service like:

1. **ClamAV REST API** (self-hosted)
2. **VirusTotal API** (commercial, 500 requests/day free)
3. **MetaDefender Cloud** (commercial)

Update `virus_scanner.py` to call external API instead of local ClamAV.

---

## Local Development Setup

### Linux (Debian/Ubuntu)

```bash
# Install ClamAV
sudo apt-get update
sudo apt-get install -y clamav clamav-daemon

# Update virus definitions
sudo freshclam

# Start ClamAV daemon
sudo systemctl start clamav-daemon
sudo systemctl enable clamav-daemon

# Verify installation
clamscan --version
```

### macOS

```bash
# Install via Homebrew
brew install clamav

# Update virus definitions
freshclam

# Start ClamAV daemon (optional)
clamd

# Verify installation
clamscan --version
```

### Windows

1. Download ClamAV from: https://www.clamav.net/downloads
2. Extract to `C:\Program Files\ClamAV`
3. Add to PATH: `C:\Program Files\ClamAV`
4. Update definitions:
   ```cmd
   freshclam.exe
   ```
5. Verify:
   ```cmd
   clamscan.exe --version
   ```

---

## Configuration

### ClamAV Daemon Configuration

Edit `/etc/clamav/clamd.conf` (Linux) or `clamd.conf`:

```ini
# Logging
LogFile /var/log/clamav/clamd.log
LogTime yes
LogFileMaxSize 2M
LogRotate yes

# Performance
MaxThreads 12
MaxConnectionQueueLength 200
StreamMaxLength 25M
MaxFileSize 25000000

# Scanning options
DetectPUA yes
ScanPE yes
ScanELF yes
ScanOLE2 yes
ScanPDF yes
ScanSWF yes
ScanXMLDOCS yes
ScanHWP3 yes

# Archive scanning
ScanArchive yes
MaxScanSize 100M
MaxFiles 10000
MaxRecursion 16
MaxFileSize 25M
```

### Freshclam Configuration

Edit `/etc/clamav/freshclam.conf`:

```ini
# Update mirror
DatabaseMirror database.clamav.net

# Update frequency
Checks 24

# Logging
UpdateLogFile /var/log/clamav/freshclam.log
LogTime yes
```

---

## Testing ClamAV Integration

### Test with EICAR File

The EICAR test file is a standard antivirus test signature:

```python
# Create test file
with open('eicar_test.txt', 'w') as f:
    f.write('X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*')

# Test scan
from app.utils.virus_scanner import VirusScanner

scanner = VirusScanner()
is_safe, threat = scanner.scan_file('eicar_test.txt')

print(f"Safe: {is_safe}")
print(f"Threat: {threat}")
# Expected output: Safe: False, Threat: "Eicar-Signature"
```

### Test API Endpoint

```bash
# Upload EICAR test file
curl -X POST "http://localhost:8000/api/resumes/upload" \
  -H "X-API-Key: your_api_key" \
  -F "file=@eicar_test.txt"

# Expected: HTTP 400 with "File rejected: Potential threat detected"
```

---

## Monitoring and Maintenance

### Check ClamAV Status

```bash
# Check daemon status
sudo systemctl status clamav-daemon

# Check freshclam status
sudo systemctl status clamav-freshclam

# Check virus database version
sigtool --info /var/lib/clamav/main.cvd
```

### Update Virus Definitions

ClamAV updates automatically via freshclam daemon. Manual update:

```bash
sudo freshclam
```

### Check Logs

```bash
# ClamAV daemon logs
sudo tail -f /var/log/clamav/clamd.log

# Freshclam update logs
sudo tail -f /var/log/clamav/freshclam.log

# Application logs (if file was rejected)
tail -f logs/resume_ai.log | grep "Virus Scanner"
```

---

## Performance Optimization

### Memory Usage

ClamAV daemon uses ~200-500MB RAM. For Railway's free tier (512MB), this may be tight.

**Solutions:**
1. Use on-demand scanning (no daemon):
   ```python
   subprocess.run(['clamscan', '--no-summary', file_path])
   ```

2. Limit file sizes:
   ```python
   # Already implemented in virus_scanner.py
   max_size = 100 * 1024 * 1024  # 100MB
   ```

3. Use external ClamAV service

### Scanning Speed

- Small files (<1MB): ~100ms
- Medium files (1-10MB): ~500ms
- Large files (10-100MB): ~2-5s

**Optimization:**
- Scan in background after upload
- Use asyncio for non-blocking scans
- Implement scan queue for high traffic

---

## Fallback Strategy

The application already implements graceful fallback:

```python
class VirusScanner:
    def __init__(self):
        self.clamav_available = self._check_clamav_availability()

        if not self.clamav_available:
            # Falls back to basic validation:
            # - File size limits
            # - Executable signature detection
            # - EICAR test file detection
```

This ensures the application works even without ClamAV installed.

---

## Security Best Practices

1. **Keep Definitions Updated:**
   - Enable automatic updates via freshclam
   - New signatures released 3-4 times daily

2. **Scan Before Encryption:**
   - Already implemented in file_handler.py
   - Infected files deleted immediately

3. **Quarantine Suspicious Files:**
   - Consider moving to quarantine folder instead of deleting
   - Allows manual review if false positive

4. **Monitor False Positives:**
   - Legitimate files sometimes flagged
   - Log all detections for review

5. **Multiple Scan Engines:**
   - Consider VirusTotal API for second opinion
   - Upload file hash (not file) for privacy

---

## Cost Analysis

### Self-Hosted ClamAV

| Item | Cost |
|------|------|
| Server RAM | +200-500MB |
| Bandwidth | ~150MB per update (24 updates/day) |
| Storage | ~300MB for virus definitions |
| **Total** | Infrastructure costs only |

### External Services

| Service | Free Tier | Paid Plans |
|---------|-----------|------------|
| VirusTotal API | 500 requests/day | $0.05 per request |
| MetaDefender Cloud | 100 requests/day | $199/month |
| ClamAV REST API | Self-hosted | Infrastructure costs |

---

## Troubleshooting

### Error: "ClamAV not available"

**Check installation:**
```bash
which clamscan
# Should output: /usr/bin/clamscan
```

**If not installed, see installation instructions above.**

### Error: "Scan timeout"

**Cause:** Large file or slow scan

**Solution:**
```python
# Increase timeout in virus_scanner.py
timeout=60  # Increase from 30 to 60 seconds
```

### Error: "Can't connect to clamd"

**Cause:** ClamAV daemon not running

**Solution:**
```bash
sudo systemctl start clamav-daemon
```

### Error: "Database is older than 7 days"

**Cause:** Freshclam not updating

**Solution:**
```bash
sudo freshclam
sudo systemctl restart clamav-daemon
```

---

## Production Checklist

- [ ] ClamAV installed and running
- [ ] Virus definitions updated (freshclam)
- [ ] Daemon configured (clamd.conf)
- [ ] Automatic updates enabled (freshclam daemon)
- [ ] Test with EICAR file passed
- [ ] Logs configured and rotating
- [ ] Monitoring alerts set up
- [ ] Fallback strategy tested
- [ ] Performance benchmarks run
- [ ] Documentation updated

---

## Additional Resources

- **ClamAV Documentation:** https://docs.clamav.net/
- **ClamAV GitHub:** https://github.com/Cisco-Talos/clamav
- **EICAR Test File:** https://www.eicar.org/
- **VirusTotal API:** https://developers.virustotal.com/
- **Railway Nixpacks:** https://nixpacks.com/

---

**Status:** Optional Enhancement - Recommended for Production

**Last Updated:** 2026-01-11
