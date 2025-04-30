# Repository Organization

This document outlines the improved organization of the ML Inference Architecture repository.

## Directory Structure

```
go-with-me-ml/
├── api/                      # API gateway and status service
│   ├── gateway/              # Bento configuration for the API Gateway
│   │   └── config.yml
│   └── status/               # Status API for checking requests
│       └── Dockerfile        # Status API container definition
│
├── models/                   # ML model services
│   ├── inference/            # Core inference code
│   │   ├── src/              # Inference service implementation
│   │   ├── requirements.txt  # Python dependencies
│   │   └── Dockerfile        # Inference container definition
│   └── config/               # Model-specific configurations
│       ├── distilgpt2/       # DistilGPT2 configuration
│       └── tinyllama/        # TinyLlama configuration
│
├── queue/                    # Message queue processing components
│   ├── worker/               # Bento ML Worker configuration
│   │   └── config.yml        # Worker processing config
│   └── collector/            # Bento Results Collector configuration
│       └── config.yml        # Collector processing config
│
├── infrastructure/           # Infrastructure and deployment
│   ├── kubernetes/           # Kubernetes manifests
│   │   ├── api/              # API Gateway Kubernetes configs
│   │   ├── models/           # ML Service Kubernetes configs
│   │   ├── queue/            # RabbitMQ Kubernetes configs
│   │   └── bento/            # Bento components Helm chart
│   └── monitoring/           # Monitoring configurations
│       ├── prometheus/       # Prometheus configuration
│       └── grafana/          # Grafana dashboards
│
├── scripts/                  # Utility scripts
│   ├── deploy.sh             # Deployment script
│   └── init-database.sh      # Database initialization
│
└── docs/                     # Documentation
    ├── 01-architecture/      # Architecture details
    ├── 02-core-components/   # Component descriptions
    ├── 03-deployment/        # Deployment guides
    └── 04-operations/        # Operations & monitoring
```

## Key Features of the New Structure

### 1. Clear Separation of Concerns

Each major component has its own top-level directory:
- `models/`: Everything related to machine learning
- `infrastructure/`: All Kubernetes and deployment configurations
- `docs/`: Project documentation

### 2. Logical Component Grouping

Components with related functionality are grouped together:
- ML Inference models and configurations in the `models/` directory
- All Kubernetes manifests in the `infrastructure/kubernetes/` directory

### 3. Self-Contained Components

Each component contains everything needed to build and deploy it:
- Docker build files (`Dockerfile`)
- Dependencies (e.g., `requirements.txt` for Python components)

### 4. Improved Deployment Structure

Kubernetes manifests are organized by component type:
- API-related manifests in `infrastructure/kubernetes/bento/`
- Model-related manifests in `infrastructure/kubernetes/models/`
- Queue-related manifests in `infrastructure/kubernetes/queue/`
- Auto-scaling configurations in `infrastructure/kubernetes/keda/`

### 5. Simplified Monitoring

Monitoring configurations are centralized:
- Prometheus configuration in `infrastructure/monitoring/prometheus/`
- Grafana dashboards in `infrastructure/monitoring/grafana/`

## Benefits of the New Structure

1. **Enhanced Maintainability**: Related files are grouped together for easier maintenance
2. **Improved Navigation**: Logical structure makes it easier to find files
3. **Better Modularity**: Components are self-contained for easier development
4. **Clear Dependencies**: Component relationships are made explicit
5. **Simplified Deployments**: Infrastructure configuration is centralized and organized

## Next Steps

1. **Standardize Configuration**: Create consistent configuration formats across components
2. **Implement CI/CD**: Set up pipelines for building and deploying components
3. **Enhance Documentation**: Create component-specific README files
4. **Add Testing**: Implement unit and integration tests for all components

## Stream Processing with Bento

The ML Inference Architecture uses Bento (formerly Benthos) for all stream processing needs. Bento components handle:

1. **API Gateway** : Receives incoming requests, validates them, checks quotas, and forwards to RabbitMQ.

2. **ML Worker** : Retrieves requests from RabbitMQ, calls the ML Service, and forwards results.

3. **Results Collector** : Consumes results from RabbitMQ, updates databases, and manages quotas.

Using Bento provides several advantages:
- **Configuration over code**: Changes to processing logic can be made without code changes
- **Reliable message delivery**: Built-in retry mechanisms ensure processing reliability
- **Observability**: Native metrics and logging provide visibility into the system
- **Scalability**: Stateless design allows simple horizontal scaling 