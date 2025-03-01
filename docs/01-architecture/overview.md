# Architecture Overview

## System Design Philosophy

This ML inference architecture is built on several key design principles:

1. **Configuration Over Code**: Using Benthos as a configuration-driven pipeline eliminates the need for custom code in connecting components.

2. **Asynchronous Processing**: Decoupling request handling from processing enables high throughput and resilience.

3. **Resource-Based Quota Management**: Token-based quotas provide accurate resource tracking and fair billing.

4. **Automatic Scaling**: Components scale based on actual workload metrics, including token consumption.

5. **Observability First**: Built-in metrics and monitoring at every layer of the stack.

## High-Level Architecture

```mermaid
graph TD
    Client[Client] -->|HTTP Request| APIGateway[Benthos API Gateway]
    APIGateway -->|Check Quota| Redis[(Redis)]
    APIGateway -->|Store Request| PostgreSQL[(PostgreSQL)]
    APIGateway -->|Queue Request| RabbitMQ[RabbitMQ]
    
    RabbitMQ -->|Consume Request| MLWorker[Benthos ML Worker]
    MLWorker -->|Call Model| MLService[ML Service]
    MLService -->|Return Result| MLWorker
    MLWorker -->|Queue Result| RabbitMQ
    
    RabbitMQ -->|Consume Result| ResultsCollector[Benthos Results Collector]
    ResultsCollector -->|Update Quota| Redis
    ResultsCollector -->|Store Result| PostgreSQL
    
    KEDA[KEDA] -->|Scale Based on Queue| MLWorker
    KEDA -->|Scale Based on Tokens| MLWorker
    KEDA -->|Scale Based on CPU/Memory| MLService
    
    style APIGateway fill:#f96,stroke:#333
    style MLWorker fill:#f96,stroke:#333
    style ResultsCollector fill:#f96,stroke:#333
    style KEDA fill:#6af,stroke:#333
    style Redis fill:#DC382D,stroke:#333,color:white
    style PostgreSQL fill:#336791,stroke:#333,color:white
    style RabbitMQ fill:#FF6600,stroke:#333
    style MLService fill:#00BFFF,stroke:#333
```

## Component Interactions

### Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway as Benthos API Gateway
    participant Redis
    participant DB as PostgreSQL
    participant Queue as RabbitMQ
    participant Worker as Benthos ML Worker
    participant ML as ML Service
    participant Collector as Results Collector
    
    Client->>Gateway: POST /generate
    Gateway->>Gateway: Generate request_id
    Gateway->>Gateway: Estimate tokens
    Gateway->>Redis: Check quotas
    
    alt Quota Exceeded
        Gateway->>Client: 429 Too Many Requests
    else Quota Available
        Gateway->>Redis: Increment request count
        Gateway->>Redis: Reserve estimated tokens
        Gateway->>DB: INSERT INTO requests
        Gateway->>Queue: Publish to inference_requests
        Gateway->>Client: 202 Accepted (request_id)
        
        Client->>Gateway: GET /status/{request_id}
        Gateway->>DB: SELECT status FROM requests
        Gateway->>Client: 200 OK (status: "queued")
        
        Worker->>Queue: Consume from inference_requests
        Worker->>ML: Call inference API
        Note over ML: Process request
        ML->>Worker: Return result with token usage
        Worker->>Queue: Publish to inference_results
        
        Collector->>Queue: Consume from inference_results
        Collector->>Redis: Adjust token quota
        Collector->>DB: UPDATE requests SET result
        
        Client->>Gateway: GET /status/{request_id}
        Gateway->>DB: SELECT status, result FROM requests
        Gateway->>Client: 200 OK (status: "completed", result: "...")
    end
```

### Token-Based Quota Management

```mermaid
flowchart TD
    subgraph "Request Phase"
        A[Receive Request] --> B[Extract User ID]
        B --> C[Estimate Token Usage]
        C --> D{Check Quota}
        D -->|Exceeded| E[Return 429]
        D -->|Available| F[Reserve Estimated Tokens]
        F --> G[Process Request]
    end
    
    subgraph "Response Phase"
        G --> H[Receive Actual Token Usage]
        H --> I[Calculate Adjustment]
        I --> J[Update Token Quota]
        J --> K[Store Usage for Billing]
    end
    
    subgraph "Quota Storage"
        Redis1[(Redis Daily Quota)]
        Redis2[(Redis Monthly Quota)]
        DB[(PostgreSQL Usage Log)]
    end
    
    D -.-> Redis1
    F -.-> Redis1
    J -.-> Redis1
    J -.-> Redis2
    K -.-> DB
```

## Token-Based Scaling

```mermaid
graph TD
    subgraph "Metrics Collection"
        A[Benthos Metrics] -->|Export| B[Prometheus]
        C[ML Service Metrics] -->|Export| B
        D[RabbitMQ Metrics] -->|Export| B
    end
    
    subgraph "KEDA Scaling"
        B -->|Query| E[KEDA Operator]
        E -->|Create/Update| F[HPA]
        F -->|Scale| G[ML Worker Deployment]
        F -->|Scale| H[ML Service Deployment]
    end
    
    subgraph "Scaling Metrics"
        I[Queue Length] -->|Trigger| E
        J[Token Consumption Rate] -->|Trigger| E
        K[CPU/Memory Usage] -->|Trigger| E
    end
