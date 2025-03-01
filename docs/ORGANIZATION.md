# Repository Organization

This document outlines the organization of the ML Inference Architecture repository and the changes made to improve its structure.

## Directory Structure

```
ml-inference-architecture/
├── config/                    # Configuration files
│   ├── benthos/               # Structured Benthos configurations
│   │   ├── api-gateway/       # API Gateway specific configs
│   │   ├── ml-worker/         # ML Worker specific configs
│   │   ├── results-collector/ # Results Collector specific configs
│   │   └── common/            # Shared Benthos components
│   └── schema.sql             # Database schema
│
├── docs/                      # Documentation
│   ├── 01-architecture/       # Architecture documentation
│   └── 02-core-components/    # Component-specific documentation
│
├── manifests/                 # Kubernetes manifests
│   ├── api-service/           # API service manifests
│   ├── benthos/               # Benthos component manifests
│   ├── keda/                  # KEDA ScaledObject definitions
│   └── ml-service/            # ML service manifests
│
├── src/                       # Source code
│   ├── api-service/           # Node.js API service
│   ├── ml-inference/          # Python ML service
│   └── scripts/               # Utility scripts
│
├── helm-values/               # Helm chart values
├── charts/                    # Helm charts
└── README.md                  # Main README
```

## Changes Made

### 1. Removed Duplicate Configurations

Deleted duplicate Benthos configuration files:
- `config/benthos-api-gateway.yaml`
- `config/benthos-ml-worker.yaml`
- `config/benthos-results-collector.yaml`
- `config/benthos.yaml`

These files contained similar functionality to the structured versions in `config/benthos/` but without using the common components.

### 2. Removed Empty or Unused Files

Deleted empty or unused files:
- `manifests/keda-scaledobject.yaml` (replaced by more specific configurations in `manifests/keda/`)
- `manifests/benthos/api-gateway.yaml` (empty file)
- `manifests/ml-service/ml-inference.yaml` (empty file)

### 3. Created Proper Kubernetes Manifests

Created proper Kubernetes manifests:
- `manifests/benthos/api-gateway.yaml`: Deployment, Service, and ConfigMap for the Benthos API Gateway
- `manifests/ml-service/ml-inference.yaml`: Deployment, Service, and PVC for the ML Inference service

### 4. Added Documentation

Added README files to explain the structure and purpose of each directory:
- `config/benthos/README.md`: Explains the Benthos configuration structure
- `manifests/README.md`: Explains the Kubernetes manifests structure
- `src/README.md`: Explains the source code structure
- Updated `docs/README.md`: Updated to reflect the current state of the repository

### 5. Improved Organization

The repository now follows a more logical organization:
- **Configuration**: All configuration files are in the `config` directory, with Benthos configurations organized by component and common elements
- **Deployment**: All Kubernetes manifests are in the `manifests` directory, organized by component
- **Documentation**: All documentation is in the `docs` directory, organized by topic
- **Source Code**: All source code is in the `src` directory, organized by component

## Benefits of the New Structure

1. **Reduced Duplication**: Common configuration elements are now shared across components
2. **Improved Maintainability**: Changes to common elements only need to be made in one place
3. **Better Organization**: Files are organized by purpose and component
4. **Enhanced Documentation**: Each directory has a README explaining its purpose and structure
5. **Clearer Deployment**: Kubernetes manifests are properly structured and documented

## Next Steps

1. **Standardize Naming**: Ensure consistent naming conventions across all files
2. **Add CI/CD**: Set up CI/CD pipelines for building and deploying the components
3. **Enhance Documentation**: Add more detailed documentation for each component
4. **Implement Testing**: Add unit and integration tests for the components 