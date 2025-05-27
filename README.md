# ML Inference Architecture

A scalable and production-ready architecture for deploying ML models, with a focus on high throughput, asynchronous processing, token-based quota management, and automatic scaling.

## What This Project Does

This platform helps you:

1. **Run ML models at scale** on Kubernetes
2. **Control costs** with token-based usage tracking
3. **Scale automatically** based on demand
4. **Process requests asynchronously** for better performance

## Project Structure

```
go-with-me-ml/
├── api/                  # API gateway and status service
│   ├── gateway/          # Request handling and validation
│   └── status/           # Status and quota endpoints
├── models/               # ML model services
│   ├── inference/        # Core inference code
│   └── config/           # Model-specific configurations
├── queue/                # Message queue components
│   ├── worker/           # Worker implementation
│   └── collector/        # Results collector
├── infrastructure/       # Infrastructure configuration
│   ├── kubernetes/       # K8s manifests
│   └── monitoring/       # Prometheus/Grafana configs
├── scripts/              # Utility scripts
└── docs/                 # Documentation
```

## How It Works

This project splits responsibilities across two repositories:

### 1. Data Infrastructure ([go-with-me-data](https://github.com/devops-360-online/go-with-me-data))
- PostgreSQL database (stores requests, results, and usage metrics)
- Redis cache (for real-time quota tracking)
- Other shared data services

### 2. ML Inference (This Repository)
- **API Gateway**: Receives requests and queues them in RabbitMQ
- **ML Worker**: Processes requests from the queue
- **Results Collector**: Records completed inference results
- **ML Service**: Runs the actual machine learning models
- **API Service**: Provides request status and quota information

## MLOps Architecture

This project follows MLOps best practices to ensure reliable, scalable, and maintainable ML systems. Our architecture implements the four continuous practices of MLOps:

### Key MLOps Components

1. **Continuous Integration (CI)**
   - Automated testing of code, data, and models
   - Version control for all artifacts
   - Consistent validation processes

2. **Continuous Deployment (CD)**
   - Automated model deployment
   - Containerized model serving
   - Deployment strategies (canary, blue/green)

3. **Continuous Training (CT)**
   - Automated model retraining
   - Performance-based training triggers
   - Model evaluation and promotion

4. **Continuous Monitoring (CM)**
   - Real-time performance tracking
   - Data drift detection
   - Automated alerting

### MLOps Tools Ecosystem

We leverage a variety of tools across different categories:

- **Version Control**: Git, DVC
- **CI/CD**: Jenkins, GitHub Actions
- **Containerization**: Docker, Kubernetes
- **Experiment Tracking**: MLflow, Weights & Biases
- **Monitoring**: Prometheus, Grafana
- **Workflow Orchestration**: Airflow, Kubeflow

For more details on our MLOps implementation, see the [MLOps documentation](docs/00-MLOps/).

## Key Features

- **Token-Based Quota System**: Track and limit usage precisely
- **Configuration-Driven Design**: Build complex workflows with minimal code
- **Auto-Scaling**: Automatically adjust resources based on demand
- **High Throughput**: Process requests asynchronously for better performance
- **Comprehensive Monitoring**: Built-in metrics and logging

## Getting Started

