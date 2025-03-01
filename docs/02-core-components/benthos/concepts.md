# Benthos Concepts

## What Benthos Does in Our Architecture

Benthos serves as the **configuration-driven glue** between our system components, specifically:

1. **API Gateway**: Benthos receives HTTP requests from clients, validates them, adds metadata (request IDs, timestamps), and forwards them to RabbitMQ queues.

2. **ML Worker**: Benthos pulls inference requests from RabbitMQ, transforms the data into the format expected by ML models, calls the ML service, and sends results back to response queues.

3. **Results Collector**: Benthos consumes processed results from RabbitMQ and stores them in PostgreSQL for persistence and tracking.

All of this happens **without writing custom code** - just YAML configuration files that can be easily modified and deployed.

```mermaid
graph LR
    A[Client] --> B[Benthos API Gateway]
    B --> C[RabbitMQ]
    C --> D[Benthos ML Worker]
    D --> E[ML Service]
    E --> D
    D --> C
    C --> F[Benthos Results Collector]
    F --> G[PostgreSQL]
    
    style B fill:#f96,stroke:#333
    style D fill:#f96,stroke:#333
    style F fill:#f96,stroke:#333
```

## Why We Need Benthos

Benthos solves several critical problems in our ML inference architecture:

### 1. Quota Management and Rate Limiting
- **User Quota Enforcement**: Benthos tracks and enforces user-specific API quotas without custom code
- **Rate Limiting**: Prevents ML services from being overwhelmed during traffic spikes
- **Priority Handling**: Routes high-priority requests to dedicated queues

#### Example: User Quota Management

Here's how Benthos handles user quotas without custom code:

```yaml
# API Gateway Benthos Configuration
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
        
    - output:
        rabbitmq:
          url: amqp://guest:guest@rabbitmq:5672/
          exchange: ""
          key: inference_requests
          
    # Return request ID to client
    - bloblang: |
        root = {
          "request_id": this.request_id,
          "status": "queued",
          "estimated_tokens": this.estimated_tokens
        }
```

And in the Results Collector:

```yaml
# Results Collector Configuration
input:
  rabbitmq:
    url: amqp://guest:guest@rabbitmq:5672/
    queue: inference_results
    
pipeline:
  processors:
    # Extract actual token usage from ML response
    - bloblang: |
        root = this
        root.actual_tokens = this.usage.total_tokens
        
    # Adjust token quota (subtract estimated, add actual)
    - redis:
        url: redis://redis:6379
        command: eval
        args_mapping: |
          root = [
            `
            local used_key = "user:" .. ARGV[1] .. ":quota:daily:tokens:used"
            local estimated = tonumber(ARGV[2])
            local actual = tonumber(ARGV[3])
            
            -- Adjust the quota (remove estimate, add actual)
            local used = tonumber(redis.call('GET', used_key) or "0")
            local new_used = used - estimated + actual
            
            -- Update with actual usage
            redis.call('SET', used_key, new_used)
            redis.call('EXPIRE', used_key, 86400)
            
            return new_used
            `,
            this.user_id,
            this.estimated_tokens,
            this.actual_tokens
          ]
          
    # Update PostgreSQL with actual token usage
    - sql:
        driver: postgres
        dsn: postgres://user:${DB_PASSWORD}@postgres:5432/ml_inference
        query: >
          UPDATE requests 
          SET 
            status = 'completed', 
            prompt_tokens = $1, 
            completion_tokens = $2, 
            total_tokens = $3,
            result = $4
          WHERE request_id = $5
        args_mapping: |
          root = [
            this.usage.prompt_tokens,
            this.usage.completion_tokens,
            this.usage.total_tokens,
            this.result,
            this.request_id
          ]
```

This configuration demonstrates how Benthos can:
1. Track both request counts and token usage
2. Estimate token usage before processing
3. Adjust quotas based on actual token consumption
4. Store both metrics in Redis and PostgreSQL
5. Provide detailed quota information to users

The token-based approach provides a more accurate representation of resource usage, as different requests can consume vastly different amounts of computational resources depending on input size and complexity.

### 2. Eliminating Boilerplate Code
- **No Custom Gateway Code**: Replaces hundreds of lines of API gateway code with configuration
- **No Custom Worker Code**: Eliminates need for worker services that just move data between systems
- **No Custom DB Connector**: Handles database operations through configuration

### 3. Operational Advantages
- **Fast Iteration**: Change data flows by updating configuration, not code
- **Reduced Maintenance**: Fewer services to maintain and debug
- **Built-in Observability**: Metrics, tracing, and logging without additional code

### 4. ML-Specific Benefits
- **Batch Processing**: Efficiently groups requests for batch inference
- **Error Handling**: Automatically retries failed ML requests with backoff
- **Result Transformation**: Formats ML model outputs for downstream systems

## Introduction

### What is Benthos?
Benthos is a high-performance, declarative stream processor that enables you to:
- Connect different systems and protocols
- Transform and filter data
- Build resilient data pipelines
- All through configuration files, without writing code

