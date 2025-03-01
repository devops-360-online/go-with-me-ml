# KEDA Setup Guide

## What We're Setting Up

In this guide, we'll set up KEDA to automatically scale our ML inference components based on workload metrics:

1. **RabbitMQ-Based Scaling**: Scale Benthos ML workers based on queue length
2. **CPU/Memory-Based Scaling**: Scale ML services based on resource utilization
3. **Latency-Based Scaling**: Scale based on inference response times

This event-driven approach allows us to:
- Optimize resource usage and costs
- Handle traffic spikes automatically
- Maintain consistent performance under varying loads

## Installation Options

### 1. Helm Installation (Recommended)

```bash
# Add KEDA Helm repository
helm repo add kedacore https://kedacore.github.io/charts

# Update Helm repositories
helm repo update

# Install KEDA in its own namespace
kubectl create namespace keda
helm install keda kedacore/keda --namespace keda
```

### 2. Operator Hub Installation

For OpenShift or Operator Hub-enabled Kubernetes:

```bash
# Create namespace
kubectl create namespace keda

# Install KEDA Operator
kubectl apply -f https://operatorhub.io/install/keda.yaml
```

### 3. YAML Installation

```bash
# Apply KEDA CRDs and components
kubectl apply -f https://github.com/kedacore/keda/releases/download/v2.10.1/keda-2.10.1.yaml
```

## Verifying Installation

Check that KEDA components are running:

```bash
kubectl get pods -n keda
```

Expected output:
```
NAME                                      READY   STATUS    RESTARTS   AGE
keda-operator-859b7b8d7f-v5tps            1/1     Running   0          1m
keda-operator-metrics-apiserver-65c4f4565b-9xd7j   1/1     Running   0          1m
```

## Basic Configuration

### 1. RabbitMQ Scaler for Benthos ML Workers

Create a file named `benthos-ml-worker-scaler.yaml`:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: benthos-ml-worker
    kind: Deployment
  minReplicaCount: 1
  maxReplicaCount: 20
  pollingInterval: 15
  cooldownPeriod: 30
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: inference_requests
      host: rabbitmq.ml-inference
      queueLength: "50"
      username: user
      value: "5"
```

Apply the configuration:

```bash
kubectl apply -f benthos-ml-worker-scaler.yaml
```

### 2. CPU/Memory Scaler for ML Service

Create a file named `ml-service-scaler.yaml`:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ml-service-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: ml-service
    kind: Deployment
  minReplicaCount: 1
  maxReplicaCount: 10
  triggers:
  - type: cpu
    metadata:
      type: Utilization
      value: "70"
  - type: memory
    metadata:
      type: Utilization
      value: "80"
```

Apply the configuration:

```bash
kubectl apply -f ml-service-scaler.yaml
```

### 3. Prometheus Scaler for Latency-Based Scaling

First, ensure Prometheus is collecting latency metrics from your ML service.

Create a file named `latency-scaler.yaml`:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ml-service-latency-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: ml-service
    kind: Deployment
  minReplicaCount: 1
  maxReplicaCount: 10
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus.monitoring:9090
      metricName: inference_latency
      threshold: "500"
      query: avg(inference_latency{service="ml-service"})
```

Apply the configuration:

```bash
kubectl apply -f latency-scaler.yaml
```

## Authentication Configuration

### 1. RabbitMQ Authentication

Create a Kubernetes secret for RabbitMQ credentials:

```bash
kubectl create secret generic rabbitmq-creds \
  --from-literal=username=user \
  --from-literal=password=password \
  -n ml-inference
```

Update your ScaledObject to use the secret:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: benthos-ml-worker
    kind: Deployment
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: inference_requests
      host: rabbitmq.ml-inference
      queueLength: "50"
      value: "5"
    authenticationRef:
      name: rabbitmq-trigger-auth
---
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: rabbitmq-trigger-auth
  namespace: ml-inference
spec:
  secretTargetRef:
  - parameter: username
    name: rabbitmq-creds
    key: username
  - parameter: password
    name: rabbitmq-creds
    key: password
```

### 2. Prometheus Authentication

For authenticated Prometheus:

```yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: prometheus-trigger-auth
  namespace: ml-inference
spec:
  secretTargetRef:
  - parameter: bearerToken
    name: prometheus-creds
    key: token
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ml-service-latency-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: ml-service
    kind: Deployment
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus.monitoring:9090
      metricName: inference_latency
      threshold: "500"
      query: avg(inference_latency{service="ml-service"})
    authenticationRef:
      name: prometheus-trigger-auth
```

## Advanced Configurations

### 1. Multi-Metric Scaling

Scale based on both queue length and CPU:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-multi-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: benthos-ml-worker
    kind: Deployment
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: inference_requests
      host: rabbitmq.ml-inference
      queueLength: "50"
      value: "5"
  - type: cpu
    metadata:
      type: Utilization
      value: "70"
```

### 2. Scaling to Zero

Enable scaling to zero for cost optimization:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-zero-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: benthos-ml-worker
    kind: Deployment
  minReplicaCount: 0
  maxReplicaCount: 20
  advanced:
    restoreToOriginalReplicaCount: true
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 300
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: inference_requests
      host: rabbitmq.ml-inference
      queueLength: "1"
      value: "1"
```

### 3. Predictive Scaling with Prometheus

Scale based on predicted workload:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-predictive-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: benthos-ml-worker
    kind: Deployment
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus.monitoring:9090
      query: predict_linear(rabbitmq_queue_messages{queue="inference_requests"}[30m], 600)
      threshold: "10"
```

## Monitoring KEDA

### 1. View Scaling Decisions

Check the HPA created by KEDA:

```bash
kubectl get hpa -n ml-inference
```

### 2. View ScaledObject Status

```bash
kubectl get scaledobject -n ml-inference
```

### 3. Troubleshoot Scaling Issues

```bash
kubectl describe scaledobject benthos-ml-worker-scaler -n ml-inference
```

## Common Configurations for ML Workloads

### 1. GPU-Based ML Service Scaling

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: gpu-ml-service-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: gpu-ml-service
    kind: Deployment
  minReplicaCount: 0
  maxReplicaCount: 5  # Limited by GPU availability
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: gpu_inference_requests
      host: rabbitmq.ml-inference
      queueLength: "10"
      value: "1"
```

### 2. Batch Processing Scaling

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: batch-inference-job-scaler
  namespace: ml-inference
spec:
  jobTargetRef:
    template:
      spec:
        containers:
        - name: batch-processor
          image: ml-batch-processor:latest
          resources:
            limits:
              nvidia.com/gpu: 1
  maxReplicaCount: 5
  pollingInterval: 30
  successfulJobsHistoryLimit: 5
  failedJobsHistoryLimit: 10
  triggers:
  - type: rabbitmq
    metadata:
      queueName: batch_inference_requests
      queueLength: "100"
```

### 3. High-Priority Queue Scaling

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: priority-ml-worker-scaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: priority-ml-worker
    kind: Deployment
  minReplicaCount: 2  # Always keep capacity for high-priority requests
  maxReplicaCount: 10
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: high_priority_requests
      host: rabbitmq.ml-inference
      queueLength: "5"  # Scale aggressively for high-priority
      value: "1"
```

## Next Steps

- [KEDA Concepts](./concepts.md)
- [Operations Guide](./operations.md)
- [Project Architecture](../../01-architecture/overview.md) 