### Prerequisites
- Kubernetes cluster (v1.19+)
- kubectl and Helm 3+
- Deployed data infrastructure from [go-with-me-data](https://github.com/devops-360-online/go-with-me-data)

### Quick Deployment

1. Clone this repository
2. Use the deployment script: `./scripts/deploy.sh`

This script will:

1. Check for prerequisites (kubectl, helm)
2. Create Kubernetes namespace
3. Deploy PostgreSQL database: `kubectl apply -f infrastructure/kubernetes/db/`
4. Deploy Redis cache: `kubectl apply -f infrastructure/kubernetes/cache/`
5. Deploy ML service: `kubectl apply -f infrastructure/kubernetes/ml/`
6. Deploy RabbitMQ and Bento components: `kubectl apply -f infrastructure/kubernetes/queue/`
7. Initialize database schemas: `kubectl apply -f infrastructure/kubernetes/init/`

## Documentation

- [Architecture Overview](docs/01-architecture/overview.md)
- [Component Descriptions](docs/02-core-components/bento/concepts.md)
- [Deployment Guide](docs/03-deployment/kubernetes-setup.md)
- [Monitoring & Operations](docs/04-operations/monitoring.md)

REMARKS: GNU Make (optional)	The repo's Makefile automates builds.
Uses redis_hash to adjust quota.
sql_exec finalises the request record.


Metric	Where to look	Normal range
queue_messages_ready	RabbitMQ / Prometheus	Should trend to zero when load steady.
bento_input_received_total	Bento exporter	Grows at same rate as queue length decreases.
ml_tokens_processed_total	ML service exporter	Use for KEDA token-based scaling.
Pod CPU/GPU	kubectl top pods, Grafana	Drives HPA on model pods.
Redis keys *:quota:*	redis-cli --scan	Daily resets via cronjob / TTL.


Symptom	Likely cause	Fix
HTTP 429 on every request	Redis quota keys missing or mis-scoped	Ensure API Gateway mapping sets user_id exactly as Redis key expects.
Messages stuck in inference_requests queue	ML Worker replicas = 0 or can't reach ML service	kubectl get hpa / kubectl logs deploy/ml-worker; check service DNS.
ML Service OOMKilled	Model too large for default 512 Mi	Set resources.requests/limits.memory in ml-inference*.yaml.
GPU pods pending	No schedulable GPU node	Label node kubectl label node <node> nvidia.com/gpu=true or use node-selector.
Postgres connection refused	Wrong DSN or network policy	Verify POSTGRES_DSN env, look at service postgresql-primary.

7. Next things to tighten
Central auth service – Replace API keys with JWT & OIDC if you need multi-tenant SaaS.

Schema migrations – Add a Flyway or Alembic Job; running CREATE TABLE IF NOT EXISTS on every insert is safe but ugly.

Blue/Green for ML models – Deploy new model image next to the old one; use Bento branch processor to shadow-test outputs before switching.

Back-pressure – Enable RabbitMQ TTL + dead-letter to protect from runaway queue growth when model is slow.

CI/CD – Automate Docker build & helm upgrade per commit (GitHub Actions).

## 🚧 Areas for Improvement

### Architecture Enhancements
- ⚠️ **Service mesh missing** - No Istio/Linkerd for advanced traffic management
- ⚠️ **API versioning** - No clear versioning strategy for endpoints
- ⚠️ **Circuit breakers** - Limited resilience patterns for service failures

### 🔒 Security Improvements Needed
- ❌ **Hardcoded credentials** in examples (replace with secrets)
- ❌ **No authentication** on SSE endpoints
- ❌ **CORS allows all origins** (`"*"`) - should be restricted
- ❌ **Missing rate limiting** per IP address

### 🚀 Performance Optimizations
- ⚠️ **Synchronous model loading** - 38s inference time suggests cold starts
- ⚠️ **No connection pooling** for Redis/PostgreSQL
- ⚠️ **Missing caching layer** for repeated prompts

### 📊 Operational Maturity
- ❌ **No unit tests** - 0% test coverage
- ⚠️ **Limited monitoring** - Need Grafana dashboards
- ❌ **No CI/CD pipeline** - Manual deployments only
- ⚠️ **No backup strategy** for databases

### 🔧 Technical Debt
- ⚠️ **Null user handling** - Seeing 'null' in collector logs
- ⚠️ **Missing request deduplication** - Same prompts processed multiple times
- ⚠️ **No request timeout handling** in SSE connections
- ⚠️ **Race conditions** - Client can miss notifications

## 🎯 Roadmap

### Phase 1: Security & Reliability (Week 1-2)
1. Replace hardcoded passwords with Kubernetes secrets
2. Add JWT authentication to all endpoints
3. Implement rate limiting with Redis
4. Add circuit breakers with retry logic

### Phase 2: Performance (Month 1)
1. Implement Redis connection pooling
2. Add prompt/result caching layer
3. Optimize model loading with warm-up
4. Add request batching for efficiency

### Phase 3: Operations (Month 2)
1. Set up GitHub Actions CI/CD pipeline
2. Add comprehensive unit and integration tests
3. Create Grafana dashboards for all metrics
4. Implement database backup jobs

### Phase 4: Advanced Features (Quarter 1)
1. A/B testing framework for models
2. Multi-model serving with routing
3. Admin UI for quota management
4. WebSocket support for streaming

## 📝 Notes

- Using **Bento** by WarpStream/Confluent for stream processing
- KEDA configuration requires KEDA operator to be installed first
- All improvements are tracked in GitHub issues for prioritization
