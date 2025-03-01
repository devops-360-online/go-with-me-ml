CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TABLE requests (
  request_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prompt TEXT NOT NULL,
  result TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  created_at TIMESTAMP DEFAULT NOW()
);