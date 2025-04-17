#!/bin/bash
set -e

# Create namespace if it doesn't exist
kubectl create namespace ml-inference --dry-run=client -o yaml | kubectl apply -f -

# Deploy PostgreSQL
echo "Deploying PostgreSQL..."
kubectl apply -f database/postgresql.yaml
echo "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=available --timeout=120s deployment/postgresql -n ml-inference

# Deploy Redis
echo "Deploying Redis..."
kubectl apply -f database/redis.yaml
echo "Waiting for Redis to be ready..."
kubectl wait --for=condition=available --timeout=60s deployment/redis -n ml-inference

# Deploy RabbitMQ (assuming it's already deployed in the queue namespace)
echo "Checking RabbitMQ status..."
kubectl get pods -n queue | grep rabbitmq

# Deploy ML Inference service
echo "Deploying ML Inference service..."
kubectl apply -f models/ml-inference.yaml
echo "Waiting for ML Inference service to be ready..."
kubectl wait --for=condition=available --timeout=180s deployment/ml-inference -n default

# Deploy Bento components
echo "Deploying Bento components..."
kubectl apply -f bento-components.yaml

echo "Waiting for Bento components to be ready..."
kubectl wait --for=condition=available --timeout=60s deployment/bento-api-gateway -n ml-inference
kubectl wait --for=condition=available --timeout=60s deployment/bento-ml-worker -n ml-inference
kubectl wait --for=condition=available --timeout=60s deployment/bento-results-collector -n ml-inference

echo "System deployed successfully!"
echo "You can test the system with:"
echo "curl -X POST \"http://localhost/generate\" -H \"Content-Type: application/json\" -d '{\"prompt\":\"Hello, world!\"}'" 