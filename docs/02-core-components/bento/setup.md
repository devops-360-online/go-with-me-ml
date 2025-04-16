# Bento Setup Guide

## What We're Setting Up

In this guide, we'll set up three Bento components that work together to handle ML inference without writing custom code:

1. **API Gateway Bento**: Receives HTTP requests and forwards them to RabbitMQ
2. **ML Worker Bento**: Pulls requests from RabbitMQ, calls ML services, and returns results
3. **Results Collector Bento**: Stores processed results in PostgreSQL

This configuration-driven approach allows us to:
- Quickly modify data flows without redeploying code
- Add validation, error handling, and retries through configuration
- Scale each component independently based on load
- Monitor the entire pipeline with built-in metrics

## Installation Options

### 1. Docker
```bash
docker pull warpstreamlabs/bento:latest
```

### 2. Kubernetes via Helm
```bash
helm repo add warpstream https://warpstreamlabs.github.io/bento-helm-chart
helm repo update
helm install bento warpstream/bento
```

### 3. Binary Installation
```bash
curl -Lsf https://sh.bento.dev | bash
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
    - bloblang: |
        root = this
        root.processed_at = now()

output:
  stdout: {}
```

Run Bento with this configuration:

```bash
bento -c config.yaml
```

Test your pipeline:

```bash
curl -X POST http://localhost:4195/post -d '{"message":"hello world"}'
```

### 2. Environment Variables

Bento supports environment variables in configuration:

```yaml
input:
  amqp:
    url: amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@${RABBITMQ_HOST}:5672/
    queue: ${QUEUE_NAME}
```

Run with environment variables:

```bash
RABBITMQ_USER=guest RABBITMQ_PASS=password RABBITMQ_HOST=localhost QUEUE_NAME=inference bento -c config.yaml
```

## Kubernetes Deployment

### 1. Basic Deployment

Create a ConfigMap for your Bento configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bento-config
data:
  bento.yaml: |
    input:
      amqp:
        url: amqp://guest:password@rabbitmq-service:5672/
        queue: inference_requests
    
    pipeline:
      processors:
        - bloblang: |
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
  name: bento-ml-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bento-ml-worker
  template:
    metadata:
      labels:
        app: bento-ml-worker
    spec:
      containers:
      - name: bento
        image: warpstreamlabs/bento:latest
        args: ["-c", "/bento/config/bento.yaml"]
        volumeMounts:
        - name: config-volume
          mountPath: /bento/config
      volumes:
      - name: config-volume
        configMap:
          name: bento-config
```

### 2. Horizontal Pod Autoscaler

Scale Bento based on CPU usage:

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
  name: bento-ml-worker-hpa-queue
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

## Helm Chart Deployment

For production deployment, we recommend using our Helm chart approach:

### 1. Creating an Umbrella Chart

Create a directory structure:

```
infrastructure/kubernetes/bento/
├── Chart.yaml
├── values.yaml
├── files/
│   ├── api-gateway-config.yml
│   ├── queue-worker-config.yml
│   └── queue-collector-config.yml
└── templates/
    └── configMap-config.yml
```

### 2. Chart.yaml

```yaml
apiVersion: v2
name: bento
description: A high-performance and resilient stream processor deployment using the Bento Helm chart.
version: 1.0.0
appVersion: "1.2.0"  # Adjust to match your desired Bento version
kubeVersion: ">=1.25.0-0"
helmVersion: ">=3.15.0"
dependencies:
  - name: bento
    repository: "https://warpstreamlabs.github.io/bento-helm-chart"
    version: "0.1.0"  # Specify the Bento chart version
    condition: bento.enabled
```

### 3. values.yaml

```yaml
# Enable the Bento dependency chart
bento:
  enabled: true  # This will enable the Bento chart dependency

# Metrics, tracing, and logging configurations
metrics:
  prometheus: {}

tracing:
  openTelemetry:
    http: []
    grpc: []
    tags: {}

logger:
  level: INFO
  static_fields:
    '@service': bento

extraVolumes:
  - name: bento-config-api-gateway-volume
    configMap:
      name: bento-config-api-gateway  
  - name: bento-config-queue-collector-volume
    configMap:
      name: bento-config-queue-collector
  - name: bento-config-queue-worker-volume
    configMap:
      name: bento-config-queue-worker
  
extraVolumeMounts:
  - name: bento-config-api-gateway-volume
    mountPath: /etc/bento/api-gateway/config.yaml 
    subPath: config.yaml            
    readOnly: true
  - name: bento-config-queue-collector-volume
    mountPath: /etc/bento/queue-collector/config.yaml  
    subPath: config.yaml             
    readOnly: true
  - name: bento-config-queue-worker-volume
    mountPath: /etc/bento/queue-worker/config.yaml  
    subPath: config.yaml             
    readOnly: true
```

### 4. ConfigMap Template

Create `templates/configMap-config.yml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bento-config-api-gateway
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ include "bento.name" . }}
    chart: {{ include "bento.chart" . }}
    release: {{ .Release.Name }}
    heritage: {{ .Release.Service }}
data:
  config.yaml: |-
{{ (.Files.Get "files/api-gateway-config.yml") | indent 4 }}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: bento-config-queue-collector
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ include "bento.name" . }}
    chart: {{ include "bento.chart" . }}
    release: {{ .Release.Name }}
    heritage: {{ .Release.Service }}
data:
  config.yaml: |-
{{ (.Files.Get "files/queue-collector-config.yml") | indent 4 }}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: bento-config-queue-worker
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ include "bento.name" . }}
    chart: {{ include "bento.chart" . }}
    release: {{ .Release.Name }}
    heritage: {{ .Release.Service }}
data:
  config.yaml: |-
{{ (.Files.Get "files/queue-worker-config.yml") | indent 4 }}
```

### 5. Deploy with Helm

```bash
# First dependency update
helm dependency update infrastructure/kubernetes/bento/

# Then install/upgrade
helm upgrade --install bento-components infrastructure/kubernetes/bento/ --namespace ml-inference
``` 