# Benthos Configuration Structure

This directory contains the configuration files for all Benthos components in the ML inference architecture.

## Directory Structure

- **api-gateway/**: Configuration for the API Gateway component that receives HTTP requests and forwards them to RabbitMQ
- **ml-worker/**: Configuration for the ML Worker component that processes inference requests from RabbitMQ
- **results-collector/**: Configuration for the Results Collector component that stores processed results in PostgreSQL
- **common/**: Shared configuration components used by multiple Benthos instances

## Common Components

The `common/` directory contains reusable configuration components:

- **observability.yaml**: Common logging and metrics configurations
- **quota.yaml**: Processors for token estimation and quota checking
- **redis.yaml**: Redis operations for quota management
- **sql.yaml**: SQL operations for request tracking and result storage

## Usage

Each Benthos component imports the common components it needs using the `resources` section. For example:

```yaml
resources:
  - label: redis_get_request_quota
    path: /benthos/common/redis.yaml
  - label: sql_store_request
    path: /benthos/common/sql.yaml
  - label: metrics_config
    path: /benthos/common/observability.yaml
```

## Deployment

When deploying to Kubernetes, these configuration files are mounted as ConfigMaps. The Kubernetes manifests for these deployments can be found in the `manifests/benthos/` directory. 