### Evolution of Data Processing
1. **Traditional Approach**
   ```
   [Custom Code] → [Custom Code] → [Custom Code]
   ```
   Problems:
   - High development overhead
   - Difficult to maintain
   - Challenging to modify
   - Requires specialized knowledge

2. **Benthos Approach**
   ```
   [Config File] → [Benthos Engine] → [Config File]
   ```
   Benefits:
   - Declarative configuration
   - No custom code required
   - Easy to modify and iterate
   - Built-in observability

### Why Benthos for ML Inference?
1. **Simplicity**: Configure complex pipelines without code
2. **Flexibility**: Connect to various systems (RabbitMQ, APIs, databases)
3. **Resilience**: Built-in error handling and retry mechanisms
4. **Performance**: High throughput with low resource usage

## Core Concepts

### 1. Stream Processing Model

#### Basic Pipeline
```mermaid
graph LR
    A[Input] --> B[Processors]
    B --> C[Output]
    style A fill:#f9f,stroke:#333
    style B fill:#ff9,stroke:#333
    style C fill:#9f9,stroke:#333
```

#### Advanced Pipeline
```mermaid
graph LR
    A[Input] --> B[Buffer]
    B --> C[Processors]
    C --> D[Rate Limit]
    D --> E[Output]
```

### 2. Configuration Structure

```yaml
input:
  rabbitmq:
    urls:
      - amqp://guest:guest@localhost:5672/
    queue: inference_requests
    
buffer:
  memory:
    limit: 5000

pipeline:
  processors:
    - mapping: |
        root.model_input = this.prompt
        root.request_id = this.request_id
        root.timestamp = now()

output:
  http_client:
    url: http://ml-service:8080/predict
    verb: POST
    headers:
      Content-Type: application/json
```

### 3. Input Types

#### HTTP Server
```mermaid
graph LR
    A[Client] -->|HTTP Request| B[Benthos HTTP Input]
    B --> C[Processors]
    C --> D[Output]
```

```yaml
input:
  http_server:
    path: /inference
    address: 0.0.0.0:8080
```

#### Message Queue
```mermaid
graph LR
    A[RabbitMQ] --> B[Benthos Queue Input]
    B --> C[Processors]
    C --> D[Output]
```

```yaml
input:
  rabbitmq:
    urls:
      - amqp://guest:guest@localhost:5672/
    queue: inference_requests
```

#### Multiple Inputs
```mermaid
graph LR
    A[HTTP] --> C[Broker]
    B[RabbitMQ] --> C
    C --> D[Processors]
    D --> E[Output]
```

```yaml
input:
  broker:
    inputs:
      - http_server:
          path: /inference
      - rabbitmq:
          queue: inference_requests
```

> **Note:** The following implementation patterns are for conceptual understanding. We will implement these patterns in the project itself as part of our "Asynchronous Architecture Patterns To Scale ML and Other High Latency Workloads on Kubernetes" architecture.

## Implementation Patterns

### 1. API Gateway Pattern
```yaml
# API Gateway Configuration
input:
  http_server:
    path: /api/v1/inference
    address: 0.0.0.0:8080

pipeline:
  processors:
    - mapping: |
        root.request_id = uuid_v4()
        root.timestamp = now()
        root = this

output:
  rabbitmq:
    urls:
      - amqp://guest:guest@rabbitmq:5672/
    exchange: inference
    key: requests
```

> **Implementation Note:** This pattern will be implemented as our API gateway, receiving HTTP requests and forwarding them to RabbitMQ without writing custom code.

### 2. ML Worker Pattern
```yaml
# ML Worker Configuration
input:
  rabbitmq:
    urls:
      - amqp://guest:guest@rabbitmq:5672/
    queue: inference_requests
    consumer_tag: ml-worker

pipeline:
  processors:
    - mapping: |
        root.model_input = this.prompt
        root.parameters = this.parameters
    - http:
        url: http://ml-model:8080/predict
        verb: POST
        headers:
          Content-Type: application/json

output:
  rabbitmq:
    urls:
      - amqp://guest:guest@rabbitmq:5672/
    exchange: inference
    key: responses
```

> **Implementation Note:** This pattern will be implemented to process ML inference requests from RabbitMQ and call the ML model service.

### 3. Error Handling Pattern
```yaml
# Error Handling Configuration
input:
  rabbitmq:
    urls:
      - amqp://guest:guest@rabbitmq:5672/
    queue: inference_requests

pipeline:
  processors:
    - mapping: |
        root = this
    - catch:
        - http:
            url: http://ml-model:8080/predict
            verb: POST
        - mapping: |
            root.error = error()
            root.status = "failed"

output:
  switch:
    cases:
      - check: this.status == "failed"
        output:
          rabbitmq:
            urls:
              - amqp://guest:guest@rabbitmq:5672/
            exchange: inference
            key: errors
      - output:
          rabbitmq:
            urls:
              - amqp://guest:guest@rabbitmq:5672/
            exchange: inference
            key: responses
```

