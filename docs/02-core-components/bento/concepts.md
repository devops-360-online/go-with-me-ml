# Bento Concepts

## What Bento Does in Our Architecture

Bento serves as the **configuration-driven glue** between our system components, specifically:

1. **API Gateway**: Bento receives HTTP requests from clients, validates them, adds metadata (request IDs, timestamps), and forwards them to RabbitMQ queues.

2. **ML Worker**: Bento pulls inference requests from RabbitMQ, transforms the data into the format expected by ML models, calls the ML service, and sends results back to response queues.

3. **Results Collector**: Bento consumes processed results from RabbitMQ and stores them in PostgreSQL for persistence and tracking.

All of this happens **without writing custom code** - just YAML configuration files that can be easily modified and deployed.

```mermaid
graph LR
    A[Client] --> B[Bento API Gateway]
    B --> C[RabbitMQ]
    C --> D[Bento ML Worker]
    D --> E[ML Service]
    E --> D
    D --> C
    C --> F[Bento Results Collector]
    F --> G[PostgreSQL]
    
    style B fill:#f96,stroke:#333
    style D fill:#f96,stroke:#333
    style F fill:#f96,stroke:#333
```

## Why We Need Bento

Bento solves several critical problems in our ML inference architecture:

### 1. Quota Management and Rate Limiting
- **User Quota Enforcement**: Bento tracks and enforces user-specific API quotas without custom code
- **Rate Limiting**: Prevents ML services from being overwhelmed during traffic spikes
- **Priority Handling**: Routes high-priority requests to dedicated queues

#### Example: User Quota Management

Here's how Bento handles user quotas without custom code:

```yaml
# API Gateway Bento Configuration
input:
  http_server:
    path: /generate
    
pipeline:
  processors:
    # Extract user ID from auth header
    - bloblang: |
        root = this
        root.user_id = this.headers."X-API-Key".split("-").first()
        
    # Check request quota
    - redis:
        url: redis://redis:6379
        command: get
        key: ${! "user:" + this.user_id + ":quota:daily:requests:limit" }
        
    - bloblang: |
        root = this
        root.request_limit = this.redis.number() or 100
        
    - redis:
        url: redis://redis:6379
        command: get
        key: ${! "user:" + this.user_id + ":quota:daily:requests:used" }
        
    - bloblang: |
        root = this
        root.requests_used = this.redis.number() or 0
        root.request_quota_exceeded = this.requests_used >= this.request_limit
        
    # Estimate tokens based on prompt length
    - bloblang: |
        root = this
        root.estimated_tokens = ceil(length(this.prompt) / 4) * 2  # Input + estimated output
        
    # Check token quota
    - redis:
        url: redis://redis:6379
        command: get
        key: ${! "user:" + this.user_id + ":quota:daily:tokens:limit" }
        
    - bloblang: |
        root = this
        root.token_limit = this.redis.number() or 10000
        
    - redis:
        url: redis://redis:6379
        command: get
        key: ${! "user:" + this.user_id + ":quota:daily:tokens:used" }
        
    - bloblang: |
        root = this
        root.tokens_used = this.redis.number() or 0
        root.token_quota_exceeded = (this.tokens_used + this.estimated_tokens) > this.token_limit
        root.quota_exceeded = this.request_quota_exceeded || this.token_quota_exceeded
        
    # Handle quota exceeded
    - branch:
        processors:
          - bloblang: |
              quota_type = ""
              if this.request_quota_exceeded {
                quota_type = "request"
              } else if this.token_quota_exceeded {
                quota_type = "token"
              }
              
              root = {
                "error": quota_type + " quota exceeded",
                "status": "error",
                "requests": {
                  "used": this.requests_used,
                  "limit": this.request_limit
                },
                "tokens": {
                  "used": this.tokens_used,
                  "limit": this.token_limit,
                  "estimated": this.estimated_tokens
                }
              }
          - output:
              http_server:
                status_code: 429
        condition:
          bloblang: root.quota_exceeded
          
    # Increment request quota if not exceeded
    - redis:
        url: redis://redis:6379
        command: incr
        key: ${! "user:" + this.user_id + ":quota:daily:requests:used" }
        
    # Set expiry on request quota counter
    - redis:
        url: redis://redis:6379
        command: expire
        key: ${! "user:" + this.user_id + ":quota:daily:requests:used" }
        value: "86400"
        
    # Reserve estimated tokens
    - redis:
        url: redis://redis:6379
        command: incrby
        key: ${! "user:" + this.user_id + ":quota:daily:tokens:used" }
        value: ${! this.estimated_tokens }
        
    # Set expiry on token quota counter
    - redis:
        url: redis://redis:6379
        command: expire
        key: ${! "user:" + this.user_id + ":quota:daily:tokens:used" }
        value: "86400"
        
    # Continue processing if quota available
    - bloblang: |
        root = this
        root.request_id = uuid_v4()
        
    # Store request in PostgreSQL with token estimation
    - sql:
        driver: postgres
        dsn: postgres://user:${DB_PASSWORD}@postgres:5432/ml_inference
        query: >
          INSERT INTO requests 
          (request_id, user_id, prompt, estimated_tokens, status) 
          VALUES ($1, $2, $3, $4, 'queued')
        args_mapping: |
          root = [
            this.request_id,
            this.user_id,
            this.prompt,
            this.estimated_tokens,
            "queued"
          ]
          
    # Send to RabbitMQ with token estimation
    - bloblang: |
        root = {
          "request_id": this.request_id,
          "user_id": this.user_id,
          "prompt": this.prompt,
          "estimated_tokens": this.estimated_tokens
        }
        
output:
  amqp:
    url: amqp://guest:guest@rabbitmq:5672/
    target: inference_requests
```

