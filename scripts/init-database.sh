#!/bin/bash
# Database Schema Initialization Script
# This script applies the database initialization job to create the necessary tables

set -e

# Print usage information
function print_usage() {
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -h, --help                 Show this help message"
  echo "  -n, --namespace NAMESPACE  Kubernetes namespace (default: default)"
  echo "  -w, --wait                 Wait for the job to complete"
  echo "  -t, --timeout SECONDS      Timeout in seconds when waiting (default: 300)"
}

# Default values
NAMESPACE="default"
WAIT=false
TIMEOUT=300

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
    -w|--wait)
      WAIT=true
      shift
      ;;
    -t|--timeout)
      TIMEOUT="$2"
      shift
      shift
      ;;
    *)
      echo "Unknown option: $1"
      print_usage
      exit 1
      ;;
  esac
done

echo "Applying database initialization job in namespace: $NAMESPACE"
kubectl apply -f deployments/manifests/migrations/init-schema.yaml -n $NAMESPACE

if [ "$WAIT" = true ]; then
  echo "Waiting for job to complete (timeout: ${TIMEOUT}s)..."
  kubectl wait --for=condition=complete job/ml-db-init --timeout=${TIMEOUT}s -n $NAMESPACE
  
  # Check if the job was successful
  if [ $? -eq 0 ]; then
    echo "Database initialization completed successfully!"
    
    # Print the logs from the job
    POD=$(kubectl get pods -n $NAMESPACE -l job-name=ml-db-init -o jsonpath='{.items[0].metadata.name}')
    echo "Job logs:"
    kubectl logs $POD -n $NAMESPACE
  else
    echo "Database initialization failed or timed out!"
    exit 1
  fi
else
  echo "Job applied. Use 'kubectl get jobs -n $NAMESPACE' to check status."
fi 