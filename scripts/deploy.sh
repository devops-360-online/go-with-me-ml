#!/bin/bash
# ML Inference Platform Deployment Script
# This script deploys all components of the ML Inference Platform

set -e

# Print usage information
function print_usage() {
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -h, --help                 Show this help message"
  echo "  -n, --namespace NAMESPACE  Kubernetes namespace (default: default)"
  echo "  -d, --data-namespace NS    Data infrastructure namespace (default: data-infra)"
  echo "  --skip-rabbitmq           Skip RabbitMQ installation"
  echo "  --skip-keda               Skip KEDA installation"
  echo "  --skip-benthos            Skip Benthos components installation"
  echo "  --skip-services           Skip ML and API services installation"
  echo "  --skip-db-init            Skip database initialization"
}

# Default values
NAMESPACE="default"
DATA_NAMESPACE="data-infra"
SKIP_RABBITMQ=false
SKIP_KEDA=false
SKIP_BENTHOS=false
SKIP_SERVICES=false
SKIP_DB_INIT=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -h|--help)
      print_usage
      exit 0
      ;;
    -n|--namespace)
      NAMESPACE="$2"
      shift
      shift
      ;;
    -d|--data-namespace)
      DATA_NAMESPACE="$2"
      shift
      shift
      ;;
    --skip-rabbitmq)
      SKIP_RABBITMQ=true
      shift
      ;;
    --skip-keda)
      SKIP_KEDA=true
      shift
      ;;
    --skip-benthos)
      SKIP_BENTHOS=true
      shift
      ;;
    --skip-services)
      SKIP_SERVICES=true
      shift
      ;;
    --skip-db-init)
      SKIP_DB_INIT=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      print_usage
      exit 1
      ;;
  esac
done

# Create namespace if it doesn't exist
kubectl get namespace $NAMESPACE > /dev/null 2>&1 || kubectl create namespace $NAMESPACE
echo "Using namespace: $NAMESPACE"

# Deploy external services secrets
echo "Deploying external services secrets..."
kubectl apply -f deployments/manifests/secrets/external-services.yaml -n $NAMESPACE
kubectl apply -f deployments/manifests/secrets/rabbitmq-credentials.yaml -n $NAMESPACE

# Deploy RabbitMQ using Helm
if [ "$SKIP_RABBITMQ" = false ]; then
  echo "Deploying RabbitMQ using Helm..."
  helm repo add bitnami https://charts.bitnami.com/bitnami
  helm repo update
  helm upgrade --install rabbitmq bitnami/rabbitmq \
    -f deployments/helm/rabbitmq/values.yaml \
    -n $NAMESPACE
fi

# Deploy KEDA using Helm
if [ "$SKIP_KEDA" = false ]; then
  echo "Deploying KEDA using Helm..."
  helm repo add kedacore https://kedacore.github.io/charts
  helm repo update
  helm upgrade --install keda kedacore/keda \
    -f deployments/helm/keda/values.yaml \
    --namespace keda --create-namespace
  
  # Deploy KEDA scalers
  echo "Deploying KEDA scalers..."
  kubectl apply -f deployments/manifests/keda/ml-worker-scaler.yaml -n $NAMESPACE
fi

# Initialize database schema
if [ "$SKIP_DB_INIT" = false ]; then
  echo "Initializing database schema..."
  ./scripts/init-database.sh -n $NAMESPACE -w
fi

# Deploy Benthos components
if [ "$SKIP_BENTHOS" = false ]; then
  echo "Deploying Benthos components..."
  kubectl apply -f deployments/manifests/benthos/api-gateway.yaml -n $NAMESPACE
  kubectl apply -f deployments/manifests/benthos/ml-worker.yaml -n $NAMESPACE
  kubectl apply -f deployments/manifests/benthos/results-collector.yaml -n $NAMESPACE
fi

# Deploy ML and API services
if [ "$SKIP_SERVICES" = false ]; then
  echo "Deploying ML and API services..."
  kubectl apply -f deployments/manifests/ml-service/ml-inference.yaml -n $NAMESPACE
  kubectl apply -f deployments/manifests/api-service/api-service.yaml -n $NAMESPACE
fi

echo "Deployment completed successfully!"
echo "Use 'kubectl get pods -n $NAMESPACE' to check the status of the pods." 