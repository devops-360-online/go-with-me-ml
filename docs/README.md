# ML Inference Architecture Documentation

## Project Overview
A scalable, configuration-driven architecture for ML inference workloads on Kubernetes with token-based quota management.

## Documentation Structure

```
docs/
├── 01-architecture/
│   ├── overview.md           # System architecture and components
│   └── data-flow.md          # Data flow and sequence diagrams
│
├── 02-core-components/
│   ├── bento/                # Bento documentation
│   │   ├── concepts.md       # Core concepts and patterns
│   │   ├── setup.md          # Installation and configuration
│   │   ├── operations.md     # Monitoring and maintenance
│   │   └── overview.md       # General overview and background
│   │
│   ├── rabbitmq/             # Message Queue documentation
│   │   ├── concepts.md       # Core concepts and patterns
│   │   ├── setup.md          # Installation and configuration
│   │   └── operations.md     # Monitoring and maintenance
│   │
│   ├── postgresql/           # Database documentation
│   │   ├── concepts.md       # Core concepts
│   │   ├── setup.md          # Installation and configuration
│   │   └── operations.md     # Monitoring and maintenance
│   │
│   ├── redis/                # Redis documentation
│   │   ├── concepts.md       # Core concepts for quota management
│   │   ├── setup.md          # Installation and configuration
│   │   └── operations.md     # Monitoring and maintenance
│   │
│   ├── keda/                 # KEDA documentation
│   │   ├── concepts.md       # Core concepts for autoscaling
│   │   ├── setup.md          # Installation and configuration
│   │   └── operations.md     # Monitoring and maintenance
│   │
│   └── api-service/          # API Service documentation
│       ├── concepts.md       # Core concepts
│       ├── setup.md          # Installation and configuration
│       └── operations.md     # Monitoring and maintenance
│
├── 03-deployment/
│   ├── kubernetes-setup.md   # Kubernetes deployment guide
│   ├── helm-charts.md        # Helm configuration
│   └── scaling.md            # Scaling strategies
│
├── 04-operations/
│   ├── monitoring.md         # Monitoring setup
│   ├── alerting.md           # Alert configuration
│   └── troubleshooting.md    # Common issues and solutions
│
├── images/                   # Documentation images
│
└── ORGANIZATION.md           # Repository organization guide
```

## Key Features

### Token-Based Quota Management
The architecture implements sophisticated token-based quota management to accurately track and limit resource usage:

- **Estimation**: API Gateway estimates token usage based on prompt length
- **Reservation**: Estimated tokens are reserved in Redis quota
- **Processing**: ML service processes the request and reports actual token usage
- **Adjustment**: Results Collector adjusts the quota based on actual usage
- **Tracking**: PostgreSQL stores token usage for billing and analytics

### Configuration-Driven Architecture
The system uses Bento as a configuration-driven tool to connect various components:

- **API Gateway**: Receives HTTP requests, validates them, and forwards them to RabbitMQ
- **ML Worker**: Pulls requests from RabbitMQ, calls ML services, and returns results
- **Results Collector**: Consumes results from RabbitMQ and stores them in PostgreSQL

### Autoscaling with KEDA
The architecture uses KEDA for intelligent autoscaling:

- **Queue-Based Scaling**: Scales based on RabbitMQ queue length
- **Token-Based Scaling**: Scales based on token consumption metrics
- **Resource-Based Scaling**: Scales based on CPU and memory utilization

## Quick Links
- [Architecture Overview](./01-architecture/overview.md)
- [Bento Concepts](./02-core-components/bento/concepts.md)
- [Configuration Templates](../config/)
- [Kubernetes Manifests](../manifests/)
- [Source Code](../src/) 