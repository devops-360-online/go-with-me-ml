# ML Inference Architecture

A scalable and production-ready architecture for deploying ML models, with a focus on high throughput, asynchronous processing, token-based quota management, and automatic scaling.

## What This Project Does

This platform helps you:

1. **Run ML models at scale** on Kubernetes
2. **Control costs** with token-based usage tracking
3. **Scale automatically** based on demand
4. **Process requests asynchronously** for better performance

## Project Structure

```
go-with-me-ml/
├── api/                  # API gateway and status service
│   ├── gateway/          # Request handling and validation
│   └── status/           # Status and quota endpoints
├── models/               # ML model services
│   ├── inference/        # Core inference code
│   └── config/           # Model-specific configurations
├── queue/                # Message queue components
│   ├── worker/           # Worker implementation
│   └── collector/        # Results collector
├── infrastructure/       # Infrastructure configuration
│   ├── kubernetes/       # K8s manifests
│   └── monitoring/       # Prometheus/Grafana configs
├── scripts/              # Utility scripts
└── docs/                 # Documentation
```

## How It Works

This project splits responsibilities across two repositories:

### 1. Data Infrastructure ([go-with-me-data](https://github.com/devops-360-online/go-with-me-data))
- PostgreSQL database (stores requests, results, and usage metrics)
- Redis cache (for real-time quota tracking)
- Other shared data services

### 2. ML Inference (This Repository)
- **API Gateway**: Receives requests and queues them in RabbitMQ
- **ML Worker**: Processes requests from the queue
- **Results Collector**: Records completed inference results
- **ML Service**: Runs the actual machine learning models
- **API Service**: Provides request status and quota information

## MLOps Architecture

This project follows MLOps best practices to ensure reliable, scalable, and maintainable ML systems. Our architecture implements the four continuous practices of MLOps:

### Key MLOps Components

1. **Continuous Integration (CI)**
   - Automated testing of code, data, and models
   - Version control for all artifacts
   - Consistent validation processes

2. **Continuous Deployment (CD)**
   - Automated model deployment
   - Containerized model serving
   - Deployment strategies (canary, blue/green)

3. **Continuous Training (CT)**
   - Automated model retraining
   - Performance-based training triggers
   - Model evaluation and promotion

4. **Continuous Monitoring (CM)**
   - Real-time performance tracking
   - Data drift detection
   - Automated alerting

### MLOps Tools Ecosystem

We leverage a variety of tools across different categories:

- **Version Control**: Git, DVC
- **CI/CD**: Jenkins, GitHub Actions
- **Containerization**: Docker, Kubernetes
- **Experiment Tracking**: MLflow, Weights & Biases
- **Monitoring**: Prometheus, Grafana
- **Workflow Orchestration**: Airflow, Kubeflow

For more details on our MLOps implementation, see the [MLOps documentation](docs/00-MLOps/).

## Key Features

- **Token-Based Quota System**: Track and limit usage precisely
- **Configuration-Driven Design**: Build complex workflows with minimal code
- **Auto-Scaling**: Automatically adjust resources based on demand
- **High Throughput**: Process requests asynchronously for better performance
- **Comprehensive Monitoring**: Built-in metrics and logging

## Getting Started

### Prerequisites
- Kubernetes cluster (v1.19+)
- kubectl and Helm 3+
- Deployed data infrastructure from [go-with-me-data](https://github.com/devops-360-online/go-with-me-data)

### Quick Deployment

1. Clone this repository
2. Use the deployment script: `./scripts/deploy.sh`

This script will:

1. Check for prerequisites (kubectl, helm)
2. Create Kubernetes namespace
3. Deploy PostgreSQL database: `kubectl apply -f infrastructure/kubernetes/db/`
4. Deploy Redis cache: `kubectl apply -f infrastructure/kubernetes/cache/`
5. Deploy ML service: `kubectl apply -f infrastructure/kubernetes/ml/`
6. Deploy RabbitMQ and Bento components: `kubectl apply -f infrastructure/kubernetes/queue/`
7. Initialize database schemas: `kubectl apply -f infrastructure/kubernetes/init/`

## Documentation

- [Architecture Overview](docs/01-architecture/overview.md)
- [Component Descriptions](docs/02-core-components/bento/concepts.md)
- [Deployment Guide](docs/03-deployment/kubernetes-setup.md)
- [Monitoring & Operations](docs/04-operations/monitoring.md)
