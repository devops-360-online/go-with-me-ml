helm upgrade --install rabbitmq ./ \
  --namespace queue \
  --create-namespace \
  -f values.yaml \
  --dependency-update \
  --debug     

  helm search repo bitnami/rabbitmq --versions

 kubectl port-forward svc/rabbitmq -n queue 15672:15672      