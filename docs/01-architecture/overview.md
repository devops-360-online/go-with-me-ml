# Architecture Overview

## System Design Philosophy in Single Mode

This ML inference architecture is built on several key design principles:

1. **Configuration Over Code**: Using Bento as a configuration-driven pipeline eliminates the need for custom code in connecting components.

2. **Asynchronous Processing**: Decoupling request handling from processing enables high throughput and resilience.

3. **Resource-Based Quota Management**: Token-based quotas provide accurate resource tracking and fair billing.

4. **Automatic Scaling**: Components scale based on actual workload metrics, including token consumption.

5. **Observability First**: Built-in metrics and monitoring at every layer of the stack.

## High-Level Architecture

```mermaid
graph TD
    Client[Client] -->|HTTP Request| APIGateway[Bento API Gateway]
    APIGateway -->|Check Quota| Redis[(Redis)]
    APIGateway -->|Store Request| PostgreSQL[(PostgreSQL)]
    APIGateway -->|Queue Request| RabbitMQ[RabbitMQ]
    
    RabbitMQ -->|Consume Request| MLWorker[Bento ML Worker]
    MLWorker -->|Call Model| MLService[ML Service]
    MLService -->|Return Result| MLWorker
    MLWorker -->|Queue Result| RabbitMQ
    
    RabbitMQ -->|Consume Result| ResultsCollector[Bento Results Collector]
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
    participant Gateway as Bento API Gateway
    participant Redis
    participant DB as PostgreSQL
    participant Queue as RabbitMQ
    participant Worker as Bento ML Worker
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
        A[Bento Metrics] -->|Export| B[Prometheus]
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

### 1. Bento Components

Bento is used for three key components, all configured without custom code:

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
                APIGateway[Bento API Gateway]
            end
            
            subgraph "Queue Tier"
                RabbitMQ[RabbitMQ StatefulSet]
            end
            
            subgraph "Processing Tier"
                MLWorker[Bento ML Worker]
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

- [Bento Documentation](../02-core-components/bento/concepts.md)
- [RabbitMQ Documentation](../02-core-components/rabbitmq/concepts.md)
- [PostgreSQL Documentation](../02-core-components/postgresql/concepts.md)
- [Redis Documentation](../02-core-components/redis/concepts.md)
- [KEDA Documentation](../02-core-components/keda/concepts.md) 

## Client Response Patterns

### The Async Response Challenge

In our async architecture, there's a fundamental gap between request submission and result delivery:

```mermaid
flowchart LR
    A["Client POST /api/gateway"] --> B["202 Accepted + request_id"]
    B --> C["❌ HTTP Connection Closed"]
    C --> D["Background Processing..."]
    D --> E["Results stored in PostgreSQL"]
    E --> F["❓ How does client get results?"]

    style C fill:#FFCDD2
    style F fill:#FFCDD2


```

**The Problem**: Async processing breaks the traditional HTTP request-response pattern. Once the initial request returns `202 Accepted`, the connection closes and we need a separate mechanism to deliver results.

### Solution Approaches

#### 1. 🔄 **Polling (Traditional REST)**

**How it works:**
```mermaid
sequenceDiagram
    participant Client
    participant Gateway as API Gateway
    participant DB as PostgreSQL
    
    Client->>Gateway: POST /api/gateway
    Gateway->>Client: 202 Accepted + request_id
    
    loop Every 2-5 seconds
        Client->>Gateway: GET /api/status/{request_id}
        Gateway->>DB: Check status
        alt Still Processing
            Gateway->>Client: 202 Processing
        else Completed
            Gateway->>Client: 200 OK + result
        end
    end
```

**Implementation Requirements:**
- ✅ Add status endpoint to API Gateway: `GET /api/status/{request_id}`
- ✅ Client polls periodically until result ready

**Pros:**
- ✅ Simple to understand and implement
- ✅ Works with any HTTP client
- ✅ No persistent connections needed
- ✅ Familiar pattern for developers

**Cons:**
- ❌ **Quota inefficiency**: 30+ requests for one result
- ❌ Higher latency (2-5 second delays)
- ❌ Increased server load from repeated requests
- ❌ Network bandwidth waste

**Quota Impact Example:**
```
One ML inference request = 1 quota unit ✅
+ 30 polling requests = 30 wasted quota units ❌
= 31 total quota usage for 1 result 😱
```

#### 2. 📡 **Server-Sent Events (Push Notifications)**

**How it works:**
```mermaid
sequenceDiagram
    participant Client
    participant Gateway as API Gateway
    participant Notifier as Notification Service
    participant Collector as Results Collector
    participant DB as PostgreSQL
    
    Client->>Gateway: POST /api/gateway
    Gateway->>Client: 202 Accepted + request_id
    
    Client->>Notifier: GET /events/{request_id} (SSE)
    Notifier->>Client: SSE: Connected
    
    Note over Gateway, DB: Background processing...
    
    Collector->>DB: Store result
    Collector->>Notifier: HTTP POST notification
    Notifier->>Client: SSE: Result ready + data
