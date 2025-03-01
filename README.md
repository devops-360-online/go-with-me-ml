# ML Inference Architecture

A scalable, configuration-driven architecture for ML inference workloads on Kubernetes with token-based quota management.

## Architecture Overview

This architecture enables high-throughput, scalable ML inference with sophisticated quota management, automatic scaling, and minimal custom code.

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

## Key Components

### 1. Benthos Components

Benthos serves as the configuration-driven glue connecting all system components:

#### API Gateway
- Receives HTTP requests from clients
- Validates requests and enforces token-based quotas
- Forwards requests to RabbitMQ

#### ML Worker
- Consumes requests from RabbitMQ
- Calls ML services
- Returns results to response queues

#### Results Collector
- Consumes results from RabbitMQ
- Updates token quotas with actual usage
- Stores results in PostgreSQL

### 2. Message Queue (RabbitMQ)

- Decouples components for scalability
- Provides reliable message delivery
- Supports priority queues for important requests

### 3. Databases

#### Redis
- Manages real-time token and request quotas
- Provides rate limiting
- Enables fast lookups and caching

#### PostgreSQL
- Stores request history and results
- Tracks token usage for billing
- Maintains user accounts and quotas

### 4. Autoscaling (KEDA)

- Scales ML workers based on queue length
- Scales based on token consumption metrics
- Scales to zero when idle to save costs

### 5. ML Services

- Containerized ML models
- Expose prediction APIs
- Report token usage metrics

## Token-Based Quota Management

This architecture implements sophisticated token-based quota management to accurately track and limit resource usage:

```mermaid
sequenceDiagram
    participant Client
    participant Gateway as Benthos API Gateway
    participant Redis
    participant Queue as RabbitMQ
    participant Worker as Benthos ML Worker
    participant ML
    participant Collector as Results Collector
    participant DB as PostgreSQL
    
    Client->>Gateway: Submit Request
    Gateway->>Gateway: Estimate tokens from prompt
    Gateway->>Redis: Check request quota
    Gateway->>Redis: Check token quota
    
    alt Quota Exceeded
        Gateway->>Client: 429 Too Many Requests
    else Quota Available
        Gateway->>Redis: Increment request count
        Gateway->>Redis: Reserve estimated tokens
        Gateway->>DB: Store request with estimated tokens
        Gateway->>Queue: Enqueue request
        Gateway->>Client: Return request_id
        
        Worker->>Queue: Dequeue request
        Worker->>ML: Process request
        ML->>Worker: Return result with actual token usage
        Worker->>Queue: Enqueue result
        
        Collector->>Queue: Dequeue result
        Collector->>Redis: Adjust token quota (estimated vs actual)
        Collector->>DB: Update request with actual token usage
    end
```

### Token Quota Flow

1. **Estimation**: API Gateway estimates token usage based on prompt length
2. **Reservation**: Estimated tokens are reserved in Redis quota
3. **Processing**: ML service processes the request and reports actual token usage
4. **Adjustment**: Results Collector adjusts the quota based on actual usage
5. **Tracking**: PostgreSQL stores token usage for billing and analytics

## Data Flow

```mermaid
flowchart LR
    subgraph "Client Layer"
        Client[Client Application]
    end
    
    subgraph "API Layer"
        Gateway[Benthos API Gateway]
    end
    
    subgraph "Queue Layer"
        RMQ[RabbitMQ]
    end
    
    subgraph "Processing Layer"
        Worker[Benthos ML Worker]
        ML[ML Service]
    end
    
    subgraph "Storage Layer"
        Redis[(Redis)]
        Postgres[(PostgreSQL)]
    end
    
    subgraph "Collection Layer"
        Collector[Results Collector]
    end
    
    subgraph "Scaling Layer"
        KEDA[KEDA Autoscaler]
    end
    
    Client -->|1. HTTP Request| Gateway
    Gateway -->|2. Check Quota| Redis
    Gateway -->|3. Store Request| Postgres
    Gateway -->|4. Queue Request| RMQ
    RMQ -->|5. Consume Request| Worker
    Worker -->|6. Call Model| ML
    ML -->|7. Return Result| Worker
    Worker -->|8. Queue Result| RMQ
    RMQ -->|9. Consume Result| Collector
    Collector -->|10. Adjust Quota| Redis
    Collector -->|11. Store Result| Postgres
    KEDA -->|12. Scale Workers| Worker
    KEDA -->|13. Scale ML Service| ML
```

## Deployment Architecture

The system is deployed on Kubernetes with the following components:

```mermaid
graph TD
    subgraph "Kubernetes Cluster"
        subgraph "API Namespace"
            APIGateway[Benthos API Gateway]
            APIService[Status API Service]
        end
        
        subgraph "Queue Namespace"
            RabbitMQ[RabbitMQ Cluster]
        end
        
        subgraph "Worker Namespace"
            MLWorker[Benthos ML Worker]
            MLService[ML Service]
        end
        
        subgraph "Storage Namespace"
            Redis[(Redis)]
            PostgreSQL[(PostgreSQL)]
        end
        
        subgraph "Collection Namespace"
            ResultsCollector[Results Collector]
        end
        
        subgraph "Monitoring Namespace"
            Prometheus[Prometheus]
            Grafana[Grafana]
        end
        
        Ingress[Ingress Controller] -->|Route /api| APIGateway
        Ingress -->|Route /status| APIService
        
        KEDA[KEDA Operator] -->|Scale| MLWorker
        KEDA -->|Scale| MLService
    end
    
    Client[Client] -->|HTTPS| Ingress
```

## Token-Based Autoscaling

KEDA scales components based on both queue length and token consumption:

