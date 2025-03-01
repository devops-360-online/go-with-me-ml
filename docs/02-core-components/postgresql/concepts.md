# PostgreSQL Concepts

## What PostgreSQL Does in Our Architecture

PostgreSQL serves as the **persistent storage backbone** for our ML inference system, specifically:

1. **Request Tracking**: Stores all inference requests with their status, timestamps, and metadata
2. **Result Storage**: Persists ML model outputs for retrieval and analysis
3. **User Management**: Maintains user accounts, API keys, and usage quotas
4. **Audit Trail**: Provides a complete history of all system activities

```mermaid
graph TD
    A[API Gateway] -->|Store Request| B[PostgreSQL]
    C[Results Collector] -->|Store Results| B
    D[Status API] -->|Query Status| B
    E[Analytics] -->|Query History| B
    
    style B fill:#336791,stroke:#333,color:white
```

## Why We Need PostgreSQL

PostgreSQL solves several critical problems in our ML inference architecture:

### 1. Persistent Request Tracking

- **Stateless Components**: Allows our API and worker services to be stateless
- **Request Recovery**: Enables recovery of in-flight requests after system restarts
- **Status Queries**: Provides a single source of truth for request status

#### Schema Design for Request Tracking

```sql
CREATE TABLE requests (
    request_id UUID PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    prompt TEXT NOT NULL,
    model_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'queued', 'processing', 'completed', 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processing_time_ms INTEGER,
    result_id UUID,
    error_message TEXT
);

CREATE INDEX idx_requests_user_id ON requests(user_id);
CREATE INDEX idx_requests_status ON requests(status);
CREATE INDEX idx_requests_created_at ON requests(created_at);
```

### 2. Result Management

- **Result Persistence**: Stores model outputs for future reference
- **Large Result Handling**: Efficiently stores large text or binary outputs
- **Result Deduplication**: Enables caching of results for identical inputs

#### Schema Design for Results

```sql
CREATE TABLE results (
    result_id UUID PRIMARY KEY,
    content TEXT NOT NULL, -- or JSONB for structured outputs
    token_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- For binary outputs like images
CREATE TABLE binary_results (
    result_id UUID PRIMARY KEY,
    content BYTEA NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 3. User and Quota Management

- **API Key Validation**: Verifies API keys for authentication
- **Usage Tracking**: Monitors usage for billing and quota enforcement
- **Rate Limiting**: Supports rate limiting decisions

#### Schema Design for Users and Quotas

```sql
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    api_key VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE quotas (
    user_id VARCHAR(50) REFERENCES users(user_id),
    quota_period VARCHAR(20) NOT NULL, -- 'daily', 'monthly', etc.
    max_requests INTEGER NOT NULL,
    requests_used INTEGER DEFAULT 0,
    reset_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (user_id, quota_period)
);

CREATE INDEX idx_api_keys ON users(api_key);
```

### 4. Operational Insights

- **Usage Analytics**: Provides data for understanding usage patterns
- **Performance Monitoring**: Tracks processing times and error rates
- **Billing Information**: Supplies data for usage-based billing

## Implementation Patterns

### 1. Request-Response Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB as PostgreSQL
    participant Queue as RabbitMQ
    participant Worker
    participant ML

    Client->>API: Submit Request
    API->>DB: Create request record (status=queued)
    API->>Queue: Enqueue request
    API->>Client: Return request_id
    
    Worker->>Queue: Dequeue request
    Worker->>DB: Update status (processing)
    Worker->>ML: Process request
    ML->>Worker: Return result
    Worker->>DB: Store result, update status (completed)
    
    Client->>API: Check status (request_id)
    API->>DB: Query request status
    API->>Client: Return status/result
```

### 2. Efficient Query Patterns

For status checks:

```sql
-- Efficient status check query
SELECT 
    r.request_id, 
    r.status, 
    r.error_message,
    res.content AS result
FROM 
    requests r
LEFT JOIN 
    results res ON r.result_id = res.result_id
WHERE 
    r.request_id = '123e4567-e89b-12d3-a456-426614174000';
```

For user history:

```sql
-- Get recent requests for a user
SELECT 
    request_id, 
    prompt, 
    status, 
    created_at,
    processing_time_ms
FROM 
    requests
WHERE 
    user_id = 'user123'
ORDER BY 
    created_at DESC
LIMIT 10;
```

