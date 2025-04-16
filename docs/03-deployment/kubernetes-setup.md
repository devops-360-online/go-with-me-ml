# ML Inference Platform: Kubernetes Deployment Guide

This guide walks you through deploying the ML Inference Platform on Kubernetes step by step.
I'm running in Kind for now testing locally.

## Understanding the Architecture

Our platform uses a microservices approach with components spread across two repositories:

```
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│ Data Infrastructure Repository      │  │ ML Inference Repository (this repo) │
│ (go-with-me-data)                   │  │                                     │
│                                     │  │                                     │
│  ┌───────────┐      ┌───────────┐   │  │  ┌───────────┐      ┌───────────┐  │
│  │PostgreSQL │      │  Redis    │   │  │  │API Gateway│      │ML Worker  │  │
│  │  Database │      │  Cache    │   │  │  │(Benthos)  │      │(Benthos)  │  │
│  └───────────┘      └───────────┘   │  │  └───────────┘      └───────────┘  │
│                                     │  │                                     │
│  ┌───────────┐                      │  │  ┌───────────┐      ┌───────────┐  │
│  │  Other    │                      │  │  │ Results   │      │ML Service │  │
│  │  Services │                      │  │  │ Collector │      │           │  │
│  └───────────┘                      │  │  └───────────┘      └───────────┘  │
│                                     │  │                                     │
└─────────────────────────────────────┘  └─────────────────────────────────────┘
```

### Data Infrastructure (External Repository)
- **PostgreSQL**: Stores requests, results, and token usage
- **Redis**: Tracks real-time quota usage
- Other shared data services

### ML Inference (This Repository)
- **API Gateway**: Receives client requests and queues them
- **ML Worker**: Processes requests from the queue
- **Results Collector**: Records completed inference results
- **ML Service**: Executes machine learning models
- **API Service**: Provides status and quota information

## Prerequisites

Before you begin, make sure you have:

- [ ] Kubernetes cluster (v1.19+)
- [ ] kubectl command-line tool installed and configured
- [ ] Helm v3+ installed for package management
- [ ] Storage class that supports ReadWriteOnce access mode
- [ ] The data infrastructure deployed from [go-with-me-data](https://github.com/devops-360-online/go-with-me-data)

## Security Features

Our Kubernetes manifests implement several security best practices:

| Feature | Description | Benefit |
|---------|-------------|---------|
| Service Account Management | Token mounting disabled when not needed | Reduces attack surface |
| Resource Limits | Explicit CPU/memory limits for all containers | Prevents resource starvation |
| Specific Image Versions | No `:latest` tags, only specific versions | Ensures consistency |
| Persistent Storage | PVCs for all components that need storage | Prevents data loss |
| Secret Management | No hardcoded credentials | Improves security |

## Deployment Process

### Step 1: Deploy Data Infrastructure

First, deploy the external data services:

```bash
# Clone the data infrastructure repository
git clone https://github.com/devops-360-online/go-with-me-data.git
cd go-with-me-data

# Follow the deployment instructions in that repository
```

### Step 2: Initialize Database Schema

Set up the required database tables:

```bash
# Apply the database initialization job
kubectl apply -f manifests/migrations/init-schema.yaml

# Wait for the job to complete
kubectl wait --for=condition=complete job/ml-db-init --timeout=60s
```

### Step 3: Create Service Credentials

Set up the credentials for connecting to external services:

```bash
# Apply all service credentials at once
kubectl apply -f manifests/secrets/external-services.yaml
```

> **Important**: Before deploying to production, replace the placeholder passwords in the secrets files with secure passwords.

### Step 4: Deploy RabbitMQ and KEDA

Set up the message queue and auto-scaling components:

```bash
# Add required Helm repositories
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# Install RabbitMQ
helm install rabbitmq bitnami/rabbitmq

# Install KEDA in its own namespace
helm install keda kedacore/keda --namespace keda --create-namespace
```

### Step 5: Deploy Benthos Components

Deploy the message processing components:

```bash
# Deploy all Benthos components (API Gateway, ML Worker, Results Collector)
kubectl apply -k manifests/benthos/
```

### Step 6: Deploy ML and API Services

Finally, deploy the services that handle ML inference and status information:

```bash
# Deploy ML inference service
kubectl apply -f manifests/ml-service/

# Deploy API service for status checks
kubectl apply -f manifests/api-service/
```

## Verifying the Deployment

Check if all components are running:

```bash
# List all pods
kubectl get pods

# Check deployment status
kubectl get deployments
```

### Testing the API

```bash
# Forward the API Gateway port to your local machine
kubectl port-forward svc/benthos-api-gateway 8080:80

# In another terminal, send a test request
curl -X POST http://localhost:8080/api/v1/inference \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test prompt", "user_id": "test-user", "model": "basic-model"}'
```

You should receive a response with a `request_id` that you can use to check the status later.

## Accessing the API

For production use, you'll want to set up proper external access:

```bash
# Apply an Ingress if you have an Ingress controller
kubectl apply -f manifests/ingress.yaml

# Or use port forwarding for testing
kubectl port-forward svc/benthos-api-gateway 8080:80
```

## Understanding Auto-Scaling

The platform automatically scales based on:

1. **Queue Length**: When requests pile up in RabbitMQ
2. **Token Processing Rate**: When processing many tokens per minute
3. **CPU Usage**: When ML service is under heavy load

You can check the scaling objects:

```bash
# View KEDA ScaledObjects
kubectl get scaledobjects

# View Horizontal Pod Autoscalers created by KEDA
kubectl get hpa
```

## Monitoring

To monitor resource usage:

```bash
# Check pod resource consumption
kubectl top pods

# Check node resource usage
kubectl top nodes
```

For detailed monitoring, see the [Operations Guide](../04-operations/monitoring.md).

## Troubleshooting

Common issues and solutions:

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| Database connection errors | Incorrect credentials or database not ready | Check the `postgres-credentials` secret and ensure the database is running |
| RabbitMQ connection errors | Message queue not ready or wrong credentials | Verify the `rabbitmq-credentials` secret and check RabbitMQ status |
| Pods in "Pending" state | Insufficient cluster resources | Check node capacity with `kubectl describe nodes` |
| Autoscaling not working | KEDA not properly installed | Check KEDA installation with `kubectl get pods -n keda` | 