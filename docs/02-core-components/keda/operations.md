# KEDA Operations Guide

## Monitoring KEDA Performance

### 1. Key Metrics to Monitor

| Metric | Description | Threshold |
|--------|-------------|-----------|
| `keda_metrics_adapter_scaler_errors_total` | Errors in scaling operations | > 0 |
| `keda_metrics_adapter_scaled_object_errors_total` | Errors in ScaledObject processing | > 0 |
| `keda_operator_scaled_object_reconcile_duration_seconds` | Time to reconcile ScaledObjects | > 5s |
| `keda_operator_scale_target_access_duration_seconds` | Time to access scale targets | > 2s |
| `keda_metrics_adapter_collector_duration_seconds` | Time to collect metrics | > 3s |

### 2. Prometheus Queries

Example Grafana dashboard queries:

```
# Scaling Error Rate
sum(rate(keda_metrics_adapter_scaler_errors_total[5m])) by (namespace, scaledObject)

# Reconciliation Time
histogram_quantile(0.95, sum(rate(keda_operator_scaled_object_reconcile_duration_seconds_bucket[5m])) by (le, namespace, scaledObject))

# Active ScaledObjects
sum(keda_metrics_adapter_scaled_object_active) by (namespace)
```

### 3. Log Monitoring

Key log patterns to watch for:

- `Error getting metrics for trigger` - Indicates issues with metrics collection
- `Error calculating target metrics` - Problems with metric calculations
- `Error scaling target` - Issues with scaling operations

Example log query in Loki:
```
{namespace="keda"} |= "Error" | logfmt | count_over_time([5m]) > 0
```

## Scaling Behavior Analysis

### 1. Analyzing Scaling Decisions

Check the HPA created by KEDA:

```bash
kubectl get hpa -n ml-inference
```

View detailed scaling history:

```bash
kubectl describe hpa benthos-ml-worker-scaler-hpa -n ml-inference
```

Look for:
- Current/target metric values
- Last scaling time
- Events showing scaling decisions

### 2. Scaling Metrics Validation

Verify that KEDA is receiving the correct metrics:

```bash
# For RabbitMQ queue length
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1/namespaces/ml-inference/rabbitmq-inference_requests?labelSelector=scaledobject.keda.sh/name=benthos-ml-worker-scaler" | jq
```

Expected output:
```json
{
  "kind": "ExternalMetricValueList",
  "apiVersion": "external.metrics.k8s.io/v1beta1",
  "metadata": {},
  "items": [
    {
      "metricName": "rabbitmq-inference_requests",
      "metricLabels": {
        "host": "rabbitmq.ml-inference",
        "queue": "inference_requests"
      },
      "timestamp": "2023-05-15T10:30:45Z",
      "value": "42"
    }
  ]
}
```

### 3. Scaling Lag Analysis

Monitor the time between metric change and scaling action:

```bash
# Get current queue length
kubectl exec -it rabbitmq-0 -n ml-inference -- rabbitmqctl list_queues name messages

# Watch HPA status
kubectl get hpa benthos-ml-worker-scaler-hpa -n ml-inference -w

# Watch pod count
kubectl get pods -l app=benthos-ml-worker -n ml-inference -w
```

## Troubleshooting

### 1. Common Issues and Solutions

| Issue | Possible Causes | Solutions |
|-------|----------------|-----------|
| No scaling despite queue growth | Authentication issues, incorrect queue name | Check KEDA logs, verify queue name and credentials |
| Scaling too slowly | Long polling interval, stabilization window | Adjust pollingInterval, modify HPA behavior |
| Scaling to zero issues | Cooldown period too short | Increase cooldownPeriod, check idleReplicaCount |
| Excessive scaling | Metric fluctuations, low thresholds | Increase threshold, add stabilization window |

### 2. Debugging Techniques

#### Check KEDA Operator Logs

```bash
kubectl logs -l app=keda-operator -n keda
```

#### Check Metrics Adapter Logs

```bash
kubectl logs -l app=keda-metrics-apiserver -n keda
```

#### Verify ScaledObject Status

```bash
kubectl get scaledobject benthos-ml-worker-scaler -n ml-inference -o yaml
```

Look for:
- `status.conditions` - Check for any error conditions
- `status.scaleTargetGVKR` - Verify target is correct
- `status.lastActiveTime` - Check when scaling was last active

### 3. Recovery Procedures

#### Restart KEDA Components

If KEDA is not functioning correctly:

```bash
# Restart KEDA operator
kubectl rollout restart deployment keda-operator -n keda

# Restart metrics adapter
kubectl rollout restart deployment keda-metrics-apiserver -n keda
```

#### Recreate Problematic ScaledObjects

```bash
# Delete and recreate ScaledObject
kubectl delete scaledobject benthos-ml-worker-scaler -n ml-inference
kubectl apply -f benthos-ml-worker-scaler.yaml
```

## Performance Tuning

### 1. Polling Interval Optimization

