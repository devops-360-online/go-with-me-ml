# RabbitMQ Documentation

## Overview
Documentation for the message queue component of our ML inference system.

## Contents

### [1. Concepts](./concepts.md)
- Message queuing fundamentals
- AMQP protocol
- Exchange types and patterns
- Message lifecycle
- Quality of Service (QoS)

### [2. Setup](./setup.md)
- Installation guide
- Basic configuration
- Security setup
- High availability
- Performance tuning

### [3. Operations](./operations.md)
- Monitoring
- Troubleshooting
- Maintenance
- Best practices
- Common pitfalls

## Quick Start

1. Install RabbitMQ:
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install rabbitmq bitnami/rabbitmq \
  --namespace async-ml \
  --set auth.username=user \
  --set auth.password=YOUR_PASSWORD \
  --set persistence.enabled=true
```

2. Verify installation:
```bash
kubectl get pods -n async-ml
kubectl port-forward svc/rabbitmq 15672:15672 -n async-ml
```

3. Access management UI:
- URL: http://localhost:15672
- Username: user
- Password: (from installation)

## Related Resources
- [Configuration Templates](../../../config/rabbitmq/)
- [Example Code](../../../examples/rabbitmq/)
- [Workshop Exercises](../../05-workshops/exercises/rabbitmq/) 