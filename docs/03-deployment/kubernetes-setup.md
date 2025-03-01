# Kubernetes Deployment Guide

This guide explains how to deploy the ML Inference Architecture on a Kubernetes cluster.

## Prerequisites

- Kubernetes cluster (v1.19+)
- kubectl installed and configured
- Helm 3+ (for dependent services)
- Kustomize (included with recent kubectl versions)

## Deployment Steps

### 1. Install Infrastructure Components

First, deploy the required infrastructure components:

```bash
# Add Helm repositories
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# Install RabbitMQ
helm install rabbitmq bitnami/rabbitmq -f config/helm/rabbitmq-values.yaml

# Install PostgreSQL
helm install postgresql bitnami/postgresql -f config/helm/postgresql-values.yaml

# Install Redis
helm install redis bitnami/redis -f config/helm/redis-values.yaml

# Install KEDA
helm install keda kedacore/keda -n keda --create-namespace
```

### 2. Create Required Secrets

Create the necessary secrets for component communication:

```bash
# Create Redis credentials secret
kubectl create secret generic redis-credentials \
  --from-literal=url=redis://redis:6379

# Create PostgreSQL credentials secret
# IMPORTANT: Replace 'your-secure-password' with a strong, unique password
kubectl create secret generic postgres-credentials \
  --from-literal=dsn=postgres://postgres:your-secure-password@postgresql:5432/mlservice

# Create RabbitMQ credentials secret
# IMPORTANT: Replace with your actual RabbitMQ credentials
kubectl create secret generic rabbitmq-credentials \
  --from-literal=url=amqp://user:your-secure-password@rabbitmq:5672/
```

> **⚠️ Security Warning**: Never use default or example passwords in production. Generate strong, unique passwords and store them securely. Consider using a secret management solution like HashiCorp Vault or AWS Secrets Manager for production deployments.

### 3. Deploy Benthos Components

Deploy the Benthos components using Kustomize:

```bash
# Apply all Benthos components
kubectl apply -k manifests/benthos/
```

This will deploy:
- API Gateway
- ML Worker
- Results Collector

### 4. Deploy ML Service

Deploy the ML inference service:

```bash
kubectl apply -f manifests/ml-service/ml-inference.yaml
```

### 5. Deploy API Service

Deploy the API service for status checks and quota management:

```bash
kubectl apply -f manifests/api-service/api-service.yaml
```

### 6. Deploy KEDA ScaledObjects

Deploy the KEDA ScaledObjects for autoscaling:

```bash
kubectl apply -f manifests/keda/ml-worker-scaler.yaml
```

## Verify Deployment

Check that all components are running:

```bash
kubectl get pods

# Expected output:
# NAME                                  READY   STATUS    RESTARTS   AGE
# benthos-api-gateway-xxxxxxxxx-xxxxx   1/1     Running   0          30s
# benthos-ml-worker-xxxxxxxxx-xxxxx     1/1     Running   0          30s
# benthos-results-collector-xxxxx-xxxx  1/1     Running   0          30s
# ml-inference-xxxxxxxxx-xxxxx          1/1     Running   0          30s
# api-service-xxxxxxxxx-xxxxx           1/1     Running   0          30s
```

## Access the API

The API Gateway is exposed as a Service of type ClusterIP. To access it:

```bash
# Port forward the API Gateway service
kubectl port-forward svc/benthos-api-gateway 8080:80

# In another terminal, test the API
curl -X POST \
  http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-api-key" \
  -d '{"prompt": "Hello, world!"}'
```

## Scaling

The ML Worker will automatically scale based on the RabbitMQ queue length and token consumption metrics as defined in the KEDA ScaledObject.

## Monitoring

For monitoring instructions, see [Monitoring Setup](../04-operations/monitoring.md). 