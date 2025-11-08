# SkillSense Backend API

AI-powered talent identification system - Input Layer API for CV processing and data extraction.

## Overview

The SkillSense Backend is a FastAPI-based REST API that handles:
- CV file uploads (PDF, DOCX, TXT)
- Automated data extraction using regex and NLP
- Confidence scoring for extracted information
- User validation and editing of extracted data
- Admin dashboard for monitoring and management

## Technology Stack

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL 15+ (Supabase)
- **ORM**: SQLAlchemy 2.0
- **CV Parsing**: PyPDF2, pdfplumber, python-docx
- **NLP**: spaCy (planned for Phase 2)
- **Authentication**: JWT tokens with bcrypt password hashing
- **Validation**: Pydantic v2

## Project Structure

```
skillsense-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   ├── database.py                # Database connection and session
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── cv_submission.py
│   │   └── extracted_data.py
│   ├── schemas/                   # Pydantic validation schemas
│   │   ├── user.py
│   │   ├── cv_submission.py
│   │   └── extracted_data.py
│   ├── api/                       # API route handlers
│   │   ├── auth.py                # Authentication endpoints
│   │   ├── cv_upload.py           # CV upload endpoints
│   │   ├── extraction.py          # Extraction data endpoints
│   │   └── admin.py               # Admin endpoints
│   ├── services/                  # Business logic services
│   │   ├── cv_parser.py           # PDF/DOCX/TXT parsing
│   │   ├── extractor.py           # Data extraction logic
│   │   └── link_validator.py     # URL validation
│   ├── utils/                     # Utility functions
│   │   ├── security.py            # Password hashing, JWT
│   │   └── file_handler.py       # File upload/storage
│   └── core/                      # Core dependencies
│       └── dependencies.py        # FastAPI dependencies
├── sql/                           # SQL scripts
│   └── init_db.sql                # Database initialization
├── uploads/                       # Uploaded CV files storage
├── tests/                         # Test files
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 15+ OR Supabase account
- pip (Python package manager)

### 1. Clone Repository

```bash
cd skillsense-backend
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Download spaCy Language Model

```bash
python -m spacy download en_core_web_sm
```

### 5. Set Up Database (Supabase)

1. Create a Supabase project at https://supabase.com
2. Go to SQL Editor in your Supabase dashboard
3. Run the SQL script from `sql/init_db.sql`
4. Note your database connection string from Project Settings > Database

### 6. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and update the following:

```env
# Your Supabase connection string
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres

# Generate a secure random secret key (32+ characters)
SECRET_KEY=your-super-secret-key-min-32-characters-long

# Optional: Update admin credentials
ADMIN_EMAIL=admin@skillsense.com
ADMIN_PASSWORD=your-secure-password
```

**Generate a secure SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 7. Run the Application

**Development mode with auto-reload:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production mode:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## API Documentation

### Authentication Endpoints

#### Register User
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe"
}
```

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1...",
  "token_type": "bearer"
}
```

#### Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer {token}
```

### CV Upload Endpoints

#### Upload CV
```http
POST /api/v1/cv/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

Form Data:
- file: [CV file - PDF/DOCX/TXT, max 10MB]

Response:
{
  "submission_id": "uuid",
  "filename": "john_doe_cv.pdf",
  "status": "uploaded",
  "message": "CV uploaded successfully..."
}
```

#### Get My Submissions
```http
GET /api/v1/cv/submissions
Authorization: Bearer {token}
```

### Extraction Endpoints

#### Get Extracted Data
```http
GET /api/v1/extraction/{submission_id}
Authorization: Bearer {token}

Response:
{
  "submission_id": "uuid",
  "status": "extracted",
  "extracted_data": {
    "personal_info": {...},
    "social_links": {...},
    "work_history": [...],
    "education": [...],
    "skills": [...]
  },
  "overall_confidence": 87.5
}
```

#### Check Extraction Status
```http
GET /api/v1/extraction/{submission_id}/status
Authorization: Bearer {token}

Response:
{
  "submission_id": "uuid",
  "status": "processing",
  "message": "Extracting data from CV",
  "progress": 50
}
```

#### Validate/Update Extracted Data
```http
PUT /api/v1/extraction/{submission_id}/validate
Authorization: Bearer {token}
Content-Type: application/json

{
  "full_name": "John Doe",
  "email": "john@example.com",
  "github_url": "https://github.com/johndoe",
  "is_validated": true
}
```

### Admin Endpoints

#### Get All Submissions
```http
GET /api/v1/admin/submissions?page=1&per_page=20&status=extracted
Authorization: Bearer {admin_token}
```

#### Get Submission Details
```http
GET /api/v1/admin/submissions/{submission_id}
Authorization: Bearer {admin_token}
```

#### Get Statistics
```http
GET /api/v1/admin/stats
Authorization: Bearer {admin_token}

