# Benthos Operations Guide

## Monitoring and Observability

### 1. Key Metrics to Monitor

| Metric | Description | Threshold |
|--------|-------------|-----------|
| `benthos_input_received` | Messages received by input | Rate change > 20% |
| `benthos_output_sent` | Messages sent by output | Rate change > 20% |
| `benthos_processor_latency` | Processing time | > 500ms |
| `benthos_output_error` | Output errors | > 0 |
| `benthos_input_connection_up` | Input connection status | 0 = down |
| `benthos_output_connection_up` | Output connection status | 0 = down |

### 2. Prometheus Dashboard

Example Grafana dashboard queries:

```
# Input/Output Rate
rate(benthos_input_received_total[5m])
rate(benthos_output_sent_total[5m])

# Error Rate
rate(benthos_output_error_total[5m])

# Processing Latency
histogram_quantile(0.95, sum(rate(benthos_processor_latency_seconds_bucket[5m])) by (le))
```

### 3. Log Monitoring

Benthos logs in JSON format by default. Key fields to monitor:

- `level`: Watch for `error` and `warn` levels
- `component`: Identifies which component generated the log
- `message`: Description of the event

Example log query in Loki:
```
{app="benthos"} | json | level="error" | count_over_time([5m]) > 0
```

## Scaling Strategies

### 1. Vertical Scaling

Increase resources for Benthos pods:

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
  name: benthos-ml-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: benthos-ml-worker
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

### 3. Scaling Considerations

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
      - mapping: |
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
  name: benthos-ml-worker
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
                  - benthos-ml-worker
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
      - name: benthos
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
    retry_period: 1s
    max_retry_backoff: 30s
    backoff_on:
      - 429  # Too Many Requests
      - 503  # Service Unavailable
```

## Troubleshooting

### 1. Common Issues and Solutions

| Issue | Possible Causes | Solutions |
|-------|----------------|-----------|
| High latency | Processor complexity, resource constraints | Increase resources, optimize processors |
| Connection failures | Network issues, service unavailability | Check network policies, service health |
| Message loss | Buffer overflow, output errors | Increase buffer size, add dead letter queues |
| High error rate | Invalid messages, downstream failures | Add validation, implement circuit breakers |

### 2. Debugging Techniques

#### Inspect Live Pipeline

Enable the HTTP server for debugging:

```yaml
http:
  address: 0.0.0.0:4195
  enabled: true
  debug_endpoints: true
```

Access debug endpoints:
- `/ready` - Readiness check
- `/metrics` - Prometheus metrics
- `/stats` - Pipeline statistics
- `/debug/pprof` - Profiling data

#### Trace Messages

Add tracing to track message flow:

```yaml
pipeline:
  processors:
    - log:
        level: DEBUG
        message: "Processing message: ${! json() }"
```

### 3. Recovery Procedures

#### Handling Backlog

When recovering from downtime with a large message backlog:

1. Temporarily increase replicas:
   ```bash
   kubectl scale deployment benthos-ml-worker --replicas=15
   ```

2. Implement a catch-up strategy:
   ```yaml
   pipeline:
     processors:
       - mapping: |
           # Prioritize older messages
           root.priority = if this.timestamp < now() - 3600 { 10 } else { 1 }
   ```

3. Monitor catch-up progress:
   ```
   rate(benthos_input_received_total[5m]) - rate(benthos_output_sent_total[5m])
   ```

## Configuration Management

### 1. Version Control

Store configurations in Git:
- Use a dedicated repository for Benthos configurations
- Implement branch protection and code reviews
- Tag releases with semantic versioning

### 2. CI/CD Pipeline

Implement a CI/CD pipeline for configuration changes:

1. Lint and validate configurations:
   ```bash
   benthos lint -c config.yaml
   ```

2. Test with sample data:
   ```bash
   benthos bloat -c config.yaml -r '{"test":"data"}'
   ```

3. Deploy to staging environment
4. Run integration tests
5. Deploy to production

### 3. Configuration Updates

Update configurations without downtime:

```bash
kubectl create configmap benthos-config-v2 --from-file=benthos.yaml=new-config.yaml
kubectl patch deployment benthos-ml-worker -p '{"spec":{"template":{"spec":{"volumes":[{"name":"config-volume","configMap":{"name":"benthos-config-v2"}}]}}}}'
```

## Security Considerations

### 1. Authentication

Secure RabbitMQ connections:

```yaml
input:
  rabbitmq:
    urls:
      - amqps://user:password@rabbitmq:5671/
    tls:
      enabled: true
      skip_cert_verify: false
      root_cas_file: /etc/benthos/certs/ca.pem
      client_cert_file: /etc/benthos/certs/client.pem
      client_key_file: /etc/benthos/certs/client-key.pem
```

### 2. Secrets Management

Use Kubernetes secrets for sensitive information:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: benthos-secrets
type: Opaque
data:
  rabbitmq-password: cGFzc3dvcmQ=  # base64 encoded
```

Reference in deployment:

```yaml
env:
  - name: RABBITMQ_PASSWORD
    valueFrom:
      secretKeyRef:
        name: benthos-secrets
        key: rabbitmq-password
```

### 3. Network Policies

Restrict network access:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: benthos-network-policy
spec:
  podSelector:
    matchLabels:
      app: benthos-ml-worker
  policyTypes:
  - Ingress
  - Egress
  ingress: []
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: rabbitmq
    ports:
    - protocol: TCP
      port: 5672
  - to:
    - podSelector:
        matchLabels:
          app: ml-service
    ports:
    - protocol: TCP
      port: 8080
```

## Next Steps

- [Benthos Concepts](./concepts.md)
- [Setup Guide](./setup.md)
- [Project Architecture](../../01-architecture/overview.md) 