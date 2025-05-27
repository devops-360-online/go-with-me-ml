 helm upgrade --install keda ./ \
  --namespace keda \
  --create-namespace \
  -f values.yaml \
  --dependency-update \
  --debug