### 3. Transaction Patterns

Ensuring data consistency:

```sql
BEGIN;

-- Update request status
UPDATE requests 
SET status = 'completed', 
    result_id = '123e4567-e89b-12d3-a456-426614174001',
    processing_time_ms = 1500,
    updated_at = NOW()
WHERE request_id = '123e4567-e89b-12d3-a456-426614174000';

-- Update user quota
UPDATE quotas
SET requests_used = requests_used + 1
WHERE user_id = 'user123' AND quota_period = 'daily';

COMMIT;
```

## Advanced Concepts

### 1. High-Volume Data Management

For systems with high request volumes:

```sql
-- Partitioning for time-based data
CREATE TABLE requests (
    request_id UUID NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    prompt TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- other fields
    PRIMARY KEY (created_at, request_id)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE requests_y2023m01 PARTITION OF requests
    FOR VALUES FROM ('2023-01-01') TO ('2023-02-01');

CREATE TABLE requests_y2023m02 PARTITION OF requests
    FOR VALUES FROM ('2023-02-01') TO ('2023-03-01');

-- And so on...
```

### 2. Archiving Strategy

For long-term storage:

```sql
-- Move completed requests older than 30 days to archive
INSERT INTO requests_archive
SELECT * FROM requests
WHERE status IN ('completed', 'failed')
AND created_at < NOW() - INTERVAL '30 days';

DELETE FROM requests
WHERE status IN ('completed', 'failed')
AND created_at < NOW() - INTERVAL '30 days';
```

### 3. Performance Optimization

```sql
-- Create materialized view for analytics
CREATE MATERIALIZED VIEW request_stats AS
SELECT 
    date_trunc('day', created_at) AS day,
    user_id,
    model_id,
    COUNT(*) AS request_count,
    AVG(processing_time_ms) AS avg_processing_time,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failure_count
FROM 
    requests
GROUP BY 
    date_trunc('day', created_at),
    user_id,
    model_id;

-- Refresh on schedule
REFRESH MATERIALIZED VIEW request_stats;
```

## Integration with Other Components

### 1. Benthos Integration

Benthos can read from and write to PostgreSQL:

```yaml
output:
  postgres:
    driver: postgres
    dsn: postgres://user:password@localhost:5432/ml_inference?sslmode=disable
    query: >
      INSERT INTO requests (request_id, user_id, prompt, model_id, status)
      VALUES ($1, $2, $3, $4, $5)
    args_mapping: |
      root = [
        this.request_id,
        this.user_id,
        this.prompt,
        this.model_id,
        "queued"
      ]
```

### 2. API Service Integration

Node.js example:

```javascript
app.post('/generate', async (req, res) => {
  const { prompt, model_id } = req.body;
  const user_id = req.user.id; // From auth middleware
  const request_id = uuidv4();
  
  // Store in PostgreSQL
  await pool.query(
    'INSERT INTO requests (request_id, user_id, prompt, model_id, status) VALUES ($1, $2, $3, $4, $5)',
    [request_id, user_id, prompt, model_id, 'queued']
  );
  
  // Send to RabbitMQ
  // ...
  
  res.json({ request_id, status: 'queued' });
});

app.get('/status/:requestId', async (req, res) => {
  const { requestId } = req.params;
  
  const result = await pool.query(`
    SELECT r.status, r.error_message, res.content AS result
    FROM requests r
    LEFT JOIN results res ON r.result_id = res.result_id
    WHERE r.request_id = $1
  `, [requestId]);
  
  if (result.rowCount === 0) {
    return res.status(404).json({ error: 'Request not found' });
  }
  
  const row = result.rows[0];
  res.json({
    status: row.status,
    result: row.result,
    error: row.error_message
  });
});
```

## Project Implementation Plan

| Component | PostgreSQL Usage | Description |
|-----------|------------------|-------------|
| API Gateway | Request Creation | Stores new inference requests |
| Status API | Request Queries | Retrieves request status and results |
| Results Collector | Result Storage | Persists ML model outputs |
| User Management | Authentication | Manages API keys and quotas |
| Analytics | Reporting | Generates usage and performance reports |