```

## Component Details

### 1. Benthos Components

Benthos is used for three key components, all configured without custom code:

#### API Gateway

```yaml
# Simplified API Gateway Configuration
input:
  http_server:
    path: /generate
    
pipeline:
  processors:
    # Extract user ID and check quota
    # Estimate tokens
    # Store request in PostgreSQL
    # ...
    
output:
  rabbitmq:
    url: amqp://guest:guest@rabbitmq:5672/
    exchange: ""
    key: inference_requests
```

#### ML Worker

```yaml
# Simplified ML Worker Configuration
input:
  rabbitmq:
    url: amqp://guest:guest@rabbitmq:5672/
    queue: inference_requests
    
pipeline:
  processors:
    # Transform request for ML service
    # Call ML service
    # Process response
    # ...
    
output:
  rabbitmq:
    url: amqp://guest:guest@rabbitmq:5672/
    exchange: ""
    key: inference_results
```

#### Results Collector

```yaml
# Simplified Results Collector Configuration
input:
  rabbitmq:
    url: amqp://guest:guest@rabbitmq:5672/
    queue: inference_results
    
pipeline:
  processors:
    # Adjust token quota
    # Store result in PostgreSQL
    # ...
    
output:
  # No output needed
```

### 2. Database Schema

#### PostgreSQL

```sql
-- Key tables for token-based quota management
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE quotas (
    quota_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    request_limit INTEGER NOT NULL,
    token_limit INTEGER NOT NULL,
    tier VARCHAR(20) NOT NULL,
    reset_frequency VARCHAR(20) DEFAULT 'monthly',
    UNIQUE(user_id)
);

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
```

#### Redis

```
# Key Redis data structures
user:{user_id}:quota:daily:requests:limit     # Daily request limit
user:{user_id}:quota:daily:requests:used      # Daily requests used
user:{user_id}:quota:daily:tokens:limit       # Daily token limit
user:{user_id}:quota:daily:tokens:used        # Daily tokens used
```

### 3. KEDA Scaling

```yaml
# Token-based scaling configuration
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ml-worker-token-scaler
spec:
  scaleTargetRef:
    name: ml-worker-deployment
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server
        query: sum(rate(ml_tokens_processed_total[5m])) * 60
        threshold: "5000"
```

## Deployment Model

The system is deployed on Kubernetes with the following structure:

```mermaid
graph TD
    subgraph "Kubernetes Cluster"
        subgraph "Control Plane"
            KEDA[KEDA Operator]
            Prometheus[Prometheus]
            Grafana[Grafana]
        end
        
        subgraph "Data Plane"
            subgraph "API Tier"
                APIGateway[Benthos API Gateway]
            end
            
            subgraph "Queue Tier"
                RabbitMQ[RabbitMQ StatefulSet]
            end
            
            subgraph "Processing Tier"
                MLWorker[Benthos ML Worker]
                MLService[ML Service]
            end
            
            subgraph "Collection Tier"
                ResultsCollector[Results Collector]
            end
            
            subgraph "Storage Tier"
                Redis[Redis StatefulSet]
                PostgreSQL[PostgreSQL StatefulSet]
            end
        end
        
        KEDA -->|Scale| MLWorker
        KEDA -->|Scale| MLService
        Prometheus -->|Scrape| APIGateway
        Prometheus -->|Scrape| MLWorker
        Prometheus -->|Scrape| MLService
        Prometheus -->|Scrape| ResultsCollector
        Prometheus -->|Scrape| RabbitMQ
    end
```

## Security Considerations

### Authentication and Authorization

- API Gateway authenticates requests using API keys
- Internal service communication uses mutual TLS
- PostgreSQL and Redis access is restricted to internal services

### Data Protection

- Sensitive data is encrypted at rest in PostgreSQL
- Network traffic is encrypted with TLS
- User data is isolated by user_id

## Performance Characteristics

### Throughput

- API Gateway: 1000+ requests/second
- ML Worker: Scales based on queue length and token consumption
- Results Collector: Matches ML Worker throughput

### Latency

- Request acceptance: < 100ms
- End-to-end processing: Depends on ML model complexity
- Status check: < 50ms

### Scaling Limits

- ML Workers: 0-100 pods based on workload
- ML Services: 1-20 pods based on CPU/memory and token consumption
- API Gateway: 2-10 pods based on HTTP request volume

## Failure Modes and Recovery

### Component Failures

- API Gateway: Multiple replicas with load balancing
- RabbitMQ: Clustered with message persistence
- PostgreSQL: Primary-replica setup with automated failover
- Redis: Sentinel-based high availability

### Recovery Procedures

- Failed requests are retried with exponential backoff
- Dead-letter queues capture unprocessable messages
- Automated database backups with point-in-time recovery

## Monitoring and Observability

### Key Metrics

- Request rate and latency
- Queue length and processing time
- Token consumption rate
- Error rates by component
- Resource utilization

### Dashboards

- System overview
- Component health
- User quota utilization
- ML model performance

## Next Steps

- [Benthos Documentation](../02-core-components/benthos/concepts.md)
- [RabbitMQ Documentation](../02-core-components/rabbitmq/concepts.md)
- [PostgreSQL Documentation](../02-core-components/postgresql/concepts.md)
- [Redis Documentation](../02-core-components/redis/concepts.md)
- [KEDA Documentation](../02-core-components/keda/concepts.md) 