Response:
{
  "overview": {
    "total_submissions": 150,
    "total_users": 50,
    "recent_submissions_7d": 25,
    "average_confidence": 85.3,
    "success_rate": 94.5
  },
  "status_breakdown": {...},
  "file_type_breakdown": {...}
}
```

## Database Schema

### Users Table
- `id` (UUID, PK)
- `email` (VARCHAR, UNIQUE)
- `password_hash` (VARCHAR)
- `full_name` (VARCHAR)
- `role` (VARCHAR) - 'user' or 'admin'
- `created_at`, `updated_at` (TIMESTAMP)

### CV Submissions Table
- `id` (UUID, PK)
- `user_id` (UUID, FK → users)
- `filename` (VARCHAR)
- `file_path` (VARCHAR)
- `file_size` (INTEGER)
- `file_type` (VARCHAR) - 'pdf', 'docx', 'txt'
- `status` (VARCHAR) - 'uploaded', 'processing', 'extracted', 'validated', 'completed', 'failed'
- `uploaded_at`, `processed_at` (TIMESTAMP)
- `error_message` (TEXT)

### Extracted Data Table
- `id` (UUID, PK)
- `submission_id` (UUID, FK → cv_submissions)
- Personal info fields with confidence scores
- Social media URLs with confidence scores
- `work_history`, `education`, `skills` (JSONB)
- `overall_confidence` (NUMERIC)
- `raw_text` (TEXT)
- `is_validated` (BOOLEAN)
- `validated_at` (TIMESTAMP)

### User Edits Table
- `id` (UUID, PK)
- `extracted_data_id` (UUID, FK → extracted_data)
- `field_name` (VARCHAR)
- `original_value`, `edited_value` (TEXT)
- `edited_at` (TIMESTAMP)

## Testing

### Run Tests
```bash
pytest tests/
```

### Test with Sample CV
```bash
curl -X POST http://localhost:8000/api/v1/cv/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@sample_cv.pdf"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `SECRET_KEY` | JWT secret key (32+ chars) | Required |
| `ALGORITHM` | JWT algorithm | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | 30 |
| `UPLOAD_DIR` | File upload directory | ./uploads |
| `MAX_FILE_SIZE` | Max file size in bytes | 10485760 (10MB) |
| `ALLOWED_EXTENSIONS` | Allowed file extensions | pdf,docx,txt |
| `DEBUG` | Debug mode | True |

## Features

### Current Features (Phase 1-3)
✅ User authentication with JWT
✅ CV file upload (PDF, DOCX, TXT)
✅ Automated text extraction from CVs
✅ Personal information extraction (name, email, phone, location)
✅ Social media link extraction (GitHub, LinkedIn, Portfolio, Twitter)
✅ Work history and education extraction
✅ Skills identification
✅ Confidence scoring (0-100) for extracted data
✅ User validation and editing of extracted data
✅ Admin dashboard with statistics
✅ Submission management and monitoring

### Planned Features (Future Phases)
⏳ Advanced NLP with spaCy Named Entity Recognition
⏳ Machine learning-based skill extraction
⏳ OCR support for scanned PDFs
⏳ Resume scoring and ranking
⏳ Bulk CV processing
⏳ Export to various formats
⏳ Email notifications
⏳ Webhook integration

## Troubleshooting

### Common Issues

**Database Connection Error**
```
Solution: Check your DATABASE_URL in .env file
Verify Supabase project is running
Check network connectivity
```

**File Upload Failed**
```
Solution: Ensure uploads/ directory exists and is writable
Check MAX_FILE_SIZE setting
Verify file type is allowed (pdf, docx, txt)
```

**JWT Token Invalid**
```
Solution: Check SECRET_KEY is set correctly
Ensure token hasn't expired (30 minutes default)
Verify Authorization header format: "Bearer {token}"
```

**Import Errors**
```
Solution: Activate virtual environment
Run: pip install -r requirements.txt
Download spaCy model: python -m spacy download en_core_web_sm
```

## Development

### Code Style
- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for functions and classes
- Keep functions small and focused

### Adding New Endpoints
1. Create route handler in `app/api/`
2. Define Pydantic schemas in `app/schemas/`
3. Add business logic to `app/services/`
4. Include router in `app/main.py`
5. Update API documentation

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Security

- Passwords are hashed using bcrypt
- JWT tokens for stateless authentication
- CORS configured for allowed origins
- File upload validation (type, size)
- SQL injection prevention (ORM parameterization)
- Input validation with Pydantic

## Production Deployment

### Using Uvicorn with Gunicorn
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Environment Best Practices
- Use strong SECRET_KEY (32+ random characters)
- Change default admin credentials
- Set DEBUG=False
- Use HTTPS in production
- Enable rate limiting
- Set up monitoring and logging
- Regular database backups

## Support

For issues and questions:
- Check the troubleshooting section
- Review API documentation at `/docs`
- Check logs for error messages

## License

[Your License Here]

## Credits

Developed as part of the SkillSense AI-powered talent identification system.
