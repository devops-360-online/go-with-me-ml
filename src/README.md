# Source Code

This directory contains the source code for the ML inference architecture components.

## Directory Structure

- **api-service/**: Node.js API service for handling status checks and quota information
- **ml-inference/**: Python ML service for running inference on machine learning models
- **scripts/**: Utility scripts for development, deployment, and maintenance

## Components

### API Service

The API service is a Node.js application that provides endpoints for:

- Checking request status
- Retrieving quota information
- Health checks

It interacts with PostgreSQL for request data and Redis for quota management.

### ML Inference Service

The ML inference service is a Python application that:

- Loads machine learning models
- Processes inference requests
- Reports token usage metrics
- Handles batching and optimization

### Scripts

The scripts directory contains utility scripts for:

- Local development setup
- Database migrations
- Monitoring and observability setup
- CI/CD pipelines

## Development

To run these components locally:

```bash
# API Service
cd src/api-service
npm install
npm start

# ML Inference Service
cd src/ml-inference
pip install -r requirements.txt
python app.py
```

## Deployment

For deployment to Kubernetes, Docker images are built from these source directories. The Kubernetes manifests for deploying these components can be found in the `manifests/` directory. 