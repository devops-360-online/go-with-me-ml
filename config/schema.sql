-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

-- Create quotas table
CREATE TABLE IF NOT EXISTS quotas (
    quota_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    request_limit INTEGER NOT NULL,
    token_limit INTEGER NOT NULL,
    tier VARCHAR(20) NOT NULL,
    reset_frequency VARCHAR(20) DEFAULT 'monthly',
    UNIQUE(user_id)
);

-- Create requests table
CREATE TABLE IF NOT EXISTS requests (
    request_id UUID PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    prompt TEXT NOT NULL,
    result TEXT,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_tokens INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    model VARCHAR(50),
    error TEXT
);

-- Create token_usage table for analytics
CREATE TABLE IF NOT EXISTS token_usage (
    usage_id SERIAL PRIMARY KEY,
    request_id UUID REFERENCES requests(request_id),
    user_id VARCHAR(50) REFERENCES users(user_id),
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    model VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_user_id ON token_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON token_usage(created_at);

-- Insert sample user
INSERT INTO users (user_id, name, email, active)
VALUES ('test-user', 'Test User', 'test@example.com', TRUE)
ON CONFLICT (user_id) DO NOTHING;

-- Insert sample quota
INSERT INTO quotas (user_id, request_limit, token_limit, tier)
VALUES ('test-user', 100, 10000, 'free')
ON CONFLICT (user_id) DO NOTHING; 