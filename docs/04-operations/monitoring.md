# Monitoring Setup

This guide describes how to set up monitoring for the ML Inference Architecture.

## Overview

The ML Inference Architecture includes built-in support for metrics and logging. These can be collected and visualized using standard tools like Prometheus and Grafana.

## Metrics Collection

### Prometheus

All components expose Prometheus metrics:

- **Benthos components**: Expose metrics on the `/metrics` endpoint (port 9090)
- **ML Service**: Exposes metrics on the `/metrics` endpoint (port 9090)
- **API Service**: Exposes metrics on the `/metrics` endpoint (port 9090)

### Installing Prometheus

```bash
# Add Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus
helm install prometheus prometheus-community/prometheus
```

### Configure Prometheus

Create a Prometheus configuration to scrape metrics from the components:

```yaml
# prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    
    scrape_configs:
      - job_name: 'benthos-api-gateway'
        kubernetes_sd_configs:
          - role: service
        relabel_configs:
          - source_labels: [__meta_kubernetes_service_name]
            regex: benthos-api-gateway
            action: keep
      
      - job_name: 'benthos-ml-worker'
        kubernetes_sd_configs:
          - role: service
        relabel_configs:
          - source_labels: [__meta_kubernetes_service_name]
            regex: benthos-ml-worker
            action: keep
      
      - job_name: 'ml-inference'
        kubernetes_sd_configs:
          - role: service
        relabel_configs:
          - source_labels: [__meta_kubernetes_service_name]
            regex: ml-inference
            action: keep
```

Apply the configuration:

```bash
kubectl apply -f prometheus-config.yaml
```

## Visualization

### Grafana

Install Grafana to visualize the metrics:

```bash
# Add Helm repositories
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Grafana
helm install grafana grafana/grafana
```

### Grafana Dashboards

Create dashboards for:

1. **API Gateway**: Request rates, latencies, and quotas
2. **ML Worker**: Processing rates, token usage, and queue depths
3. **ML Service**: Inference times, batch sizes, and resource utilization

Sample dashboard JSON configurations are available in the `config/grafana/` directory.

## Logging

### Centralized Logging

All components use structured JSON logging, which can be collected using tools like Fluentd, Fluent Bit, or Loki.

### Installing Loki Stack

```bash
# Add Helm repositories
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Loki Stack (includes Promtail and Grafana)
helm install loki grafana/loki-stack
```

## Alerting

### Configure Prometheus Alerting Rules

Create alerting rules for critical conditions:

```yaml
# prometheus-alerts.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-alerts
data:
  alerts.yml: |
    groups:
      - name: ml-inference-alerts
        rules:
          - alert: HighRequestLatency
            expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 1
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "High request latency"
              description: "95th percentile latency is over 1s"
          
          - alert: QuotaExceeded
            expr: rate(quota_exceeded_total[5m]) > 0
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "Quota exceeded events detected"
              description: "Users are hitting quota limits"
```

Apply the alerting rules:

```bash
kubectl apply -f prometheus-alerts.yaml
```

## Integration with Cloud Providers

### AWS CloudWatch

For AWS deployments, metrics and logs can be forwarded to CloudWatch using the CloudWatch agent.

### Google Cloud Operations

For GCP deployments, metrics and logs can be forwarded to Google Cloud Operations using the Google Cloud Operations agent. 