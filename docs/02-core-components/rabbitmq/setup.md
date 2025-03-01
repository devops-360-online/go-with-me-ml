# RabbitMQ Setup and Configuration Guide

## Overview
This document provides detailed information about setting up and configuring RabbitMQ for the Go With Me ML project.

## Installation

### Using Helm
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install rabbitmq bitnami/rabbitmq \
  --namespace async-ml \
  --set auth.username=user \
  --set auth.password=YOUR_PASSWORD \
  --set persistence.enabled=true
```

## AMQP Configuration

### Exchange Setup
```yaml
exchanges:
  - name: ml_requests
    type: direct
    durable: true
    auto_delete: false
    internal: false
    arguments: {}
```

### Queue Setup
```yaml
queues:
  - name: inference_queue
    durable: true
    auto_delete: false
    exclusive: false
    arguments:
      x-max-priority: 10
      x-queue-type: classic
```

### Binding Configuration
```yaml
bindings:
  - exchange: ml_requests
    queue: inference_queue
    routing_key: inference
```

## High Availability Configuration

### Cluster Setup
```yaml
cluster:
  formation:
    peer_discovery_backend: k8s
    k8s:
      service_name: rabbitmq-cluster
      address_type: hostname
  partition_handling: autoheal
```

### Queue Mirroring
For RabbitMQ 3.8+:
```yaml
policies:
  - name: ha-policy
    pattern: ".*"
    definition:
      ha-mode: all
      ha-sync-mode: automatic
```

## Security Configuration

### TLS Setup
```yaml
ssl_options:
  cacertfile: /path/to/ca_certificate.pem
  certfile: /path/to/server_certificate.pem
  keyfile: /path/to/server_key.pem
  verify: verify_peer
  fail_if_no_peer_cert: true
```

### Access Control
```yaml
permissions:
  - user: ml_producer
    configure: "^ml_.*"
    write: "^ml_.*"
    read: "^$"
  
  - user: ml_consumer
    configure: "^$"
    write: "^$"
    read: "^ml_.*"
```

## Monitoring and Management

### Prometheus Integration
```yaml
prometheus:
  enabled: true
  operator:
    serviceMonitor:
      enabled: true
      namespace: monitoring
```

### Management Plugin
The management plugin is accessible at:
- URL: `http://rabbitmq-host:15672`
- Default credentials:
  - Username: `user`
  - Password: (specified in helm values)

## Performance Tuning

### Memory Settings
```yaml
resources:
  limits:
    memory: 2Gi
  requests:
    memory: 1Gi
```

### Message Settings
```yaml
rabbitmq:
  additional_config: |
    total_memory_available_override_value = 2GB
    vm_memory_high_watermark.relative = 0.8
    channel_max = 2000
    max_message_size = 134217728  # 128MB
```

## Troubleshooting

### Common Issues

1. **Connection Issues**
   - Check network policies
   - Verify credentials
   - Ensure ports are open (5672 for AMQP, 15672 for management)

2. **Performance Issues**
   - Monitor queue length
   - Check consumer acknowledgments
   - Review memory usage

3. **High Availability Issues**
   - Check node status
   - Verify network partition handling
   - Review cluster formation logs

## Best Practices

1. **Message Handling**
   - Use publisher confirms
   - Implement consumer acknowledgments
   - Set appropriate prefetch counts

2. **Security**
   - Rotate credentials regularly
   - Use TLS for production
   - Implement proper access control

3. **Monitoring**
   - Set up alerting for queue length
   - Monitor memory usage
   - Track consumer lag

## References

- [Official RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [AMQP 0-9-1 Protocol](https://www.rabbitmq.com/tutorials/amqp-concepts.html)
- [Kubernetes RabbitMQ Operator](https://www.rabbitmq.com/kubernetes/operator/operator-overview.html) 