```

**Implementation Requirements:**
- ✅ **Notification Service** (FastAPI + asyncio)
- ✅ **Enhanced Results Collector** (add HTTP notification to Bento config)
- ✅ **SSE Client Library** (Python requests + sseclient)

**Pros:**
- ✅ **Quota efficient**: Only 2 requests total (submit + SSE)
- ✅ Real-time delivery (immediate when ready)
- ✅ Low server load (no repeated polling)
- ✅ Excellent modern browser support

**Cons:**
- ❌ More complex architecture (additional service)
- ❌ Requires persistent connection management

**Quota Impact Example:**
```
One ML inference request = 1 quota unit ✅
+ One SSE connection = 0 quota units ✅
= 1 total quota usage for 1 result 🎉
```

#### 3. ⚡ **WebSockets (Bidirectional Real-time)**

**How it works:**
```mermaid
sequenceDiagram
    participant Client
    participant WS as WebSocket Gateway
    
    Client->>WS: Open WebSocket connection
    WS->>Client: Connected
    
    Client->>WS: JSON: Submit request
    Note over WS: Background processing...
    WS->>Client: JSON: Result ready + data
    
    Client->>WS: JSON: Another request
    WS->>Client: JSON: Another result
```

**Implementation Requirements:**
- ✅ **WebSocket Service** (FastAPI + WebSockets)
- ✅ **Message routing** from Results Collector
- ✅ **Connection state management**

**Pros:**
- ✅ Real-time bidirectional communication
- ✅ Very low latency
- ✅ Connection reuse for multiple requests
- ✅ Perfect for streaming mode

**Cons:**
- ❌ Most complex implementation
- ❌ Connection management complexity
- ❌ Firewall/proxy compatibility issues

### Comparison Matrix

| Factor | Polling | SSE | WebSocket |
|--------|---------|-----|-----------|
| **Quota Efficiency** | ❌ Poor (30x usage) | ✅ Excellent (1x usage) | ✅ Excellent (1x usage) |
| **Implementation Complexity** | 🟢 Simple | 🟡 Moderate | 🔴 Complex |
| **Real-time Delivery** | ❌ 2-5s delay | ✅ Immediate | ✅ Immediate |
| **Server Load** | ❌ High | ✅ Low | ✅ Low |
| **Client Compatibility** | ✅ Universal | ✅ 96%+ browsers | 🟡 WebSocket support |
| **Network Efficiency** | ❌ Poor | ✅ Excellent | ✅ Excellent |
| **Implementation Time** | 🟢 1 hour | 🟡 1-2 days | 🔴 2-3 days |
| **Best For** | Simple batch processing | Batch with real-time notifications | Interactive/streaming |

### SSE Implementation Architecture

Since SSE provides the best balance of quota efficiency and real-time delivery for batch processing, here's the detailed implementation:

```mermaid
graph TD
    Client[Client] -->|1. POST /api/gateway| Gateway[API Gateway]
    Gateway -->|2. 202 + request_id| Client
    
    Client -->|3. GET /events/request_id| Notifier[Notification Service]
    Notifier -->|4. SSE stream open| Client
    
    Gateway -->|Queue request| RabbitMQ[RabbitMQ]
    RabbitMQ -->|Process| Worker[ML Worker]
    Worker -->|Result| Collector[Results Collector]
    
    Collector -->|Store result| DB[(PostgreSQL)]
    Collector -->|5. HTTP POST notification| Notifier
    Notifier -->|6. Push via SSE| Client
    
    style Notifier fill:#f9f,stroke:#333
    style Client fill:#bbf,stroke:#333
```

#### Component Details

**1. Notification Service** (New)
```python
# services/notification_service.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()
active_connections = {}  # request_id -> asyncio.Queue