### 2. Transformation and Mapping
- **Data Transformation**: Easily converts between formats (JSON, XML, protobuf)
- **Field Mapping**: Rename, restructure, and manipulate data fields
- **Conditional Logic**: Apply different transformations based on content

### 3. Integration
- **Input/Output Agnostic**: Connect to over 70 different inputs/outputs
- **Protocol Translation**: Convert between HTTP, AMQP, Kafka, etc.
- **API Abstraction**: Create REST endpoints with minimal configuration

### 4. Resilience and Error Handling
- **Automatic Retries**: Built-in retry mechanisms with backoff
- **Dead Letter Queues**: Route failed messages to error queues
- **Circuit Breaking**: Prevent cascading failures
- **Graceful Shutdown**: Clean handling of in-flight requests

## Key Bento Components

Bento uses a modular architecture with three main components:

### 1. Inputs
Inputs pull data into Bento from various sources.

Common inputs in our architecture:
- `http_server`: Receives API requests from clients
- `amqp`: Consumes messages from RabbitMQ queues

### 2. Processors
Processors transform, filter, enrich, or otherwise manipulate data.

Key processors in our architecture:
- `bloblang`: Powerful transformation language
- `redis`: Interacts with Redis for quota tracking
- `sql`: Queries/updates PostgreSQL
- `http_client`: Calls external APIs (like ML services)

### 3. Outputs
Outputs send processed data to external destinations.

Common outputs in our architecture:
- `amqp`: Sends messages to RabbitMQ queues
- `http_client`: Calls ML services
- `drop`: Explicitly discards messages where needed

## Bento as Parallel Stream Processor

Bento uses a parallel stream processing architecture:

```mermaid
graph LR
    A[Input] --> B[Processor 1]
    B --> C[Processor 2]
    C --> D[Processor N]
    D --> E[Output]
    
    %% Add parallel paths
    A --> F[Batch 1]
    F --> G[Parallel Processing]
    G --> H[Merge Results]
    H --> E
```

## Configuration Structure

A typical Bento configuration has this structure:

```yaml
# Define how messages enter the pipeline
input:
  type: http_server  # Or any other input type
  http_server:
    address: 0.0.0.0:8080
    path: /api/v1/inference

# Optional: Stream-wide error handling
stream:
  retries: 3
  backoff:
    initial_interval: 1s
    max_interval: -1s
    max_elapsed_time: 30s

# Define processing steps
pipeline:
  processors:
    # List of processing steps
    - bloblang: |
        root.request_id = uuid_v4()
    
    - log:
        level: INFO
        message: "Processing request ${! json(\"request_id\") }"
    
    # More processors...

# Define where processed messages go
output:
  amqp:
    url: amqp://guest:guest@rabbitmq:5672/
    exchange: ml_exchange
    target: inference_requests
```

## Client Notification Patterns

### Enhancing Results Collector with SSE Notifications

For real-time client notifications without polling overhead, the Results Collector can be enhanced to send HTTP notifications when results are ready. This is particularly important for quota-sensitive systems where polling wastes request allocations.

#### Problem with Traditional Polling

```yaml
# Traditional client flow - QUOTA INEFFICIENT
# 1 ML request = 1 quota unit
# 30 polling requests = 30 wasted quota units  
# Total: 31 quota units for 1 result ❌
```

#### Solution: SSE Push Notifications

```yaml
# SSE flow - QUOTA EFFICIENT  
# 1 ML request = 1 quota unit
# 1 SSE connection = 0 quota units
# Total: 1 quota unit for 1 result ✅
```

#### Enhanced Results Collector Configuration