```mermaid
graph TD
    subgraph "Metrics Sources"
        Queue[RabbitMQ Queue Length]
        Tokens[Token Consumption Rate]
        CPU[CPU Utilization]
    end
    
    subgraph "KEDA ScaledObjects"
        QueueScaler[Queue-Based Scaler]
        TokenScaler[Token-Based Scaler]
        HybridScaler[Hybrid Scaler]
    end
    
    subgraph "Deployments"
        MLWorker[ML Worker Pods]
        MLService[ML Service Pods]
    end
    
    Queue -->|Queue Length Metric| QueueScaler
    Tokens -->|Token Rate Metric| TokenScaler
    Queue -->|Queue Length Metric| HybridScaler
    Tokens -->|Token Rate Metric| HybridScaler
    CPU -->|CPU Metric| HybridScaler
    
    QueueScaler -->|Scale| MLWorker
    TokenScaler -->|Scale| MLWorker
    HybridScaler -->|Scale| MLService
```

## Component Documentation

For detailed documentation on each component:

- [Benthos Documentation](docs/02-core-components/benthos/concepts.md)
- [RabbitMQ Documentation](docs/02-core-components/rabbitmq/concepts.md)
- [PostgreSQL Documentation](docs/02-core-components/postgresql/concepts.md)
- [Redis Documentation](docs/02-core-components/redis/concepts.md)
- [KEDA Documentation](docs/02-core-components/keda/concepts.md)
- [Architecture Overview](docs/01-architecture/overview.md)

## Getting Started

### Prerequisites

- Kubernetes cluster
- Helm 3+
- kubectl

### Installation

```bash
# Add Helm repositories
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# Install RabbitMQ
helm install rabbitmq bitnami/rabbitmq -f helm-values/rabbitmq-values.yaml

# Install PostgreSQL
helm install postgresql bitnami/postgresql -f helm-values/postgresql-values.yaml

# Install Redis
helm install redis bitnami/redis -f helm-values/redis-values.yaml

# Install KEDA
helm install keda kedacore/keda -n keda --create-namespace

# Deploy Benthos components
kubectl apply -f k8s/benthos/
```

### Configuration

The system is primarily configured through:

1. **Benthos YAML files**: Define data flows and transformations
2. **Kubernetes manifests**: Define deployment parameters
3. **KEDA ScaledObjects**: Define scaling behaviors

## License

[MIT License](LICENSE)

## Architecture Improvements

After reviewing the initial implementation, we've identified several improvements to enhance maintainability, reduce duplication, and improve separation of concerns:

### 1. Configuration Management

- **Centralized Configuration**: Move all environment-specific configuration to Helm values or Kustomize overlays
- **DRY Benthos Configs**: Use Benthos includes/imports to share common configuration blocks
- **ConfigMap Generation**: Generate Kubernetes ConfigMaps from the source Benthos YAML files

### 2. Component Decoupling

- **API Service Refactoring**:
  - Move token estimation to a separate microservice or library
  - Separate quota management logic from request handling
  - Use dependency injection for database and message queue clients

- **Benthos Pipeline Modularization**:
  - Break down large pipelines into smaller, reusable components
  - Use Benthos resources for common processors

### 3. Deployment Simplification

- **Helm Charts**: Create Helm charts for each component with shared values
- **CI/CD Pipeline**: Automate deployment with proper environment separation
- **Secrets Management**: Use Kubernetes secrets for sensitive information

### 4. Code Organization

```
├── src/
│   ├── api-service/           # Node.js API service
│   │   ├── src/
│   │   │   ├── controllers/   # Request handlers
│   │   │   ├── services/      # Business logic
│   │   │   ├── models/        # Data models
│   │   │   ├── utils/         # Utilities (including tokenizer)
│   │   │   └── config/        # Configuration
│   │   └── ...
│   │
│   ├── ml-inference/          # Python ML service
│   │   ├── app/
│   │   │   ├── models/        # ML model wrappers
│   │   │   ├── api/           # API endpoints
│   │   │   ├── utils/         # Utilities
│   │   │   └── config/        # Configuration
│   │   └── ...
│   │
│   └── shared-libs/           # Shared libraries
│       ├── token-estimation/  # Token estimation library
│       └── quota-management/  # Quota management library
│
├── config/
│   ├── benthos/
│   │   ├── common/            # Shared Benthos components
│   │   ├── api-gateway/       # API Gateway specific configs
│   │   ├── ml-worker/         # ML Worker specific configs
│   │   └── results-collector/ # Results Collector specific configs
│   │
│   ├── database/              # Database schemas and migrations
│   └── redis/                 # Redis schemas and scripts
│
├── deploy/
│   ├── helm/                  # Helm charts
│   │   ├── api-service/
│   │   ├── ml-inference/
│   │   ├── benthos/
│   │   └── common/            # Shared Helm templates
│   │
│   └── kubernetes/            # Raw Kubernetes manifests
│       ├── base/              # Base configurations
│       └── overlays/          # Environment-specific overlays
│
└── scripts/                   # Utility scripts
    ├── local-dev/             # Local development setup
    ├── ci/                    # CI/CD scripts
    └── monitoring/            # Monitoring setup
```

### 5. Monitoring and Observability

- **Unified Logging**: Implement structured logging across all components
- **Centralized Metrics**: Standardize metrics collection and dashboards
- **Distributed Tracing**: Add OpenTelemetry tracing for request flows

### 6. Testing Strategy

- **Unit Tests**: For individual components
- **Integration Tests**: For component interactions
- **End-to-End Tests**: For complete flows
- **Load Tests**: For performance and scaling validation

These improvements will make the system more maintainable, easier to understand, and more robust as it grows.