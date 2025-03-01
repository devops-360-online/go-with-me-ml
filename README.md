# ML Inference Architecture

A scalable, token-based architecture for managing machine learning inference workloads on Kubernetes.

## Project Overview

This project implements a configuration-driven approach to ML inference using Benthos for managing asynchronous ML workloads. The architecture focuses on token-based quota management, efficient resource utilization, and autoscaling based on workload demands.

## Repository Structure

- **config/**: Configuration files for Benthos components
- **docs/**: Project documentation
  - **01-architecture/**: Architecture overview and design documents
  - **02-core-components/**: Detailed documentation for each component
  - **03-deployment/**: Deployment guides and instructions
  - **04-operations/**: Operational guidelines and monitoring setup
- **manifests/**: Kubernetes manifests for deploying the system
  - **api-service/**: API service for status and quota management
  - **benthos/**: Benthos components (API Gateway, ML Worker, Results Collector)
  - **keda/**: KEDA ScaledObjects for autoscaling
  - **ml-service/**: ML inference service
  - **migrations/**: Database schema initialization
- **src/**: Source code for custom components
  - **api-service/**: Node.js API for status and quota information
  - **ml-service/**: Sample ML inference service

## Architecture

This project follows a microservices architecture with clear separation of concerns:

### Data Infrastructure Repository

The data infrastructure (PostgreSQL, Redis) is managed in a separate repository:
[go-with-me-data](https://github.com/devops-360-online/go-with-me-data)

### ML Inference Components (This Repository)

- **API Gateway**: Receives HTTP requests, validates them, and forwards to RabbitMQ
- **ML Worker**: Processes inference requests from RabbitMQ and calls ML models
- **Results Collector**: Stores processed results in PostgreSQL
- **ML Service**: Executes the actual machine learning models
- **API Service**: Provides endpoints for checking request status and quota information

## Key Features

- **Token-based Quota Management**: Track and enforce quotas based on token usage
- **Configuration-driven Architecture**: Use Benthos to implement complex flows without custom code
- **Autoscaling with KEDA**: Scale based on queue length and token processing rate
- **Asynchronous Processing**: Handle high-latency ML workloads efficiently
- **Observability**: Comprehensive metrics and logging for monitoring

## Quick Start

See [Kubernetes Deployment Guide](docs/03-deployment/kubernetes-setup.md) for detailed deployment instructions.

### Prerequisites

- Kubernetes cluster (v1.19+)
- kubectl and Helm 3+
- Deployed data infrastructure from [go-with-me-data](https://github.com/devops-360-online/go-with-me-data)

### Basic Deployment Steps

1. Deploy data infrastructure from [go-with-me-data](https://github.com/devops-360-online/go-with-me-data)
2. Initialize database schema: `kubectl apply -f manifests/migrations/init-schema.yaml`
3. Create required secrets for external service connections
4. Deploy RabbitMQ and KEDA
5. Deploy Benthos components: `kubectl apply -k manifests/benthos/`
6. Deploy ML and API services

## Documentation

- [Architecture Overview](docs/01-architecture/overview.md)
- [Benthos Components](docs/02-core-components/benthos/concepts.md)
- [Deployment Guide](docs/03-deployment/kubernetes-setup.md)
- [Monitoring Setup](docs/04-operations/monitoring.md)

## License

MIT