```yaml
# infrastructure/kubernetes/bento/files/results-collector-with-sse.yml
input:
  amqp:
    url: "${RABBITMQ_URL}"
    queue: inference_results
    consumer_group: results_collectors

pipeline:
  processors:
    - log:
        level: INFO
        message: "Processing result: ${! json() }"

    - try:
        # Parse and process result (existing logic)
        - bloblang: |
            let parsed = content().parse_json().catch({})
            let data = $parsed.output.parse_json().catch({})
            let usage = $data.token_usage.or({})
            
            let p = $usage.prompt_tokens.or(0).floor()
            let c = $usage.completion_tokens.or(0).floor()
            let t = $usage.total_tokens.or($p + $c).floor().or(1)

            root = $parsed.merge({
              "prompt_tokens":     $p,
              "completion_tokens": $c,
              "total_tokens":      $t
            })

        # Update Redis quotas (existing functionality)
        - branch:
            processors:
              - redis:
                  url: "${REDIS_URL}"
                  command: INCRBY
                  key: ${! "user:" + this.user_id + ":quota:daily:tokens:used" }
                  value: ${! this.total_tokens }
            result_map: root = deleted()

        # Update PostgreSQL (existing functionality)
        - branch:
            processors:
              - sql:
                  driver: postgres
                  dsn: "${POSTGRES_URL}"
                  query: |
                    UPDATE inference_requests
                    SET result = $1,
                        status = 'completed',
                        completed_at = NOW(),
                        prompt_tokens = $2,
                        completion_tokens = $3,
                        total_tokens = $4
                    WHERE request_id = $5;
                  args_mapping: |
                    root = [
                      this.output,
                      this.prompt_tokens,
                      this.completion_tokens,
                      this.total_tokens,
                      this.request_id
                    ]
            result_map: root = deleted()

        # NEW: Send SSE notification to connected clients
        - branch:
            processors:
              - http:
                  url: "${NOTIFICATION_SERVICE_URL}/notify"
                  verb: POST
                  headers:
                    Content-Type: "application/json"
                  timeout: "5s"
                  retry_period: "1s"
                  max_retry_backoff: "10s"
                  retries: 3
                  body: |
                    {
                      "type": "completed",
                      "request_id": "${! this.request_id }",
                      "user_id": "${! this.user_id }",
                      "result": ${! this.output },
                      "token_usage": {
                        "prompt_tokens": ${! this.prompt_tokens },
                        "completion_tokens": ${! this.completion_tokens },
                        "total_tokens": ${! this.total_tokens }
                      },
                      "timestamp": "${! timestamp_unix() }"
                    }
                  
              - log:
                  level: INFO
                  message: "Sent SSE notification for request ${! this.request_id }"
                  
            result_map: root = deleted()

        # Optional: Store in Redis for immediate access
        - branch:
            processors:
              - redis:
                  url: "${REDIS_URL}"
                  command: SET
                  key: ${! "result:" + this.request_id }
                  value: |
                    {
                      "status": "completed",
                      "result": "${! this.output }",
                      "token_usage": {
                        "prompt_tokens": ${! this.prompt_tokens },
                        "completion_tokens": ${! this.completion_tokens },
                        "total_tokens": ${! this.total_tokens }
                      }
                    }
                    
              - redis:
                  url: "${REDIS_URL}"
                  command: EXPIRE
                  key: ${! "result:" + this.request_id }
                  value: 3600  # Keep for 1 hour
                  
            result_map: root = deleted()

        - log:
            level: INFO
            message: "Completed processing for request ${! this.request_id }"

    - catch:
        # Handle errors and notify clients of failures
        - log:
            level: ERROR
            message: "Processing failed: ${!error()}"
            
        - branch:
            processors:
              # Notify client of error via SSE
              - http:
                  url: "${NOTIFICATION_SERVICE_URL}/notify"
                  verb: POST
                  headers:
                    Content-Type: "application/json"
                  timeout: "5s"
                  retries: 2
                  body: |
                    {
                      "type": "error",
                      "request_id": "${! this.request_id }",
                      "error_message": "${! error() }",
                      "timestamp": "${! timestamp_unix() }"
                    }
                    
              - log:
                  level: ERROR
                  message: "Sent error notification for request ${! this.request_id }"
                  
            result_map: root = deleted()

output:
  drop: {}
```

#### Key Benefits of This Approach

1. **Quota Efficiency**: No wasted requests for polling
2. **Real-time Delivery**: Immediate notification when results ready  
3. **Error Handling**: Automatic retries and error notifications
4. **Monitoring**: Built-in logging for debugging
5. **Resilience**: Graceful handling of notification service failures

#### Environment Variables Required

```bash
# Results Collector
NOTIFICATION_SERVICE_URL=http://notification-service:8081
RABBITMQ_URL=amqp://user:pass@rabbitmq:5672
REDIS_URL=redis://redis:6379
POSTGRES_URL=postgresql://user:pass@postgres:5432/ml_inference
```

#### Bento Configuration Benefits

Using Bento for this notification enhancement provides:

- **No Custom Code**: Pure configuration-driven approach
- **Built-in Retry Logic**: Automatic handling of notification failures
- **Parallel Processing**: Non-blocking notifications via `branch` processor
- **Error Recovery**: `try`/`catch` blocks for robust error handling  
- **Monitoring Integration**: Native logging and metrics support
- **Easy Deployment**: Configuration changes without code rebuilds

This pattern demonstrates how Bento's configuration-driven approach makes it easy to add sophisticated features like real-time client notifications without writing custom integration code. 