@app.get("/events/{request_id}")
async def sse_stream(request_id: str):
    queue = asyncio.Queue()
    active_connections[request_id] = queue
    
    async def generate():
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=300)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "completed":
                    break
        finally:
            del active_connections[request_id]
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/notify")
async def receive_notification(notification: dict):
    request_id = notification.get("request_id")
    if request_id in active_connections:
        await active_connections[request_id].put(notification)
        return {"status": "sent"}
    return {"status": "no_connection"}
```

**2. Enhanced Results Collector** (Modified Bento Config)
```yaml
# Add to existing results-collector.yml
pipeline:
  processors:
    # ... existing processors ...
    
    # NEW: Send SSE notification
    - branch:
        processors:
          - http:
              url: "${NOTIFICATION_SERVICE_URL}/notify"
              verb: POST
              headers:
                Content-Type: "application/json"
              body: |
                {
                  "type": "completed",
                  "request_id": "${! this.request_id }",
                  "result": ${! this.output },
                  "token_usage": {
                    "prompt_tokens": ${! this.prompt_tokens },
                    "completion_tokens": ${! this.completion_tokens },
                    "total_tokens": ${! this.total_tokens }
                  }
                }
        result_map: root = deleted()
```

**3. SSE Client Library**
```python
# client/sse_client.py
import requests
import sseclient
import json

class SSEMLClient:
    def submit_and_wait(self, prompt: str):
        # Step 1: Submit request
        response = requests.post("/api/gateway", json={"prompt": prompt})
        request_id = response.json()["request_id"]
        
        # Step 2: Wait for result via SSE
        sse_url = f"/events/{request_id}"
        response = requests.get(sse_url, stream=True)
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            data = json.loads(event.data)
            if data["type"] == "completed":
                return data["result"]
```

### Recommended Implementation Path

**Phase SSE** (Recommended)
- Quota efficient for your rate-limited system
- Real-time delivery improves user experience  
- Moderate complexity but manageable
- Perfect for current batch processing needs

### Environment Variables

```bash
# Results Collector (Bento)
NOTIFICATION_SERVICE_URL=http://notification-service:8081

