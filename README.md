# Resume AI Backend

FastAPI backend for Resume AI application - handles resume tailoring with OpenAI GPT-4o and Perplexity research.

## Features

- **Resume Tailoring**: Customizes resumes for specific companies and job postings
- **AI-Powered Research**: Uses Perplexity AI to research companies
- **Resume Generation**: Tailors resume content with OpenAI GPT-4o
- **DOCX Generation**: Creates formatted Word documents
- **Database**: Stores base resumes, tailored resumes, jobs, and company research

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL (production) / SQLite (local development)
- **ORM**: SQLAlchemy with async support
- **AI Services**: OpenAI GPT-4o, Perplexity AI
- **Document Generation**: python-docx

## Local Development

### Prerequisites

- Python 3.10+
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/resume-ai-backend.git
cd resume-ai-backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```env
# AI API Keys
OPENAI_API_KEY=your_openai_api_key
PERPLEXITY_API_KEY=your_perplexity_api_key

# Test Mode (set to true to use mock data)
TEST_MODE=false

# Database (leave blank for auto-detect: PostgreSQL on Railway, SQLite locally)
# DATABASE_URL=

# File Storage
UPLOAD_DIR=./uploads
RESUMES_DIR=./resumes

# App Settings
APP_NAME=ResumeAI
APP_VERSION=1.0.0
DEBUG=true

# API Settings (Railway will override with $PORT)
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

5. Run the development server:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

6. API will be available at `http://127.0.0.1:8000`
   - Docs: `http://127.0.0.1:8000/docs`
   - Health check: `http://127.0.0.1:8000/health`

## Railway Deployment

### Prerequisites

- Railway account: https://railway.app
- GitHub repository

### Deployment Steps

1. **Push to GitHub**:
```bash
cd backend
git init
git add .
git commit -m "Initial backend commit"
git remote add origin https://github.com/YOUR_USERNAME/resume-ai-backend.git
git branch -M main
git push -u origin main
```

2. **Create Railway Project**:
   - Go to https://railway.app
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `resume-ai-backend` repository
   - Railway will auto-detect the Python app

3. **Add PostgreSQL Database**:
   - In your Railway project, click "+ New"
   - Select "Database" → "PostgreSQL"
   - Railway will automatically set the `DATABASE_URL` environment variable

4. **Configure Environment Variables**:
   - Go to your service → "Variables" tab
   - Add these variables:
     ```
     OPENAI_API_KEY=your_actual_openai_key
     PERPLEXITY_API_KEY=your_actual_perplexity_key
     TEST_MODE=false
     ```
   - Railway will automatically provide: `DATABASE_URL`, `PORT`

5. **Deploy**:
   - Railway will automatically build and deploy
   - Your API will be available at the Railway-provided URL (e.g., `https://your-app.railway.app`)

6. **Verify Deployment**:
   - Visit `https://your-app.railway.app/health`
   - Should return: `{"status": "healthy", "version": "1.0.0", ...}`
   - Check logs in Railway dashboard for any errors

### Database Migrations

Railway automatically runs the database initialization on startup (see `app/database.py`). Tables are created automatically on first run.

To reset the database:
- Delete the PostgreSQL service in Railway
- Create a new PostgreSQL service
- Redeploy the backend

## API Endpoints

### Health & Info

- `GET /` - Root endpoint with app info
- `GET /health` - Health check endpoint

### Resumes

- `POST /api/resumes/upload` - Upload a base resume
- `GET /api/resumes/list` - List all base resumes
- `GET /api/resumes/{resume_id}` - Get specific resume
- `DELETE /api/resumes/{resume_id}` - Delete resume

### Tailoring

- `POST /api/tailor/tailor` - Tailor a resume for a job
  ```json
  {
    "base_resume_id": 1,
    "job_url": "https://...",
    "company": "Microsoft",
    "job_title": "Senior Security Program Manager",
    "job_description": "..."
  }
  ```
- `GET /api/tailor/tailored/{tailored_id}` - Get tailored resume
- `GET /api/tailor/list` - List all tailored resumes

## Architecture

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings (auto-detects Railway vs local)
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   │   ├── resume.py
│   │   ├── job.py
│   │   └── company.py
│   ├── routes/              # API endpoints
│   │   ├── resumes.py
│   │   └── tailoring.py
│   └── services/            # Business logic
│       ├── perplexity_client.py
│       ├── openai_tailor.py
│       └── docx_generator.py
├── .env                     # Local environment variables (not in git)
├── .env.example             # Example environment variables
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── railway.json             # Railway deployment config
└── README.md               # This file
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key (for GPT-4o) |
| `PERPLEXITY_API_KEY` | Yes | - | Perplexity AI API key |
| `TEST_MODE` | No | `false` | Use mock data instead of real APIs |
| `DATABASE_URL` | No | Auto-detect | PostgreSQL URL (Railway provides this) |
| `PORT` | No | `8000` | Server port (Railway provides this) |
| `BACKEND_HOST` | No | `0.0.0.0` | Server host |
| `DEBUG` | No | `true` | Debug mode |

## Troubleshooting

### Local Development

**Database errors**:
- Ensure `database/` directory exists
- Delete `database/resume_ai.db` to reset local database

**Import errors**:
- Activate virtual environment: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Railway Deployment

**Build failures**:
- Check Railway build logs
- Ensure all dependencies are in `requirements.txt`
- Verify Python version compatibility

**Runtime errors**:
- Check Railway deployment logs
- Verify environment variables are set correctly
- Ensure PostgreSQL database is connected

**Database connection errors**:
- Verify PostgreSQL service is running
- Check that `DATABASE_URL` is automatically set
- Railway format: `postgres://user:pass@host:port/dbname`

## Test Mode

Set `TEST_MODE=true` to use mock AI responses without calling real APIs:

- Mock company research from Perplexity
- Mock resume tailoring from OpenAI
- Useful for testing without API costs

## License

MIT License

## Support

For issues, please create a GitHub issue or contact the maintainer.
