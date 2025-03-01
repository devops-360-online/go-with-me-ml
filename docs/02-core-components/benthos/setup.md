# Benthos Setup Guide

## What We're Setting Up

In this guide, we'll set up three Benthos components that work together to handle ML inference without writing custom code:

1. **API Gateway Benthos**: Receives HTTP requests and forwards them to RabbitMQ
2. **ML Worker Benthos**: Pulls requests from RabbitMQ, calls ML services, and returns results
3. **Results Collector Benthos**: Stores processed results in PostgreSQL

This configuration-driven approach allows us to:
- Quickly modify data flows without redeploying code
- Add validation, error handling, and retries through configuration
- Scale each component independently based on load
- Monitor the entire pipeline with built-in metrics

## Installation Options

### 1. Docker
```bash
docker pull jeffail/benthos:latest
```

### 2. Kubernetes via Helm
```bash
helm repo add benthos https://helm.benthos.dev
helm repo update
helm install benthos benthos/benthos
```

### 3. Binary Installation
```bash
curl -Lsf https://sh.benthos.dev | bash
```

## Basic Configuration

### 1. Creating Your First Pipeline

Create a file named `config.yaml`:

```yaml
input:
  http_server:
    path: /post
    address: 0.0.0.0:4195

pipeline:
  processors:
    - mapping: |
        root = this
        root.processed_at = now()

output:
  stdout: {}
```

Run Benthos with this configuration:

```bash
benthos -c config.yaml
```

Test your pipeline:

```bash
curl -X POST http://localhost:4195/post -d '{"message":"hello world"}'
```

### 2. Environment Variables

Benthos supports environment variables in configuration:

```yaml
input:
  rabbitmq:
    urls:
      - amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@${RABBITMQ_HOST}:5672/
    queue: ${QUEUE_NAME}
```

Run with environment variables:

```bash
RABBITMQ_USER=guest RABBITMQ_PASS=password RABBITMQ_HOST=localhost QUEUE_NAME=inference benthos -c config.yaml
```

## Kubernetes Deployment

### 1. Basic Deployment

Create a ConfigMap for your Benthos configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: benthos-config
data:
  benthos.yaml: |
    input:
      rabbitmq:
        urls:
          - amqp://guest:password@rabbitmq-service:5672/
        queue: inference_requests
    
    pipeline:
      processors:
        - mapping: |
            root = this
    
    output:
      http_client:
        url: http://ml-service:8080/predict
        verb: POST
```

Create a Deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: benthos-ml-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: benthos-ml-worker
  template:
    metadata:
      labels:
        app: benthos-ml-worker
    spec:
      containers:
      - name: benthos
        image: jeffail/benthos:latest
        args: ["-c", "/benthos/config/benthos.yaml"]
        volumeMounts:
        - name: config-volume
          mountPath: /benthos/config
      volumes:
      - name: config-volume
        configMap:
          name: benthos-config
```

### 2. Horizontal Pod Autoscaler

Scale Benthos based on CPU usage:

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
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### 3. Custom Metrics Autoscaling

Scale based on RabbitMQ queue length:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: benthos-ml-worker-hpa-queue
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

## Common Configurations

### 1. API Gateway

```yaml
input:
  http_server:
    path: /api/v1/inference
    address: 0.0.0.0:8080

pipeline:
  processors:
    - mapping: |
        root.request_id = uuid_v4()
        root.timestamp = now()
        root = this

output:
  rabbitmq:
    urls:
      - amqp://guest:password@rabbitmq:5672/
    exchange: inference
    key: requests
```

### 2. ML Worker

```yaml
input:
  rabbitmq:
    urls:
      - amqp://guest:password@rabbitmq:5672/
    queue: inference_requests
    consumer_tag: ml-worker

pipeline:
  processors:
    - mapping: |
        root.model_input = this.prompt
        root.parameters = this.parameters
    - http:
        url: http://ml-model:8080/predict
        verb: POST
        headers:
          Content-Type: application/json

output:
  rabbitmq:
    urls:
      - amqp://guest:password@rabbitmq:5672/
    exchange: inference
    key: responses
```

### 3. Results Collector

```yaml
input:
  rabbitmq:
    urls:
      - amqp://guest:password@rabbitmq:5672/
    queue: inference_responses

pipeline:
  processors:
    - mapping: |
        root = this

output:
  postgres:
    driver: postgres
    dsn: postgres://user:password@postgres:5432/ml_results?sslmode=disable
    table: inference_results
    columns:
      - request_id
      - result
      - created_at
    args_mapping: |
      root = [
        this.request_id,
        this.result,
        now()
      ]
```

## Monitoring Setup

### 1. Prometheus Metrics

```yaml
# Add to your Benthos config
metrics:
  prometheus:
    prefix: benthos
    path_mapping: /metrics
    address: 0.0.0.0:9090
```

Create a Prometheus ServiceMonitor:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: benthos-monitor
spec:
  selector:
    matchLabels:
      app: benthos-ml-worker
  endpoints:
  - port: metrics
    interval: 15s
```

### 2. Jaeger Tracing

```yaml
# Add to your Benthos config
tracer:
  jaeger:
    agent_address: jaeger-agent:6831
    service_name: benthos-ml-pipeline
```

## Troubleshooting

### 1. Common Issues

- **Connection Errors**: Check network policies and service endpoints
- **Configuration Errors**: Validate YAML syntax and field names
- **Performance Issues**: Check resource limits and processor complexity

### 2. Debugging Tools

- **Benthos Bloat**: Test configurations with sample data
  ```bash
  benthos bloat -c config.yaml
  ```

- **Benthos Lint**: Validate configuration files
  ```bash
  benthos lint -c config.yaml
  ```

- **Benthos List**: View available components
  ```bash
  benthos list inputs
  benthos list processors
  benthos list outputs
  ```

## Next Steps

- [Benthos Concepts](./concepts.md)
- [Operations Guide](./operations.md)
- [Project Architecture](../../01-architecture/overview.md) 