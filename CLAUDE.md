# SkillSense Backend - Development Notes

## Architecture Overview

This is a FastAPI-based backend for CV processing and data extraction.

### Key Components

**Models** (`app/models/`)
- `user.py` - User authentication model
- `cv_submission.py` - CV upload tracking
- `extracted_data.py` - Extracted CV data with confidence scores

**Services** (`app/services/`)
- `cv_parser.py` - PDF/DOCX/TXT parsing (PyPDF2, pdfplumber, python-docx)
- `extractor.py` - Data extraction with regex patterns
- `link_validator.py` - URL validation

**API Endpoints** (`app/api/`)
- `auth.py` - User registration, login, JWT tokens
- `cv_upload.py` - CV file upload with background processing
- `extraction.py` - Get/validate extracted data
- `admin.py` - Admin statistics and management

### Database Schema (Supabase PostgreSQL)

```sql
users (id, email, password_hash, role, ...)
  ↓
cv_submissions (id, user_id, filename, status, ...)
  ↓
extracted_data (id, submission_id, personal_info, social_links, work_history, ...)
  ↓
user_edits (id, extracted_data_id, field_name, original_value, edited_value, ...)
```

### Background Processing

CV extraction runs as a background task:
1. File uploaded → status: "uploaded"
2. Background task starts → status: "processing"
3. Extraction complete → status: "extracted"
4. User validates → status: "validated"

### Confidence Scoring

- **High (80-100%)**: Clear pattern match, validated format
- **Medium (60-79%)**: Probable match, needs review
- **Low (0-59%)**: Uncertain, requires attention

Algorithm in `extractor.py`:
- Email: Regex + domain validation (85-99%)
- Phone: Regex format matching (75-95%)
- Social links: URL pattern + domain check (70-90%)
- Work/Education: Section detection + entity extraction (70-85%)

### Environment Variables

Required in `.env`:
- `DATABASE_URL` - Supabase PostgreSQL connection string
- `SECRET_KEY` - JWT secret (32+ characters)
- `UPLOAD_DIR` - File upload directory (default: ./uploads)
- `MAX_FILE_SIZE` - Max upload size in bytes (default: 10MB)

### Development Workflow

1. Models → Schemas → Services → API endpoints
2. Database changes: Update models, run migrations
3. New extraction logic: Add to `extractor.py`
4. New endpoints: Add to `app/api/`, include in `main.py`

### Testing

```bash
# Run with sample CV
curl -X POST http://localhost:8000/api/v1/cv/upload \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@sample.pdf"
```

### Future Enhancements

- [ ] Implement spaCy NER for better extraction
- [ ] Add OCR for scanned PDFs
- [ ] Implement caching for repeated requests
- [ ] Add rate limiting
- [ ] WebSocket for real-time updates
- [ ] Celery for distributed task processing

### Common Issues

**Import errors**: Ensure virtual environment is activated
**Database errors**: Check Supabase connection string
**Upload fails**: Verify uploads/ directory exists and is writable

### Code Style

- Type hints for all functions
- Pydantic for validation
- SQLAlchemy for ORM
- Async where beneficial
- Comprehensive docstrings