> **Implementation Note:** This pattern will be crucial for handling failed ML inference requests and implementing retry logic.

### 4. Rate Limiting Pattern
```yaml
# Rate Limiting Configuration
input:
  rabbitmq:
    urls:
      - amqp://guest:guest@rabbitmq:5672/
    queue: inference_requests

pipeline:
  processors:
    - rate_limit:
        resource: ml_inference
        rate: 100
        interval: 60s
    - mapping: |
        root = this

output:
  http_client:
    url: http://ml-model:8080/predict
    verb: POST
```

> **Implementation Note:** We'll implement rate limiting to prevent overloading ML services and ensure fair resource allocation.

## Advanced Concepts

### 1. Dynamic Routing
```yaml
# Dynamic Routing Configuration
input:
  http_server:
    path: /inference
    address: 0.0.0.0:8080

pipeline:
  processors:
    - mapping: |
        root = this
        root.model_type = this.model_type

output:
  switch:
    cases:
      - check: this.model_type == "text"
        output:
          rabbitmq:
            exchange: inference
            key: text_model
      - check: this.model_type == "image"
        output:
          rabbitmq:
            exchange: inference
            key: image_model
      - output:
          rabbitmq:
            exchange: inference
            key: default_model
```

> **Implementation Note:** Dynamic routing will be essential for directing requests to the appropriate ML model based on request attributes.

### 2. Batch Processing
```yaml
# Batch Processing Configuration
input:
  rabbitmq:
    urls:
      - amqp://guest:guest@rabbitmq:5672/
    queue: inference_requests

buffer:
  batch:
    count: 10
    period: 1s

pipeline:
  processors:
    - batch:
        processors:
          - mapping: |
              root = this

output:
  http_client:
    url: http://ml-model:8080/batch_predict
    verb: POST
```

> **Implementation Note:** We'll implement batch processing for efficient handling of multiple ML inference requests.

### 3. Circuit Breaker Pattern
```yaml
# Circuit Breaker Configuration
input:
  rabbitmq:
    urls:
      - amqp://guest:guest@rabbitmq:5672/
    queue: inference_requests

pipeline:
  processors:
    - mapping: |
        root = this
    - http:
        url: http://ml-model:8080/predict
        verb: POST
        retry_period: 1s
        max_retry_backoff: 30s
        backoff_on:
          - 429  # Too Many Requests
          - 503  # Service Unavailable
        drop_on:
          - 400  # Bad Request
          - 404  # Not Found

output:
  switch:
    cases:
      - check: error() != null
        output:
          rabbitmq:
            exchange: inference
            key: errors
      - output:
          rabbitmq:
            exchange: inference
            key: responses
```

> **Implementation Note:** We'll implement circuit breakers to prevent cascading failures when ML services are overloaded.

## Observability and Monitoring

### 1. Metrics Configuration
```yaml
# Metrics Configuration
metrics:
  prometheus:
    prefix: benthos
    path_mapping: /metrics
    address: 0.0.0.0:9090
```

### 2. Tracing Configuration
```yaml
# Tracing Configuration
tracer:
  jaeger:
    agent_address: jaeger-agent:6831
    service_name: benthos-ml-pipeline
```

### 3. Logging Configuration
```yaml
# Logging Configuration
logger:
  level: INFO
  format: json
  add_timestamp: true
  static_fields:
    component: benthos
    environment: production
```

## Best Practices

### 1. Configuration Management
- Use environment variables for dynamic configuration
- Split configurations into logical components
- Use version control for configurations
- Implement CI/CD for configuration changes

### 2. Error Handling
- Implement dead letter queues
- Use proper retry mechanisms
- Log failed messages
- Implement circuit breakers

### 3. Performance Optimization
- Use appropriate batch sizes
- Implement rate limiting
- Monitor throughput and latency
- Use resource limits

### 4. Security
- Use TLS for connections
- Implement proper authentication
- Sanitize sensitive data
- Implement proper access controls

## Project Implementation Plan

| Pattern | Component | Description |
|---------|-----------|-------------|
| API Gateway | HTTP Input | Receiving and validating inference requests |
| ML Worker | RabbitMQ Input/Output | Processing inference requests from queues |
| Error Handling | Catch Processors | Handling failed ML inference requests |
| Rate Limiting | Rate Limit Processors | Preventing ML service overload |
| Dynamic Routing | Switch Output | Directing requests to appropriate ML models |
| Batch Processing | Batch Buffer | Efficient processing of multiple requests |
| Circuit Breaker | HTTP Retry | Preventing cascading failures |
| Observability | Prometheus/Jaeger | Monitoring pipeline performance |

## Next Steps
- [Setup Guide](./setup.md)
- [Operations Guide](./operations.md)
- [Project Architecture](../../01-architecture/overview.md) 