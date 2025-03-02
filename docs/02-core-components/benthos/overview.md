# Benthos Components Overview

This document provides a simplified explanation of how Benthos components work in our ML Inference Platform.

## What is Benthos?

[Benthos](https://www.benthos.dev/) is a high-performance, configuration-driven data streaming tool. In our platform, we use Benthos to:

1. Receive and validate HTTP requests
2. Save request information in PostgreSQL
3. Process requests through RabbitMQ
4. Collect and store inference results

## Our Benthos Components

We use three primary Benthos components:

```
                 HTTP                    RabbitMQ                  RabbitMQ
┌─────────┐    Request     ┌─────────┐    Queue      ┌─────────┐    Results    ┌─────────┐
│  User   │ ────────────► │   API    │ ───────────► │   ML    │ ───────────► │ Results │
│ Request │               │ Gateway  │              │ Worker  │              │Collector│
└─────────┘               └─────────┘              └─────────┘              └─────────┘
                               │                        │                       │
                               ▼                        ▼                       ▼
                         ┌─────────┐                ┌─────────┐            ┌─────────┐
                         │PostgreSQL│                │   ML    │            │PostgreSQL│
                         │ Database │                │ Service │            │ Database │
                         └─────────┘                └─────────┘            └─────────┘
```

### 1. API Gateway

**Purpose**: Receive HTTP requests and queue them for processing

**Key features**:
- Provides an HTTP endpoint for clients
- Validates request payloads
- Generates unique request IDs
- Estimates token usage
- Stores request metadata in PostgreSQL
- Sends requests to RabbitMQ
- Returns request ID to client

**Configuration highlights**:
```yaml
# Input: HTTP Server
input:
  http_server:
    path: /api/v1/inference
    methods: [POST]

# Processing: Generate ID, store in database
pipeline:
  processors:
    - mapping: |
        root.request_id = uuid_v4()
        # Add other fields...
    - sql_raw:
        # Save to PostgreSQL
        
# Output: Send to queue and respond to client
output:
  broker:
    outputs:
      - amqp_1:  # RabbitMQ
      - sync_response:  # HTTP response
```

### 2. ML Worker

**Purpose**: Process inference requests from the queue

**Key features**:
- Consumes requests from RabbitMQ
- Calls the ML Service for inference
- Tracks token usage
- Sends results to another RabbitMQ queue

**Configuration highlights**:
```yaml
# Input: RabbitMQ queue
input:
  amqp_0:
    queue: ml_requests
    
# Processing: Call ML service
pipeline:
  processors:
    - http:
        url: http://ml-service/inference
        verb: POST
    - mapping: |
        # Process response, calculate tokens
        
# Output: Send results to queue
output:
  amqp_1:
    queue: ml_results
```

### 3. Results Collector

**Purpose**: Store inference results and update quotas

**Key features**:
- Consumes results from RabbitMQ
- Updates request status in PostgreSQL
- Records actual token usage
- Updates user quotas

**Configuration highlights**:
```yaml
# Input: Results queue
input:
  amqp_0:
    queue: ml_results
    
# Processing: Update database
pipeline:
  processors:
    - sql_raw:
        # Update requests table
    - sql_raw:
        # Update token_logs table
        
# Output: Optional metrics
output:
  switch:
    cases:
      - check: this.error
        output:
          # Handle errors
```

## How Data Flows Through the System

1. **Client sends request** → API Gateway
2. API Gateway:
   - Generates request ID
   - Stores request in PostgreSQL
   - Sends to RabbitMQ
   - Returns request ID to client
3. ML Worker:
   - Picks up request from RabbitMQ
   - Calls ML Service for processing
   - Calculates token usage
   - Sends results to another queue
4. Results Collector:
   - Picks up results from queue
   - Updates request status in PostgreSQL
   - Logs token usage
   - Updates user quota

## Benefits of Using Benthos

1. **Declarative Configuration**: Complex data flows defined in YAML
2. **Resilience**: Built-in retry mechanisms and fault tolerance
3. **Observability**: Prometheus metrics and structured logging
4. **Performance**: High throughput with minimal resource usage
5. **Flexibility**: Easily modify data flows without code changes

## Common Operations

### Viewing Benthos Logs

```bash
kubectl logs deployment/benthos-api-gateway
kubectl logs deployment/benthos-ml-worker
kubectl logs deployment/benthos-results-collector
```

### Modifying Configuration

To update a Benthos component:

1. Edit the ConfigMap with the Benthos configuration
2. Apply the changes:
   ```bash
   kubectl apply -f manifests/benthos/api-gateway.yaml
   ```
3. Restart the pod to pick up changes:
   ```bash
   kubectl rollout restart deployment/benthos-api-gateway
   ```

### Checking Metrics

Benthos exposes Prometheus metrics on port 9090:

```bash
kubectl port-forward svc/benthos-api-gateway 9090:9090
```

Then open http://localhost:9090/metrics in your browser. 