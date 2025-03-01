# Kubernetes Manifests

This directory contains the Kubernetes manifests for deploying the ML inference architecture.

## Directory Structure

- **api-service/**: Manifests for the API service component
- **benthos/**: Manifests for the Benthos components (API Gateway, ML Worker, Results Collector)
- **keda/**: ScaledObject definitions for KEDA-based autoscaling
- **ml-service/**: Manifests for the ML inference service

## Deployment Components

### API Service

The API service provides endpoints for checking request status and quota information. It's implemented as a Node.js application.

### Benthos Components

- **api-gateway.yaml**: Deployment for the Benthos API Gateway that receives HTTP requests and forwards them to RabbitMQ
- **ml-worker.yaml**: Deployment for the Benthos ML Worker that processes inference requests from RabbitMQ
- **results-collector.yaml**: Deployment for the Benthos Results Collector that stores processed results in PostgreSQL
- **kustomization.yaml**: Kustomize configuration to generate ConfigMaps from external configuration files

### KEDA Scalers

- **ml-worker-scaler.yaml**: ScaledObject definitions for autoscaling the ML Worker based on queue length and token processing rate

### ML Service

- **ml-inference.yaml**: Deployment for the ML inference service that runs the actual machine learning models

## Deployment

These manifests use Kustomize to generate ConfigMaps from the configuration files in the `config/benthos/` directory. This allows you to manage configurations separately from Kubernetes resources.

To deploy using Kustomize:

```bash
# Apply the Benthos components with Kustomize
kubectl apply -k manifests/benthos/

# Apply other components
kubectl apply -f manifests/ml-service/
kubectl apply -f manifests/api-service/
kubectl apply -f manifests/keda/
```

Alternatively, you can apply all manifests at once:

```bash
# Apply all manifests
kubectl apply -k manifests/
```

## Configuration

The Kustomize setup automatically generates ConfigMaps from external configuration files:

- **API Gateway Configuration**: Generated from `config/benthos/api-gateway/config.yaml`
- **ML Worker Configuration**: Generated from `config/benthos/ml-worker/config.yaml`
- **Common Components**: Generated from files in `config/benthos/common/`

If you modify any configuration files, simply reapply the manifests with Kustomize to update the ConfigMaps.

## Secrets

These manifests reference Secrets that should be created separately:

- **redis-credentials**: Contains Redis connection information
- **postgres-credentials**: Contains PostgreSQL connection information
- **rabbitmq-credentials**: Contains RabbitMQ connection information

Make sure to create these secrets before applying the manifests:

```bash
# Example: Create Redis credentials secret
kubectl create secret generic redis-credentials \
  --from-literal=url=redis://redis:6379

# Example: Create PostgreSQL credentials secret
# IMPORTANT: Replace 'your-secure-password' with a strong, unique password
kubectl create secret generic postgres-credentials \
  --from-literal=dsn=postgres://user:your-secure-password@postgresql:5432/mlservice

# Example: Create RabbitMQ credentials secret
# IMPORTANT: Replace with your actual RabbitMQ credentials
kubectl create secret generic rabbitmq-credentials \
  --from-literal=url=amqp://user:your-secure-password@rabbitmq:5672/
```

> **⚠️ Security Warning**: Never use default or example passwords in production. Generate strong, unique passwords and store them securely. Consider using a secret management solution like HashiCorp Vault or AWS Secrets Manager for production deployments. 