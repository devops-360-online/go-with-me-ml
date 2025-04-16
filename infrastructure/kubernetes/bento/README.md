 helm upgrade --install bento ./ \
  --namespace ml-inference \
  --create-namespace \
  -f values.yaml \
  --dependency-update \
  --debug

  helm uninstall bento --namespace  ml-inference


kubectl port-forward -n ml-inference svc/bento-api-gateway 8080:80