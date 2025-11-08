# SkillSense Phase 2 - Data Collection Layer Setup Guide

This guide will help you set up the Data Collection Layer (Phase 2) for SkillSense, which includes GitHub scraping and Tavily web search integration.

---

## Prerequisites

Before starting Phase 2 setup, ensure:
- ✅ Phase 1 is fully implemented and working
- ✅ Database is running (Supabase PostgreSQL)
- ✅ Backend API is functional

---

## Step 1: Install Dependencies

Install the new Phase 2 dependencies:

```bash
cd skillsense-backend
pip install -r requirements.txt
```

New packages installed:
- `beautifulsoup4` - HTML parsing
- `lxml` - XML/HTML processing
- `html5lib` - HTML5 parsing
- `newspaper3k` - Article extraction

---

## Step 2: Obtain API Keys

### 2.1 GitHub Personal Access Token

GitHub API is used to scrape user profiles, repositories, and contribution data.

**Steps to get your token:**

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name: `SkillSense Data Collection`
4. Set expiration: `No expiration` or `90 days`
5. Select scopes:
   - ✅ `public_repo` - Access public repositories
   - ✅ `read:user` - Read user profile data
6. Click "Generate token"
7. **IMPORTANT**: Copy the token immediately (you won't see it again!)

**Token format**: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**Rate Limits**:
- Without token: 60 requests/hour
- With token: 5,000 requests/hour

**Free Tier**: ✅ Yes, completely free!

---

### 2.2 Tavily API Key

Tavily is an AI-powered search API optimized for finding relevant web content.

**Steps to get your API key:**

1. Go to https://tavily.com
2. Click "Get Started" or "Sign Up"
3. Create an account (email + password)
4. Verify your email
5. Go to Dashboard → API Keys
6. Copy your API key

**Token format**: `tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**Pricing** (as of 2024):
- Free Tier: 1,000 searches/month
- Basic: $30/month - 10,000 searches
- Pro: Custom pricing

**Recommendation**: Start with the free tier for testing, upgrade if needed.

---

## Step 3: Configure Environment Variables

1. Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

2. Open `.env` in your editor and add your API keys:

```bash
# Phase 2: Data Collection API Keys
GITHUB_TOKEN=ghp_your_actual_token_here
TAVILY_API_KEY=tvly-your_actual_key_here
```

3. **IMPORTANT**: Never commit `.env` to git! It's already in `.gitignore`.

---

## Step 4: Run Database Migration

Run the Phase 2 SQL script to create the new tables:

### For Supabase:

1. Go to your Supabase project dashboard
2. Click "SQL Editor" in the left sidebar
3. Click "New Query"
4. Copy the contents of `sql/add_collection_tables.sql`
5. Paste into the editor
6. Click "Run"

**Expected output**: "Phase 2 database tables created successfully!"

### For Local PostgreSQL:

```bash
psql -U postgres -d skillsense -f sql/add_collection_tables.sql
```

**Tables created**:
- `collected_sources` - Tracks collection status
- `github_data` - GitHub profile and repo data
- `web_mentions` - Articles and web mentions
- `aggregated_profile` - Combined data from all sources

---

## Step 5: Verify Installation

1. Start the backend server:

```bash
cd skillsense-backend
uvicorn app.main:app --reload
```

2. Check the API documentation:

Open http://localhost:8000/docs

3. Look for new Phase 2 endpoints under "collection" tag:
   - `POST /api/v1/collection/start/{submission_id}`
   - `GET /api/v1/collection/status/{submission_id}`
   - `GET /api/v1/collection/results/{submission_id}`

4. Test API info endpoint:

```bash
curl http://localhost:8000/api/v1/info
```

You should see `"collection": "/api/v1/collection"` in the endpoints.

---

## Step 6: Test Data Collection

### 6.1 Upload a CV

Use the existing Phase 1 flow to upload a CV with GitHub and social links.

### 6.2 Start Collection

```bash
curl -X POST "http://localhost:8000/api/v1/collection/start/{submission_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

### 6.3 Check Status

```bash
curl "http://localhost:8000/api/v1/collection/status/{submission_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 6.4 Get Results

```bash
curl "http://localhost:8000/api/v1/collection/results/{submission_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Architecture Overview

### Data Flow

```
1. User uploads CV → Phase 1 extraction
2. User validates extracted data
3. System triggers Phase 2 collection:
   ├─ GitHub Scraper (if github_url found)
   │  ├─ Profile data
   │  ├─ Repositories
   │  └─ Languages/Technologies
   │
   └─ Tavily Search (if name found)
      ├─ Search queries with context
      ├─ Article extraction
      └─ Relevance scoring

4. Data Aggregation:
   ├─ Combine all sources
   ├─ Resolve conflicts
   ├─ Calculate quality scores
   └─ Store in aggregated_profile
```

### Key Components

**Scrapers** (`app/scrapers/`):
- `base_scraper.py` - Abstract base class with rate limiting and retries
- `github_scraper.py` - GitHub API integration

**Search** (`app/search/`):
- `tavily_search.py` - Tavily API integration

**Services** (`app/services/`):
- `collection_orchestrator.py` - Coordinates all collection tasks

**Aggregation** (`app/aggregation/`):
- `data_aggregator.py` - Combines data from multiple sources

**API** (`app/api/`):
- `collection.py` - REST endpoints for collection

---

## Troubleshooting

### GitHub API Rate Limit Error

**Error**: `GitHub API rate limit exceeded`

**Solution**:
1. Verify your `GITHUB_TOKEN` is correct
2. Check rate limit: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`
3. Wait for reset time or use a different token

### Tavily API Error

**Error**: `Invalid Tavily API key`

**Solution**:
1. Verify your `TAVILY_API_KEY` is correct
2. Check you've activated your account (email verification)
3. Check API usage on Tavily dashboard

### Collection Stuck in "collecting" Status

**Solution**:
1. Check backend logs for errors
2. Verify network connectivity
3. Check if API keys are working
4. Try restarting the collection

### Database Connection Error

**Error**: `Phase 1 tables not found`

**Solution**:
1. Verify Phase 1 migration ran successfully
2. Check database connection string
3. Verify `cv_submissions` table exists

---

## Security Best Practices

1. **Never commit API keys**:
   - Always use `.env` file
   - Verify `.env` is in `.gitignore`

2. **Rotate keys regularly**:
   - GitHub tokens: Every 90 days
   - Tavily keys: Every 6 months

3. **Use environment-specific keys**:
   - Development: Separate keys
   - Production: Different keys with stricter limits

4. **Monitor API usage**:
   - GitHub: https://github.com/settings/tokens
   - Tavily: Dashboard

---

## Cost Estimation

For 100 CV submissions/month:

**GitHub API**: FREE
- ~500 API calls (5 per submission)
- Well within 5,000/hour limit

**Tavily API**:
- ~300 searches (3 per submission)
- Free tier: 1,000/month ✅
- Or Basic: $30/month for 10,000 searches

**Total estimated cost**: $0 - $30/month depending on volume

---

## Next Steps

After Phase 2 is working:

1. ✅ Test with multiple CV submissions
2. ✅ Verify data quality scores are accurate
3. ✅ Check aggregated profiles in database
4. 📝 Move to Phase 3: Skill Extraction & Matching
5. 📝 Implement frontend UI for viewing collected data

---

## Support

If you encounter issues:

1. Check logs: `tail -f logs/skillsense.log`
2. Verify API keys are working
3. Test scrapers individually
4. Check database tables were created correctly

For detailed API documentation, visit: http://localhost:8000/docs

---

**Phase 2 Implementation Complete!** 🚀

You now have a fully functional data collection layer that enriches CV data with GitHub profiles and web mentions.
