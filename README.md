# ML Inference Architecture

A Kubernetes-based platform for scalable machine learning inference with automatic scaling and quota management.

## What This Project Does

This platform helps you:

1. **Run ML models at scale** on Kubernetes
2. **Control costs** with token-based usage tracking
3. **Scale automatically** based on demand
4. **Process requests asynchronously** for better performance

## Project Structure

```
ml-inference/
├── config/              # Configuration templates
├── docs/                # Documentation
├── manifests/           # Kubernetes deployment files
│   ├── api-service/     # API status service
│   ├── benthos/         # Message processing components
│   ├── keda/            # Auto-scaling configuration
│   ├── ml-service/      # ML model service
│   ├── migrations/      # Database setup
│   └── secrets/         # External service connections
└── src/                 # Source code
    ├── api-service/     # Status API implementation
    └── ml-service/      # ML service implementation
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
1. Set up data services: `git clone https://github.com/devops-360-online/go-with-me-data`
2. Initialize database: `kubectl apply -f manifests/migrations/init-schema.yaml`
3. Create service credentials: `kubectl apply -f manifests/secrets/external-services.yaml`
4. Deploy message broker: `helm install rabbitmq bitnami/rabbitmq`
5. Deploy autoscaler: `helm install keda kedacore/keda --namespace keda --create-namespace`
6. Deploy ML components: `kubectl apply -k manifests/benthos/`
7. Deploy services: `kubectl apply -f manifests/ml-service/ -f manifests/api-service/`

## Documentation

- [Architecture Details](docs/01-architecture/overview.md)
- [Component Descriptions](docs/02-core-components/benthos/concepts.md)
- [Deployment Guide](docs/03-deployment/kubernetes-setup.md)
- [Operations & Monitoring](docs/04-operations/monitoring.md)

## License

MIT