# Notification Service
PORT=8081
LOG_LEVEL=INFO
```

This SSE approach gives you **real-time push notifications without wasting quota requests**, making it ideal for your token-based rate limiting system.

### SSE and HTTP Protocol Versions

#### HTTP/1.1 vs HTTP/2 vs HTTP/3 with SSE

**Important Clarification**: SSE actually works **BETTER** with HTTP/2 and HTTP/3, not worse. Here's the technical reality:

##### HTTP/1.1 (Original SSE)
- ❌ **6 connection limit** per domain (browser restriction)
- ❌ Each SSE stream uses one of these 6 connections
- ❌ With multiple tabs, you quickly hit connection limits
- ✅ Simple, well-tested implementation

##### HTTP/2 (Major Improvement)
- ✅ **100+ concurrent streams** over single TCP connection
- ✅ **Connection multiplexing** - multiple SSE streams share one connection
- ✅ **No 6-connection browser limit** when using HTTP/2
- ✅ Better performance due to header compression and flow control
- ✅ **Eliminates head-of-line blocking** within the same connection

##### HTTP/3 (Latest Standard)
- ✅ Same benefits as HTTP/2 for SSE
- ✅ **UDP-based** - eliminates TCP head-of-line blocking entirely
- ✅ **Better mobile performance** due to connection migration
- ✅ **30.1% of websites** already use HTTP/3 (2024 data)

#### Common Implementation Issues

**The confusion you found likely stems from:**

1. **Server Implementation Bugs**: Some servers/proxies have poor HTTP/2 SSE implementations
2. **Proxy/CDN Issues**: Legacy proxies might interfere with HTTP/2 SSE streams
3. **Configuration Problems**: Incorrectly configured timeouts or buffering

#### When to Force HTTP/1.1

**Only force HTTP/1.1 if you encounter:**
- Specific server/proxy bugs with HTTP/2 SSE
- Legacy infrastructure that doesn't handle HTTP/2 SSE correctly
- Debugging server-side implementation issues

**But remember**: Forcing HTTP/1.1 **reduces performance** by:
- Limiting you to 6 concurrent SSE connections
- Losing HTTP/2's multiplexing benefits
- Missing header compression and flow control

#### SSE is Modern Technology ✅

**SSE is not "old technology":**
- ✅ **HTML Living Standard** (actively maintained by WHATWG)
- ✅ **96%+ browser support** (2024)
- ✅ **Better with modern HTTP** (HTTP/2, HTTP/3)
- ✅ **Perfect for real-time notifications** without WebSocket complexity
- ✅ **Used by major platforms** (Twitter, Facebook, GitHub for live updates)

#### Production Configuration

**For optimal SSE performance:**

```yaml
# Nginx Configuration (example)
server {
    # Enable HTTP/2
    listen 443 ssl http2;
    
    location /events {
        # SSE-specific optimizations
        proxy_set_header Connection '';
        proxy_set_header Cache-Control 'no-cache';
        proxy_set_header X-Accel-Buffering 'no';
        proxy_read_timeout 24h;
        proxy_connect_timeout 5s;
        proxy_send_timeout 24h;
        
        # Forward to your notification service
        proxy_pass http://notification-service:8081;
    }
}
```

**Key Configuration Points:**
- ✅ Use HTTP/2 (don't force HTTP/1.1 unless you have specific issues)
- ✅ Disable proxy buffering (`X-Accel-Buffering: no`)
- ✅ Set long timeouts for SSE endpoints
- ✅ Proper `Content-Type: text/event-stream` headers

#### Browser Compatibility Reality

**SSE HTTP/2 Support** (Excellent):
- ✅ Chrome 6+ (HTTP/2 since v40)
- ✅ Firefox 6+ (HTTP/2 since v36)  
- ✅ Safari 5+ (HTTP/2 since v9)
- ✅ Edge 79+ (Chromium-based)

**Your users get automatic HTTP/2 when available**, falling back to HTTP/1.1 gracefully.

#### Recommendation for Your Architecture

**For your quota-sensitive system:**
1. ✅ **Use SSE with HTTP/2** (default modern behavior)
2. ✅ **Configure proper timeouts** in your load balancer/proxy
3. ✅ **Monitor connection counts** in production
4. ✅ **Test with multiple browser tabs** to verify multiplexing
5. ❌ **Don't force HTTP/1.1** unless you encounter specific bugs

SSE with HTTP/2 is the **optimal choice** for your real-time notification system!

## System Design Philosophy in Streaming Mode

### **Why Streaming Mode is Different**

In **Single Mode** (batch), we process requests like this:
1. Client sends request → wait
2. System processes everything → wait  
3. Client gets complete result

In **Streaming Mode**, we process like this:
1. Client sends request → immediately starts getting partial results
2. System sends each word/token as soon as it's generated
3. Client sees the response being "typed" in real-time

**Key Insight**: Streaming is like watching a video while it's downloading vs. waiting for the entire movie to download first.

### **Core Tools in Our Streaming Architecture**

| Tool | Purpose | Why We Use It |
|------|---------|---------------|
| **Kafka** | Message streaming broker | Handles millions of small token messages efficiently |
| **gRPC** | Communication between services | Built for streaming, faster than REST APIs |
| **Redis** | Fast data storage | Real-time quota tracking and token caching |
| **PostgreSQL** | Permanent data storage | Stores complete requests and billing data |
| **KEDA** | Auto-scaling | Scales workers based on Kafka queue length |
| **Prometheus** | Monitoring | Tracks tokens/second, latency, system health |
| **WebSockets/SSE** | Client connections | Keeps connection open for real-time streaming |

### **Simple Design Principles**

#### **1. Events Tell the Story**
Instead of storing "current state", we store "what happened":
- ❌ **Old way**: "Request status = completed"  
- ✅ **New way**: "Token received → Token received → Request completed"

**Why?** If something breaks, we can replay all the events to rebuild the state.

#### **2. Different Things Have Different Speed Needs**
- **Super Fast** (under 100ms): Checking if user is allowed, starting the request
- **Real-time** (100ms-1s): Sending each token to the user
- **Eventually** (1s+): Saving final results, updating billing

**Why?** Not everything needs to be instant. We optimize each layer for its job.

#### **3. Handle Overload Gracefully**  
When the system gets too busy:
- ❌ **Bad**: Crash or block everything
- ✅ **Good**: Make responses shorter or slightly slower, but keep working

**Example**: Under high load, generate 50 tokens instead of 100, but don't drop user connections.

#### **4. Manage Connection Lifecycles**
Unlike batch requests, streaming creates ongoing relationships:
- **Start**: Authenticate user, reserve resources, open stream
- **During**: Send tokens, handle disconnections, maintain heartbeat
- **End**: Clean up resources, finalize billing, close stream

### **Architecture Patterns (Made Simple)**

#### **1. Different Data, Different Rules**
Not all data needs the same treatment:

| Data Type | Consistency Rule | Example |
|-----------|------------------|---------|
| **Critical** | Must be exact | User's remaining quota |
| **Eventual** | Can be slightly delayed | Total tokens used today |
| **Session** | Consistent per user | User's own request history |

#### **2. Smart Data Placement**
Instead of randomly placing data, we group related things:
- **User Grouping**: All of user123's data goes to the same place
- **Time Grouping**: Active streams separate from old completed requests
- **Priority Grouping**: Premium users get dedicated resources

#### **3. Quality Control Under Load**
When system is stressed, automatically adjust:
- **Response Length**: Shorter answers when busy
- **Processing Speed**: Faster, simpler models when overloaded  
- **Features**: Disable fancy formatting when necessary

**Goal**: Always stay available, even if quality temporarily decreases.

### **System Components and Jobs**

#### **Gateway** (Using WebSockets + Kafka)
**Job**: Be the front door for users
- Accept user requests
- Keep connections open for streaming
- Send tokens to users as they arrive
- Enforce rate limits and quotas

#### **Workers** (Using Kafka + gRPC)  
**Job**: Bridge between requests and AI models
- Take requests from Kafka queue
- Talk to AI model via gRPC streaming
- Send each token back to Kafka as it's generated
- Handle errors and retries

#### **AI Models** (Using gRPC + FastAPI)
**Job**: Generate text/responses
- Accept streaming requests
- Generate tokens one by one
- Send each token immediately (no waiting)
- Report final statistics

#### **Aggregator** (Using Kafka + Redis)
**Job**: Collect and finalize results
- Gather all tokens for each request
- Detect when streaming is complete
- Update quotas and billing
- Store final results in PostgreSQL

### **How the Tools Work Together**

```
User's Browser (WebSocket)
    ↓
