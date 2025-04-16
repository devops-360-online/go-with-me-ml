# Bento Operations Guide

## Monitoring and Observability

### 1. Key Metrics to Monitor

| Metric | Description | Threshold |
|--------|-------------|-----------|
| `bento_input_received` | Messages received by input | Rate change > 20% |
| `bento_output_sent` | Messages sent by output | Rate change > 20% |
| `bento_processor_latency` | Processing time | > 500ms |
| `bento_output_error` | Output errors | > 0 |
| `bento_input_connection_up` | Input connection status | 0 = down |
| `bento_output_connection_up` | Output connection status | 0 = down |

### 2. Prometheus Dashboard

Example Grafana dashboard queries:

```
# Input/Output Rate
rate(bento_input_received_total[5m])
rate(bento_output_sent_total[5m])

# Error Rate
rate(bento_output_error_total[5m])

# Processing Latency
histogram_quantile(0.95, sum(rate(bento_processor_latency_seconds_bucket[5m])) by (le))
```

### 3. Log Monitoring

Bento logs in JSON format by default. Key fields to monitor:

- `level`: Watch for `error` and `warn` levels
- `component`: Identifies which component generated the log
- `message`: Description of the event

Example log query in Loki:
```
{app="bento"} | json | level="error" | count_over_time([5m]) > 0
```

## Scaling Strategies

### 1. Vertical Scaling

Increase resources for Bento pods:

```yaml
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi
```

### 2. Horizontal Scaling

Scale based on queue length:

1. Deploy the RabbitMQ Prometheus exporter
2. Configure Prometheus to scrape RabbitMQ metrics
3. Set up HPA with custom metrics:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bento-ml-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bento-ml-worker
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: External
    external:
      metric:
        name: rabbitmq_queue_messages
        selector:
          matchLabels:
            queue: inference_requests
      target:
        type: AverageValue
        averageValue: 100
```

### 3. Scaling with KEDA

KEDA provides more advanced scaling options for Bento:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: bento-ml-worker-scaler
spec:
  scaleTargetRef:
    name: bento-ml-worker
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
  - type: rabbitmq
    metadata:
      protocol: amqp
      queueName: inference_requests
      host: amqp://guest:guest@rabbitmq:5672/
      queueLength: "50"  # Target queue length per replica
```

### 4. Scaling Considerations

- **Input Rate**: Scale based on message ingestion rate
- **Processing Complexity**: Scale based on processor latency
- **Output Backpressure**: Monitor output errors and backpressure

## Performance Tuning

### 1. Buffer Configuration

Adjust buffer settings for throughput vs. latency:

```yaml
buffer:
  memory:
    limit: 10000  # Increase for throughput, decrease for latency
```

For batch processing:

```yaml
buffer:
  batch:
    count: 20     # Increase for throughput
    period: 1s    # Decrease for latency
    processors:
      - bloblang: |
          root = this
```

### 2. Thread Pool Configuration

Adjust thread pool for parallel processing:

```yaml
pipeline:
  threads: 8  # Increase for CPU-bound workloads
```

### 3. Rate Limiting

Prevent overwhelming downstream services:

```yaml
pipeline:
  processors:
    - rate_limit:
        resource: ml_inference
        rate: 100
        interval: 1s
```

## High Availability Setup

### 1. Multi-Zone Deployment

Deploy across multiple availability zones:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bento-ml-worker
spec:
  replicas: 6
  template:
    spec:
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
                  - bento-ml-worker
              topologyKey: topology.kubernetes.io/zone
```

### 2. Graceful Shutdown

Configure graceful shutdown to prevent message loss:

```yaml
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 60
      containers:
      - name: bento
        lifecycle:
          preStop:
            exec:
              command: ["sh", "-c", "sleep 30"]
```

### 3. Circuit Breaking

Prevent cascading failures with circuit breakers:

```yaml
output:
  http_client:
    url: http://ml-service:8080/predict
    verb: POST
    retries: 3
    backoff:
      initial_interval: 1s
      max_interval: 5s
      max_elapsed_time: 30s
```

## Managing Configuration Files

### 1. Using ConfigMaps for Configuration

Store Bento configurations in ConfigMaps for easier management:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bento-api-gateway-config
data:
  config.yaml: |
    input:
      http_server:
        address: ":8080"
        path: /api/gateway
    
    pipeline:
      processors:
        - bloblang: |
            root = this
            root.request_id = uuid_v4()
    
    output:
      amqp:
        url: amqp://guest:guest@rabbitmq:5672/
        target: inference_requests
```

### 2. Using Helm for Configuration Management

For larger deployments, use Helm to manage Bento configurations:

```yaml
# In values.yaml
apiGateway:
  config:
    input:
      http_server:
        address: ":8080"
        path: /api/gateway
    output:
      amqp:
        url: "amqp://guest:guest@rabbitmq:5672/"
        target: "inference_requests"

# In templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bento-api-gateway-config
data:
  config.yaml: |
    {{- toYaml .Values.apiGateway.config | nindent 4 }}
```

This approach allows you to customize configurations per environment using Helm's value overrides.

### 3. Configuration Validation

Validate your Bento configurations before applying them:

```bash
bento -c config.yaml --print-json
```

This command will fail if the configuration is invalid, helping you catch issues before deployment. 