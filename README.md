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
├── config/                # Configuration templates
│   └── benthos/           # Benthos configuration templates
├── docs/                  # Documentation
├── deployments/           # Deployment files
│   ├── helm/              # Helm charts for third-party components
│   │   ├── keda/          # KEDA auto-scaling configuration
│   │   └── rabbitmq/      # RabbitMQ message broker configuration
│   └── manifests/         # Kubernetes manifests
│       ├── api-service/   # API status service
│       ├── benthos/       # Message processing components
│       ├── keda/          # Auto-scaling configuration
│       ├── ml-service/    # ML model service
│       ├── migrations/    # Database setup
│       └── secrets/       # External service connections
├── scripts/               # Deployment and utility scripts
└── src/                   # Source code
    ├── api-service/       # Status API implementation
    └── ml-service/        # ML service implementation
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

We provide a deployment script that handles the installation of all components:

```bash
# Deploy everything
./scripts/deploy.sh

# Deploy to a specific namespace
./scripts/deploy.sh -n ml-inference

# Skip certain components
./scripts/deploy.sh --skip-rabbitmq --skip-keda
```

### Manual Deployment

If you prefer to deploy components individually:

1. Set up data services: `git clone https://github.com/devops-360-online/go-with-me-data`
2. Create service credentials: 
   ```bash
   kubectl apply -f deployments/manifests/secrets/external-services.yaml
   kubectl apply -f deployments/manifests/secrets/rabbitmq-credentials.yaml
   ```
3. Initialize database: `./scripts/init-database.sh -w`
4. Deploy message broker: `helm install rabbitmq bitnami/rabbitmq -f deployments/helm/rabbitmq/values.yaml`
5. Deploy autoscaler: 
   ```bash
   helm install keda kedacore/keda -f deployments/helm/keda/values.yaml --namespace keda --create-namespace
   kubectl apply -f deployments/manifests/keda/ml-worker-scaler.yaml
   ```
6. Deploy Benthos components: `kubectl apply -f deployments/manifests/benthos/`
7. Deploy services: `kubectl apply -f deployments/manifests/ml-service/ -f deployments/manifests/api-service/`

## Documentation

- [Architecture Details](docs/01-architecture/overview.md)
- [Component Descriptions](docs/02-core-components/benthos/concepts.md)
- [Deployment Guide](docs/03-deployment/kubernetes-setup.md)
- [Operations & Monitoring](docs/04-operations/monitoring.md)

## License

MIT