Gateway (WebSocket → Kafka)
    ↓  
Kafka (Stream of tokens)
    ↓
Workers (Kafka → gRPC)
    ↓
AI Model (gRPC streaming)
    ↓
Back through the chain...
```

**Real Example**:
1. User types: "Write a story about cats"
2. Gateway puts request in Kafka topic "prompts"
3. Worker picks it up, sends to AI model via gRPC
4. AI generates: "Once" → "upon" → "a" → "time"
5. Each word goes through Kafka topic "tokens"
6. Gateway sends each word to user's browser immediately
7. User sees story appearing word by word

### **Key Benefits of This Design**

1. **Scalable**: Add more workers when Kafka queue gets long
2. **Reliable**: If one part fails, others keep working
3. **Fast**: Users see results immediately, not after everything finishes
4. **Economic**: Pay for exactly what you use, tracked in real-time
5. **Learnable**: Each component has a clear, single job

### **Common Challenges and Solutions**

| Challenge | Solution |
|-----------|----------|
| **Connection drops** | Automatic reconnection with resume capability |
| **Too many requests** | KEDA auto-scales workers based on queue length |
| **Partial failures** | Use Kafka to replay and recover |
| **Quota tracking** | Redis provides real-time usage tracking |
| **System monitoring** | Prometheus tracks every important metric |

This streaming architecture gives users a much better experience while keeping the system manageable and cost-effective.

```mermaid
flowchart TD
  subgraph "Kafka cluster"
      P["prompt (topic)"]:::kafka
      T["tokens (topic)"]:::kafka
  end
  classDef kafka fill:#FF8A4E,stroke:#333,color:#000

  Client((Browser)):::client
  GW["gateway-proxy<br/>(gRPC-web + ws)"]:::svc
  Worker["worker-producer<br/>(Kafka ↔ LLM gRPC)"]:::svc
  Model["LLM service<br/>(bidi gRPC)"]:::svc
  Redis[(Redis)]:::db
  PG[(PostgreSQL)]:::db
  KEDA:::ctrl

  Client-->|ws/SSE tokens|GW
  Client-->|HTTP POST prompt|GW
  GW-->|Kafka produce|P
  Worker-->|Kafka consume|P
  Worker-->|stream prompt|Model
  Model-->|token|Worker
  Worker-->|Kafka produce|T
  GW-->|Kafka filtered consume&nbsp;key=requestId|T
  GW-->|Quota adjust / stats|Redis & PG
  KEDA-.->|lag on&nbsp;prompt|Worker

  classDef svc fill:#F9A825,stroke:#333
  classDef client fill:#00BFFF,stroke:#333
  classDef db fill:#336791,stroke:#FFF,color:#FFF
  classDef ctrl fill:#6af,stroke:#333
```