Balance responsiveness vs. resource usage:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-scaler
spec:
  pollingInterval: 15  # Check every 15 seconds
  # For high-priority workloads, reduce to 5-10 seconds
  # For batch workloads, increase to 30-60 seconds
```

### 2. Cooldown Period Tuning

Prevent scaling thrashing:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-scaler
spec:
  cooldownPeriod: 300  # Wait 5 minutes after scaling before scaling down
  # For volatile workloads, increase to 10-15 minutes
  # For stable workloads, decrease to 2-3 minutes
```

### 3. Advanced HPA Behavior

Fine-tune scaling behavior:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-scaler
spec:
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 300
          policies:
          - type: Percent
            value: 20
            periodSeconds: 60
        scaleUp:
          stabilizationWindowSeconds: 0
          policies:
          - type: Pods
            value: 4
            periodSeconds: 60
          - type: Percent
            value: 100
            periodSeconds: 60
          selectPolicy: Max
```

## High Availability Setup

### 1. KEDA Redundancy

Ensure KEDA is deployed with multiple replicas:

```yaml
# In Helm values
operator:
  replicaCount: 2

metricsServer:
  replicaCount: 2
```

### 2. Multi-Zone Deployment

Deploy KEDA across multiple availability zones:

```yaml
# In Helm values
operator:
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values:
              - keda-operator
          topologyKey: topology.kubernetes.io/zone

metricsServer:
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values:
              - keda-metrics-apiserver
          topologyKey: topology.kubernetes.io/zone
```

### 3. Fallback Configurations

Ensure workloads can function if KEDA fails:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: benthos-ml-worker-scaler
spec:
  fallback:
    failureThreshold: 3
    replicas: 5
```

This ensures that if KEDA fails to get metrics 3 times, it will maintain 5 replicas.

## Maintenance Procedures

### 1. Upgrading KEDA

```bash
# Using Helm
helm repo update
helm upgrade keda kedacore/keda --namespace keda

# Verify upgrade
kubectl get deployment -n keda
```

### 2. Backing Up KEDA Resources

```bash
# Backup all ScaledObjects
kubectl get scaledobjects --all-namespaces -o yaml > scaledobjects-backup.yaml

# Backup all TriggerAuthentications
kubectl get triggerauthentications --all-namespaces -o yaml > triggerauths-backup.yaml

# Backup all ScaledJobs
kubectl get scaledjobs --all-namespaces -o yaml > scaledjobs-backup.yaml
```

### 3. Migrating KEDA Between Clusters

```bash
# Export from source cluster
kubectl get scaledobjects -n ml-inference -o yaml > scaledobjects-export.yaml
kubectl get triggerauthentications -n ml-inference -o yaml > triggerauths-export.yaml

# Edit resources to match target environment
# (Update hostnames, endpoints, etc.)

# Import to target cluster
kubectl apply -f scaledobjects-export.yaml
kubectl apply -f triggerauths-export.yaml
```

## ML-Specific Operational Patterns

### 1. Handling Model Reloading

When deploying new ML models, temporarily adjust scaling:

```bash
# Before model update, increase min replicas
kubectl patch scaledobject ml-service-scaler -n ml-inference --type=merge -p '{"spec":{"minReplicaCount": 5}}'

# Deploy new model version
kubectl apply -f ml-service-new-model.yaml

# After successful deployment and warm-up, restore normal scaling
kubectl patch scaledobject ml-service-scaler -n ml-inference --type=merge -p '{"spec":{"minReplicaCount": 1}}'
```

### 2. Handling Batch Inference Jobs

For periodic batch processing:

```bash
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: nightly-batch-inference
spec:
  jobTargetRef:
    template:
      spec:
        containers:
        - name: batch-processor
          image: ml-batch-processor:latest
  schedule: "0 0 * * *"  # Run at midnight
  maxReplicaCount: 10
  triggers:
  - type: rabbitmq
    metadata:
      queueName: nightly_batch_queue
      queueLength: "1"  # Start as soon as there's a message
```

### 3. Cost Optimization Strategies

Implement day/night scaling profiles:

```bash
# Daytime profile (8am-8pm)
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ml-service-daytime-scaler
spec:
  scaleTargetRef:
    name: ml-service
  minReplicaCount: 2
  maxReplicaCount: 20
  triggers:
  - type: cron
    metadata:
      timezone: UTC
      start: 0 8 * * *
      end: 0 20 * * *
      desiredReplicas: "2"
  - type: rabbitmq
    metadata:
      queueName: inference_requests
      queueLength: "20"

# Nighttime profile (8pm-8am)
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ml-service-nighttime-scaler
spec:
  scaleTargetRef:
    name: ml-service
  minReplicaCount: 0
  maxReplicaCount: 5
  triggers:
  - type: cron
    metadata:
      timezone: UTC
      start: 0 20 * * *
      end: 0 8 * * *
      desiredReplicas: "0"
  - type: rabbitmq
    metadata:
      queueName: inference_requests
      queueLength: "50"
```

## Next Steps

- [KEDA Concepts](./concepts.md)
- [Setup Guide](./setup.md)
- [Project Architecture](../../01-architecture/overview.md) 