## Next Steps
- [Setup Guide](./setup.md)
- [Operations Guide](./operations.md)
- [Project Architecture](../../01-architecture/overview.md)

## Database Schema

Our PostgreSQL database uses the following schema to track ML inference requests and manage user quotas:

```sql
-- Users table
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

-- Quotas table with both request and token limits
CREATE TABLE quotas (
    quota_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    request_limit INTEGER NOT NULL,
    token_limit INTEGER NOT NULL,
    tier VARCHAR(20) NOT NULL,
    reset_frequency VARCHAR(20) DEFAULT 'monthly',
    UNIQUE(user_id)
);

-- Requests table with token tracking
CREATE TABLE requests (
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

-- Usage tracking for billing and analytics
CREATE TABLE usage (
    usage_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    period VARCHAR(20) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    requests_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    UNIQUE(user_id, period, period_start)
);

-- Indexes for performance
CREATE INDEX idx_requests_user_id ON requests(user_id);
CREATE INDEX idx_requests_created_at ON requests(created_at);
CREATE INDEX idx_requests_status ON requests(status);
CREATE INDEX idx_usage_user_period ON usage(user_id, period, period_start);
```

### Key Schema Features for Token-Based Quotas

1. **Quotas Table**:
   - Includes both `request_limit` and `token_limit` fields
   - Allows for different tiers with varying limits

2. **Requests Table**:
   - Tracks `estimated_tokens` at request time
   - Records actual token usage with `prompt_tokens`, `completion_tokens`, and `total_tokens`
   - Stores the model used, which may have different token costs

3. **Usage Table**:
   - Aggregates both request counts and token usage
   - Organized by billing periods for easy reporting

## Implementation Patterns

### 1. Token Usage Tracking

```sql
-- Record a new request with estimated tokens
INSERT INTO requests 
(request_id, user_id, prompt, estimated_tokens, status) 
VALUES 
('550e8400-e29b-41d4-a716-446655440000', 'user123', 'Translate the following text to French...', 150, 'queued');

-- Update with actual token usage after completion
UPDATE requests 
SET 
  status = 'completed', 
  prompt_tokens = 120, 
  completion_tokens = 80, 
  total_tokens = 200,
  result = 'Le texte traduit en français...',
  completed_at = CURRENT_TIMESTAMP
WHERE request_id = '550e8400-e29b-41d4-a716-446655440000';
```

### 2. Quota Checking

```sql
-- Check if user has sufficient token quota
WITH user_quota AS (
  SELECT token_limit 
  FROM quotas 
  WHERE user_id = 'user123'
),
user_usage AS (
  SELECT COALESCE(SUM(total_tokens), 0) as tokens_used
  FROM requests
  WHERE user_id = 'user123' 
  AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
)
SELECT 
  (SELECT token_limit FROM user_quota) - 
  (SELECT tokens_used FROM user_usage) AS remaining_tokens;
```

### 3. Usage Reporting

```sql
-- Update monthly usage statistics
INSERT INTO usage (user_id, period, period_start, period_end, requests_count, tokens_used)
SELECT 
  user_id,
  'monthly',
  DATE_TRUNC('month', CURRENT_DATE),
  (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month - 1 day')::date,
  COUNT(*),
  COALESCE(SUM(total_tokens), 0)
FROM requests
WHERE 
  created_at >= DATE_TRUNC('month', CURRENT_DATE) AND
  created_at < (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')
GROUP BY user_id
ON CONFLICT (user_id, period, period_start) 
DO UPDATE SET
  requests_count = EXCLUDED.requests_count,
  tokens_used = EXCLUDED.tokens_used;
```

### 4. Tiered Pricing Analysis

```sql
-- Analyze which pricing tier would be most economical for each user
WITH user_usage AS (
  SELECT 
    user_id,
    MAX(requests_count) as max_requests,
    MAX(tokens_used) as max_tokens
  FROM usage
  WHERE period = 'monthly'
  GROUP BY user_id
)
SELECT 
  u.user_id,
  u.max_requests,
  u.max_tokens,
  CASE 
    WHEN u.max_tokens < 100000 THEN 'basic'
    WHEN u.max_tokens < 1000000 THEN 'standard'
    ELSE 'premium'
  END as recommended_tier
FROM user_usage u;
``` 