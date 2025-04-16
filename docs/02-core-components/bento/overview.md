# Bento Overview

## What is Bento?

Bento is an MIT-licensed open-source stream processor that enables data and event routing between various sources and destinations through configuration rather than code. Originally known as Benthos, it was forked by WarpStream to maintain the original open-source approach after Redpanda's acquisition of Benthos.

Key features:
- **Configuration-driven**: Create complex data pipelines with YAML files
- **Stateless design**: Easy horizontal scaling
- **Strong typing**: Manipulate data with a type-safe language (Bloblang)
- **Extensive connectivity**: 70+ integrations with various systems
- **Metrics and tracing**: Built-in observability

## Why Bento for ML Inference?

Traditional ML deployment approaches often require custom code and complex architecture for request handling, queue management, result processing, etc. Bento eliminates this need by:

1. **Simplifying Integration**: Connect any data source to any destination
2. **Reducing Boilerplate**: Handle common patterns without coding
3. **Scaling Easily**: Deploy multiple instances with identical configurations
4. **Improving Operations**: Built-in metrics make monitoring straightforward

## Our Bento Architecture

We use Bento for three key components in our ML inference pipeline:

### 1. API Gateway
```mermaid
graph LR
    A[Client] -->|HTTP Request| B[Bento API Gateway]
    B -->|Validate & Queue| C[RabbitMQ]
    
    style B fill:#f96,stroke:#333
```

The API Gateway:
- Receives client requests
- Validates input and permissions
- Checks token quotas
- Stores request metadata in PostgreSQL
- Queues requests in RabbitMQ

### 2. ML Worker
```mermaid
graph LR
    A[RabbitMQ] -->|Dequeue Request| B[Bento ML Worker]
    B -->|Call API| C[ML Service]
    C -->|Response| B
    B -->|Queue Result| D[RabbitMQ]
    
    style B fill:#f96,stroke:#333
```

The ML Worker:
- Pulls requests from RabbitMQ
- Transforms data for the ML service
- Calls the ML service with the request
- Processes the response
- Queues results back to RabbitMQ

### 3. Results Collector
```mermaid
graph LR
    A[RabbitMQ] -->|Dequeue Result| B[Bento Results Collector]
    B -->|Update| C[PostgreSQL]
    B -->|Adjust Quota| D[Redis]
    
    style B fill:#f96,stroke:#333
```

The Results Collector:
- Pulls results from RabbitMQ
- Updates token usage in Redis
- Stores results in PostgreSQL
- Handles error scenarios

## Benefits of This Architecture

This setup provides several advantages:

1. **Asynchronous Processing**: Clients don't need to wait for ML processing
2. **Automatic Retries**: Failed ML calls are retried according to policy
3. **Quota Management**: Token usage is tracked precisely
4. **Scalable Components**: Each component can scale independently
5. **Configuration Flexibility**: Modify behavior without code changes

## Key Bento Capabilities We Use

### 1. HTTP Server
```yaml
input:
  http_server:
    address: 0.0.0.0:8080
    path: /api/v1/inference
    timeout: 5s
```

### 2. Message Queue Integration
```yaml
output:
  amqp:
    url: amqp://guest:guest@rabbitmq:5672/
    target: inference_requests
```

### 3. Data Transformation
```yaml
processors:
  - bloblang: |
      root.request_id = uuid_v4()
      root.estimated_tokens = ceil(length(this.prompt) / 4)
```

### 4. Database Interaction
```yaml
processors:
  - sql:
      driver: postgres
      dsn: postgres://user:${DB_PASSWORD}@postgres:5432/ml_inference
      query: >
        INSERT INTO requests (request_id, user_id, prompt, status)
        VALUES ($1, $2, $3, 'queued')
``` 