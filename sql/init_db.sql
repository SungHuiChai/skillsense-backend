-- SkillSense Database Initialization Script
-- For Supabase PostgreSQL
-- Run this script in your Supabase SQL Editor

-- Enable UUID extension (should already be enabled in Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables if they exist (be careful in production!)
-- DROP TABLE IF EXISTS user_edits CASCADE;
-- DROP TABLE IF EXISTS extracted_data CASCADE;
-- DROP TABLE IF EXISTS cv_submissions CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ============================================================================
-- CV SUBMISSIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS cv_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    file_type VARCHAR(50) CHECK (file_type IN ('pdf', 'docx', 'txt')),
    status VARCHAR(50) DEFAULT 'uploaded' CHECK (
        status IN ('uploaded', 'processing', 'extracted', 'validated', 'completed', 'failed')
    ),
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_cv_submissions_user_id ON cv_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_cv_submissions_status ON cv_submissions(status);
CREATE INDEX IF NOT EXISTS idx_cv_submissions_uploaded_at ON cv_submissions(uploaded_at DESC);

-- ============================================================================
-- EXTRACTED DATA TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS extracted_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL UNIQUE REFERENCES cv_submissions(id) ON DELETE CASCADE,

    -- Personal Information
    full_name VARCHAR(255),
    full_name_confidence NUMERIC(5,2) CHECK (full_name_confidence >= 0 AND full_name_confidence <= 100),
    email VARCHAR(255),
    email_confidence NUMERIC(5,2) CHECK (email_confidence >= 0 AND email_confidence <= 100),
    phone VARCHAR(50),
    phone_confidence NUMERIC(5,2) CHECK (phone_confidence >= 0 AND phone_confidence <= 100),
    location VARCHAR(255),
    location_confidence NUMERIC(5,2) CHECK (location_confidence >= 0 AND location_confidence <= 100),

    -- Social Media Links
    github_url VARCHAR(500),
    github_url_confidence NUMERIC(5,2) CHECK (github_url_confidence >= 0 AND github_url_confidence <= 100),
    linkedin_url VARCHAR(500),
    linkedin_url_confidence NUMERIC(5,2) CHECK (linkedin_url_confidence >= 0 AND linkedin_url_confidence <= 100),
    portfolio_url VARCHAR(500),
    portfolio_url_confidence NUMERIC(5,2) CHECK (portfolio_url_confidence >= 0 AND portfolio_url_confidence <= 100),
    twitter_url VARCHAR(500),
    twitter_url_confidence NUMERIC(5,2) CHECK (twitter_url_confidence >= 0 AND twitter_url_confidence <= 100),
    other_urls TEXT,

    -- Extracted Sections (JSONB for flexibility)
    work_history JSONB,
    education JSONB,
    skills JSONB,
    certifications JSONB,
    languages JSONB,

    -- Metadata
    extraction_method VARCHAR(50),
    overall_confidence NUMERIC(5,2) CHECK (overall_confidence >= 0 AND overall_confidence <= 100),
    raw_text TEXT,

    -- User Validation Status
    is_validated BOOLEAN DEFAULT FALSE,
    validated_at TIMESTAMP WITH TIME ZONE,
    validation_notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_extracted_data_submission_id ON extracted_data(submission_id);
CREATE INDEX IF NOT EXISTS idx_extracted_data_email ON extracted_data(email);
CREATE INDEX IF NOT EXISTS idx_extracted_data_is_validated ON extracted_data(is_validated);

-- ============================================================================
-- USER EDITS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extracted_data_id UUID NOT NULL REFERENCES extracted_data(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    original_value TEXT,
    edited_value TEXT,
    edited_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_edits_extracted_data_id ON user_edits(extracted_data_id);
CREATE INDEX IF NOT EXISTS idx_user_edits_edited_at ON user_edits(edited_at DESC);

-- ============================================================================
-- TRIGGERS FOR AUTO-UPDATING TIMESTAMPS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for users table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for extracted_data table
DROP TRIGGER IF EXISTS update_extracted_data_updated_at ON extracted_data;
CREATE TRIGGER update_extracted_data_updated_at
    BEFORE UPDATE ON extracted_data
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) - Optional but recommended for Supabase
-- ============================================================================

-- Enable RLS on tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE cv_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_edits ENABLE ROW LEVEL SECURITY;

-- Create policies (example - adjust based on your authentication strategy)
-- Users can read their own data
CREATE POLICY "Users can read own data" ON users
    FOR SELECT
    USING (auth.uid()::text = id::text);

-- Users can read their own submissions
CREATE POLICY "Users can read own submissions" ON cv_submissions
    FOR SELECT
    USING (auth.uid()::text = user_id::text);

-- Users can insert their own submissions
CREATE POLICY "Users can insert own submissions" ON cv_submissions
    FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text);

-- Note: Adjust these policies based on your authentication setup
-- For API-based authentication with JWT, you might want to disable RLS
-- or create service role policies

-- ============================================================================
-- INITIAL DATA SEED
-- ============================================================================

-- Insert default admin user (password: admin123)
-- Password hash for 'admin123' using bcrypt
INSERT INTO users (email, password_hash, full_name, role)
VALUES (
    'admin@skillsense.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7vxj2gS1Im',
    'System Administrator',
    'admin'
)
ON CONFLICT (email) DO NOTHING;

-- Insert test user (password: test123)
INSERT INTO users (email, password_hash, full_name, role)
VALUES (
    'test@example.com',
    '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
    'Test User',
    'user'
)
ON CONFLICT (email) DO NOTHING;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Show created tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Show created indexes
SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully!';
    RAISE NOTICE 'Admin credentials: admin@skillsense.com / admin123';
    RAISE NOTICE 'Test user credentials: test@example.com / test123';
    RAISE NOTICE 'Remember to change these passwords in production!';
END $$;
