# Kubernetes Deployment Guide

This guide outlines the steps to deploy the ML Inference Architecture on Kubernetes.

## Architecture Overview

This project follows a microservices architecture with clear separation of concerns across multiple repositories:

1. **Data Infrastructure** ([go-with-me-data](https://github.com/devops-360-online/go-with-me-data)):
   - PostgreSQL database for storing ML inference requests and results
   - Redis for temporary storage and caching of token usage
   - Other shared data services

2. **ML Inference Architecture** (this repository):
   - API Gateway for receiving and validating requests
   - ML Worker for processing requests
   - Results Collector for storing results
   - ML Service for executing models
   - API Service for checking status and quota

This separation allows for independent evolution and maintenance of data infrastructure and ML inference components.

## Prerequisites

- Kubernetes cluster (v1.19+)
- kubectl CLI installed and configured
- Helm v3+ installed
- Kustomize installed (included with recent kubectl versions)
- Storage class that supports ReadWriteOnce access mode
- Data Infrastructure deployed from [go-with-me-data](https://github.com/devops-360-online/go-with-me-data)

## Security and Resource Management Features

Our Kubernetes manifests implement the following security and resource management best practices:

1. **Service Account Management**:
   - Dedicated service accounts with specific RBAC permissions
   - Automounting of service account tokens disabled for components that don't require API access

2. **Resource Requests and Limits**:
   - All containers define resource requests and limits for CPU, memory, and ephemeral storage
   - Prevents resource starvation and ensures fair resource allocation

3. **Image Security**:
   - Specific version tags for container images instead of `:latest`
   - Ensures deterministic deployments

4. **Persistent Storage**:
   - Components that need persistent storage utilize PersistentVolumeClaims
   - Ensures data durability

5. **Secret Management**:
   - No hardcoded credentials in manifests
   - All sensitive information stored in Kubernetes Secrets

## Deployment Steps

### 1. Deploy Data Infrastructure

Deploy PostgreSQL, Redis, and other data services from the [go-with-me-data](https://github.com/devops-360-online/go-with-me-data) repository:

```bash
# Clone the data infrastructure repository
git clone https://github.com/devops-360-online/go-with-me-data.git
cd go-with-me-data

# Deploy the infrastructure following the instructions in that repository
```

### 2. Initialize Database Schema

Return to this repository directory and initialize the database schema:

```bash
kubectl apply -f manifests/migrations/init-schema.yaml
```

Wait for the job to complete:

```bash
kubectl wait --for=condition=complete job/ml-db-init --timeout=60s
```

### 3. Create Required Secrets

Create secrets for external service connections:

```bash
# Create PostgreSQL credentials secret (use your secure password)
kubectl create secret generic postgres-credentials \
  --from-literal=dsn=postgres://postgres:your-secure-password@postgresql.data-infra:5432/mlservice

# Create RabbitMQ credentials secret (use your secure password)
kubectl create secret generic rabbitmq-credentials \
  --from-literal=url=amqp://user:your-secure-password@rabbitmq:5672/
```

### 4. Deploy RabbitMQ and KEDA

```bash
# Install RabbitMQ using Helm
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install rabbitmq bitnami/rabbitmq

# Install KEDA using Helm
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace
```

### 5. Deploy Benthos Components

```bash
# Apply all Benthos components using Kustomize
kubectl apply -k manifests/benthos/
```

### 6. Deploy ML Service and API Service

```bash
# Deploy ML Service
kubectl apply -f manifests/ml-service/

# Deploy API Service
kubectl apply -f manifests/api-service/
```

## Verification

Check that all pods are running:

```bash
kubectl get pods
```

Test the API Gateway:

```bash
kubectl port-forward svc/api-gateway 8080:80
curl -X POST http://localhost:8080/api/v1/inference -d '{"prompt": "test prompt"}'
```

## Accessing the API

To access the API externally, set up an Ingress or use port-forwarding:

```bash
# Example Ingress (if you have an Ingress controller installed)
kubectl apply -f manifests/ingress.yaml

# Port forwarding for testing
kubectl port-forward svc/api-gateway 8080:80
```

## Scaling

The system uses KEDA for autoscaling based on RabbitMQ queue length:

```bash
# Check ScaledObjects
kubectl get scaledobjects

# Check HPA created by KEDA
kubectl get hpa
```

## Monitoring

Monitor resource utilization:

```bash
# Check pod resource usage
kubectl top pods

# Check node resource usage
kubectl top nodes
```

For detailed monitoring, refer to the [Monitoring Setup](../04-operations/monitoring.md) guide. 